"""
parse_conversation — extract a concept checklist from a ChatGPT thread.

Three concept kinds:
  technical   - a component/library/pattern that was coded or proposed
  idea        - a vision, intent, or framing the user or assistant named
  decision    - a resolution the user expressed ("let's go with X")

Output (per thread):
  harvest/<id>_<slug>/concepts.json   - machine-readable checklist
  harvest/<id>_<slug>/concepts.md     - human-readable checklist

Local-only by default. No LLM calls.

Usage:
  python parse_conversation.py 487
  python parse_conversation.py 487 --out /tmp/concepts.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()
MEMORY_PATH = BASE / "memory_db.json"

CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

# Library/framework signatures → human label for technical concepts.
# Matched against code block bodies and import/require lines.
TECH_SIGNATURES: list[tuple[str, re.Pattern[str], str]] = [
    ("flask-server",        re.compile(r"\bfrom flask import|\bFlask\s*\("),                     "Flask HTTP server"),
    ("flask-cors",          re.compile(r"flask[_-]cors|\bCORS\s*\("),                            "CORS config for Flask"),
    ("json-persistence",    re.compile(r"json\.(dump|load)|chat_history\.json|history\.json"),   "JSON file persistence"),
    ("api-key-auth",        re.compile(r"X-API-KEY|API_KEY|VALID_API_KEYS|valid[_ ]?api[_ ]?keys", re.IGNORECASE), "API-key auth"),
    ("openai",              re.compile(r"\bimport openai|from openai\b|ChatCompletion|openai\.api_key"), "OpenAI integration"),
    ("anthropic",           re.compile(r"\bfrom anthropic|anthropic\.|claude[-_]api"),           "Anthropic / Claude integration"),
    ("react-native",        re.compile(r"react-native|react_native|@react-navigation|@react-native"), "React Native mobile client"),
    ("react-web",           re.compile(r"\bfrom ['\"]react['\"]|import React\b|useState|useEffect"), "React web client"),
    ("axios",               re.compile(r"\baxios\.|from ['\"]axios['\"]"),                        "HTTP client (axios)"),
    ("requests-py",         re.compile(r"\bimport requests\b|requests\.(get|post)"),             "HTTP client (requests, Python)"),
    ("google-drive",        re.compile(r"googleapiclient|google\.oauth2|drive\.files\(\)"),      "Google Drive sync"),
    ("polling-loop",        re.compile(r"while True:\s*\n.*time\.sleep", re.DOTALL),             "Polling loop client"),
    ("websocket",           re.compile(r"\bwebsockets?\b|socket\.io|WebSocket"),                 "WebSocket realtime channel"),
    ("sqlite",              re.compile(r"\bimport sqlite3|sqlite3\.connect"),                    "SQLite storage"),
    ("dart-flutter",        re.compile(r"import 'package:flutter|void main\(\)\s*\{\s*runApp"),   "Flutter/Dart app"),
    ("dotenv",              re.compile(r"from dotenv|dotenv\.|python-dotenv"),                   ".env config"),
    ("cron-schedule",       re.compile(r"\bschedule\.every|APScheduler|cron"),                    "Scheduled job / cron"),
    ("subprocess-cli",      re.compile(r"subprocess\.(run|Popen)"),                               "Subprocess / CLI shellout"),
    ("iteration-tracker",   re.compile(r"iteration|workflow_status|conversation_flow",            re.IGNORECASE), "Iteration / workflow_status tracking"),
    ("execution-pipeline",  re.compile(r"execution[_ ]pipeline|AI[_ ]Execution",                  re.IGNORECASE), "AI execution pipeline structure"),
    ("report-generation",   re.compile(r"generate[_ ]?report|business[_ ]report|weekly[_ ]report", re.IGNORECASE), "Report generation"),
]

# Idea heuristics: phrases in USER messages that signal vision/intent.
IDEA_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aspiration",     re.compile(r"\bi (want|need|wish|dream|hope)\b.{0,200}", re.IGNORECASE)),
    ("goal-framing",   re.compile(r"\b(goal|vision|purpose|intent)\s+(is|of)\b.{0,200}", re.IGNORECASE)),
    ("identity",       re.compile(r"\bi am\b.{0,100}|\bi'm\b.{0,100}", re.IGNORECASE)),
    ("pain-point",     re.compile(r"\b(problem|issue|struggle|stuck|cant|can't)\b.{0,150}", re.IGNORECASE)),
    ("why-question",   re.compile(r"^why\b.{0,200}", re.IGNORECASE | re.MULTILINE)),
]

# Decision heuristics: phrases in USER messages that signal chosen direction.
DECISION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("go-with",      re.compile(r"\b(let'?s go with|let'?s use|we'?ll use|use the|go with|lock in)\b.{0,150}", re.IGNORECASE)),
    ("yes-do",       re.compile(r"^(yes|yep|yeah|ok(ay)?|do it|proceed|sounds good)\b.{0,200}", re.IGNORECASE | re.MULTILINE)),
    ("final-answer", re.compile(r"\b(final answer|the answer is|decided|confirmed|approved)\b.{0,150}", re.IGNORECASE)),
    ("pick",         re.compile(r"\b(i('?ll| will)? (pick|choose|select)|going with)\b.{0,150}", re.IGNORECASE)),
]

STOP_SHORT = {"yes", "yep", "yeah", "ok", "okay", "no", "nope", "sure", "thanks", "thx", "hi", "hey"}


@dataclass
class Concept:
    id: str
    kind: str                       # "technical" | "idea" | "decision"
    label: str
    evidence_quote: str             # short quote, <=240 chars
    msg_range: tuple[int, int]      # [first_msg_idx, last_msg_idx]
    signal: str                     # which pattern matched (e.g. "flask-server")
    hit_count: int = 1              # how many times signal fired


def _msg_text(msg: dict) -> str:
    if "text" in msg:
        return str(msg["text"] or "")
    c = msg.get("content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in c)
    if isinstance(c, dict):
        return "\n".join(str(p) for p in (c.get("parts") or []))
    return str(c)


def _trim(s: str, n: int = 240) -> str:
    s = s.strip().replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[: n - 1] + "…"


def extract_technical(msgs: list[dict]) -> list[Concept]:
    """Scan assistant code blocks + user mentions for library/framework signatures."""
    hits: dict[str, dict] = {}
    full_text_per_msg = [_msg_text(m) for m in msgs]

    for idx, text in enumerate(full_text_per_msg):
        # Look inside code blocks AND the plain prose (both can mention libraries).
        for sig_id, pat, label in TECH_SIGNATURES:
            m = pat.search(text)
            if not m:
                continue
            rec = hits.setdefault(sig_id, {"label": label, "first": idx, "last": idx, "quote": None, "count": 0})
            rec["last"] = idx
            rec["count"] += 1
            if rec["quote"] is None:
                # Capture a 240-char window around the match.
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 80)
                rec["quote"] = _trim(text[start:end])

    out: list[Concept] = []
    for i, (sig_id, rec) in enumerate(sorted(hits.items(), key=lambda kv: kv[1]["first"])):
        out.append(Concept(
            id=f"T{i + 1}",
            kind="technical",
            label=rec["label"],
            evidence_quote=rec["quote"] or "",
            msg_range=(rec["first"], rec["last"]),
            signal=sig_id,
            hit_count=rec["count"],
        ))
    return out


def extract_ideas(msgs: list[dict]) -> list[Concept]:
    """Find aspirational / framing statements in USER messages."""
    out: list[Concept] = []
    seen_quotes: set[str] = set()
    counter = 1
    for idx, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        text = _msg_text(m).strip()
        if len(text) < 30 or text.lower() in STOP_SHORT:
            continue
        for sig_id, pat in IDEA_PATTERNS:
            match = pat.search(text)
            if not match:
                continue
            quote = _trim(match.group(0), 240)
            # Dedup by first 60 chars (avoids "I want a dog" × 12 copies).
            key = quote.lower()[:60]
            if key in seen_quotes:
                continue
            seen_quotes.add(key)
            out.append(Concept(
                id=f"I{counter}",
                kind="idea",
                label=_short_label(quote),
                evidence_quote=quote,
                msg_range=(idx, idx),
                signal=sig_id,
                hit_count=1,
            ))
            counter += 1
            if counter > 25:  # cap
                return out
    return out


def extract_decisions(msgs: list[dict]) -> list[Concept]:
    """Find user decision/approval moments."""
    out: list[Concept] = []
    counter = 1
    for idx, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        text = _msg_text(m).strip()
        if len(text) < 8 or text.lower() in STOP_SHORT:
            continue
        for sig_id, pat in DECISION_PATTERNS:
            match = pat.search(text)
            if not match:
                continue
            quote = _trim(match.group(0), 240)
            out.append(Concept(
                id=f"D{counter}",
                kind="decision",
                label=_short_label(quote),
                evidence_quote=quote,
                msg_range=(idx, idx),
                signal=sig_id,
                hit_count=1,
            ))
            counter += 1
            break  # one decision tag per message is enough
        if counter > 20:
            break
    return out


def _short_label(quote: str) -> str:
    """Strip quote to first ~60 chars for a scannable label."""
    q = quote.strip()
    q = re.sub(r"\s+", " ", q)
    if len(q) <= 60:
        return q
    cut = q[:60].rsplit(" ", 1)[0]
    return cut + "…"


def render_markdown(convo_id: int, title: str, concepts: list[Concept]) -> str:
    by_kind: dict[str, list[Concept]] = defaultdict(list)
    for c in concepts:
        by_kind[c.kind].append(c)

    lines = [
        f"# Concept Checklist — #{convo_id} {title}",
        "",
        f"- total concepts: {len(concepts)}",
        f"- technical: {len(by_kind['technical'])}",
        f"- ideas: {len(by_kind['idea'])}",
        f"- decisions: {len(by_kind['decision'])}",
        "",
        "> Tick boxes manually as you verify each concept appears in your built artifact.",
        "> Use `cycleboard verify <id> <path>` to auto-check technical concepts.",
        "",
    ]
    for kind, header in [("technical", "Technical"), ("idea", "Ideas / Intent"), ("decision", "Decisions")]:
        items = by_kind[kind]
        if not items:
            continue
        lines.append(f"## {header} ({len(items)})")
        lines.append("")
        for c in items:
            rng = f"msg {c.msg_range[0]}" if c.msg_range[0] == c.msg_range[1] else f"msg {c.msg_range[0]}–{c.msg_range[1]}"
            lines.append(f"- [ ] **{c.id} · {c.label}**  _{rng} · {c.hit_count}×_")
            lines.append(f"  > {c.evidence_quote}")
            lines.append("")
    return "\n".join(lines)


def parse(convo_id: int, out_json: Path | None = None, out_md: Path | None = None) -> tuple[Path, Path]:
    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    if convo_id < 0 or convo_id >= len(memory):
        raise SystemExit(f"convo_id {convo_id} out of range (0..{len(memory) - 1})")

    conv = memory[convo_id]
    title = conv.get("title") or f"convo_{convo_id}"
    msgs = conv.get("messages", [])

    concepts: list[Concept] = []
    concepts += extract_technical(msgs)
    concepts += extract_ideas(msgs)
    concepts += extract_decisions(msgs)

    if out_json is None:
        harvest_dirs = list((BASE / "harvest").glob(f"{convo_id}_*"))
        base_dir = harvest_dirs[0] if harvest_dirs else BASE
        out_json = base_dir / "concepts.json"
        out_md = out_md or base_dir / "concepts.md"
    if out_md is None:
        out_md = out_json.with_suffix(".md")

    payload = {
        "convo_id": convo_id,
        "title": title,
        "counts": {
            "total": len(concepts),
            "technical": sum(1 for c in concepts if c.kind == "technical"),
            "idea": sum(1 for c in concepts if c.kind == "idea"),
            "decision": sum(1 for c in concepts if c.kind == "decision"),
        },
        "concepts": [asdict(c) for c in concepts],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(convo_id, title, concepts), encoding="utf-8")
    return out_json, out_md


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("convo_id", type=int)
    p.add_argument("--out", type=Path, default=None, help="Output concepts.json path")
    args = p.parse_args()
    j, m = parse(args.convo_id, args.out)
    print(f"wrote {j} ({j.stat().st_size / 1024:.1f} KB)")
    print(f"wrote {m} ({m.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
