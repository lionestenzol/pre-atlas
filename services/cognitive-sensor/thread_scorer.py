"""
thread_scorer — emit per-thread signal cards without reading full conversations.

Signals (no LLM calls, all deterministic):
  - size:          total / user / assistant message counts
  - density:       messages per day bucket (activity curve)
  - code_blocks:   fenced ``` blocks + language tags + longest block
  - kwic_hits:     ±2 context hits for hedge / resolution / frustration words
                   (user-only slice, per removegpt.py)
  - final_text:    first 240 chars of last assistant + last user message
  - topics:        top 5 from results.db
  - classification:domain/outcome from conversation_classifications.json
  - cluster:       cluster_id + sibling count from atlas_clusters.json

Usage:
  python thread_scorer.py --convo 81
  python thread_scorer.py --cluster 121
  python thread_scorer.py --convos 81,87,78,360,255,316,317 --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import io
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.resolve()
MEMORY_PATH = BASE / "memory_db.json"
DB_PATH = BASE / "results.db"
CLUSTERS_PATH = BASE / "atlas_clusters.json"
CLASSIFICATIONS_PATH = BASE / "conversation_classifications.json"

# From removegpt.py + additions for code-work threads
HEDGE_WORDS = {"might", "could", "would", "maybe", "perhaps", "probably", "likely",
               "seems", "kind of", "sort of", "i think", "i feel"}
RESOLUTION_WORDS = {"works", "worked", "perfect", "done", "finished", "got it",
                    "final", "final version", "yes that's it", "fixed", "resolved"}
FRUSTRATION_WORDS = {"wait", "no wait", "that's wrong", "ugh", "stop", "annoying",
                     "tired", "not working", "broken", "again", "still"}

CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

# Reference dirs to scan blocks against. Add more as new lanes appear.
REPO_SCAN_DIRS = [
    BASE.parent.parent / "apps" / "code-converter",
]

_sig_noise = re.compile(r"\s+")


def _code_signature(body: str, head: int = 80) -> str:
    """Normalize code for fuzzy overlap: first `head` non-whitespace chars, lowered."""
    compressed = _sig_noise.sub(" ", body.strip().lower())
    return compressed[:head]


def _collect_reference_signatures() -> list[str]:
    """Load signatures from every scannable file in REPO_SCAN_DIRS + patterns.json entries."""
    sigs: list[str] = []
    for d in REPO_SCAN_DIRS:
        if not d.exists():
            continue
        # patterns.json entries if present
        pj = d / "patterns.json"
        if pj.exists():
            try:
                pats = json.loads(pj.read_text(encoding="utf-8"))
                pat_list = pats if isinstance(pats, list) else pats.get("patterns", [])
                for p in pat_list:
                    py = p.get("python", "") if isinstance(p, dict) else ""
                    if py:
                        sigs.append(_code_signature(py))
            except Exception:
                pass
        # any .py / .ts / .js / .html source files
        for ext in (".py", ".ts", ".tsx", ".js", ".html", ".sql"):
            for f in d.rglob(f"*{ext}"):
                if "__pycache__" in f.parts or "node_modules" in f.parts:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                # Sliding signature windows — every 200 chars, take 80-char signature
                for start in range(0, max(1, len(text) - 80), 200):
                    sigs.append(_code_signature(text[start : start + 300]))
    return [s for s in sigs if len(s) >= 20]


# Cached at module load
_REPO_SIGS: list[str] | None = None


def _get_repo_sigs() -> list[str]:
    global _REPO_SIGS
    if _REPO_SIGS is None:
        _REPO_SIGS = _collect_reference_signatures()
    return _REPO_SIGS


def scan_blocks_against_repo(blocks: list[tuple[str, str]]) -> dict[str, Any]:
    """Return counts + samples of blocks overlapping / not overlapping repo signatures."""
    repo_sigs = _get_repo_sigs()
    if not repo_sigs:
        return {"blocks_total": len(blocks), "blocks_overlapping": 0, "blocks_unique": len(blocks),
                "unique_samples": [(lang, body.split("\n", 1)[0][:90]) for lang, body in blocks[:5]],
                "repo_dirs_scanned": [str(d.name) for d in REPO_SCAN_DIRS if d.exists()]}

    overlapping = 0
    unique_samples: list[tuple[str, str]] = []
    for lang, body in blocks:
        sig = _code_signature(body)
        if len(sig) < 20:
            continue
        hit = any(sig[:40] in rs or rs[:40] in sig for rs in repo_sigs)
        if hit:
            overlapping += 1
        elif len(unique_samples) < 8:
            first_line = body.split("\n", 1)[0][:90]
            unique_samples.append((lang or "?", first_line))

    return {
        "blocks_total": len(blocks),
        "blocks_overlapping": overlapping,
        "blocks_unique": len(blocks) - overlapping,
        "unique_samples": unique_samples,
        "repo_dirs_scanned": [str(d.name) for d in REPO_SCAN_DIRS if d.exists()],
    }


def _fix_stdout() -> None:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_memory() -> list[dict]:
    return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))


def load_clusters() -> tuple[dict[str, int], dict[int, list[str]]]:
    """Return (convo_id→cluster, cluster→[convo_ids])."""
    d = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    assigns = {str(k): v for k, v in d.get("convo_cluster_assignments", {}).items()}
    by_cluster: dict[int, list[str]] = defaultdict(list)
    for cid, cluster in assigns.items():
        by_cluster[int(cluster)].append(cid)
    return assigns, dict(by_cluster)


def load_classifications() -> dict[str, dict]:
    if not CLASSIFICATIONS_PATH.exists():
        return {}
    d = json.loads(CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
    convos = d.get("conversations", d) if isinstance(d, dict) else d
    if isinstance(convos, list):
        return {str(c.get("convo_id", i)): c for i, c in enumerate(convos)}
    return {}


def get_topics(con: sqlite3.Connection, convo_id: str, limit: int = 5) -> list[tuple[str, int]]:
    rows = con.execute(
        "SELECT topic, weight FROM topics WHERE convo_id = ? ORDER BY weight DESC LIMIT ?",
        (convo_id, limit),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def get_date(con: sqlite3.Connection, convo_id: str) -> str | None:
    row = con.execute("SELECT date FROM convo_time WHERE convo_id = ?", (convo_id,)).fetchone()
    return row[0] if row else None


def get_title(con: sqlite3.Connection, convo_id: str) -> str | None:
    row = con.execute("SELECT title FROM convo_titles WHERE convo_id = ?", (convo_id,)).fetchone()
    return row[0] if row else None


def _msg_text(msg: dict) -> str:
    raw = msg.get("text", "")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        parts = raw.get("parts", [])
        if parts:
            return " ".join(str(p) for p in parts if isinstance(p, str))
    return ""


def score_thread(convo_id: str, memory: list[dict], con: sqlite3.Connection,
                 clusters: dict[str, int], by_cluster: dict[int, list[str]],
                 classifications: dict[str, dict]) -> dict[str, Any]:
    idx = int(convo_id)
    if idx < 0 or idx >= len(memory):
        return {"convo_id": convo_id, "error": "out_of_range"}

    conv = memory[idx]
    msgs = conv.get("messages", [])
    title = conv.get("title") or get_title(con, convo_id) or f"convo_{convo_id}"

    user_msgs = [m for m in msgs if m.get("role") == "user"]
    asst_msgs = [m for m in msgs if m.get("role") == "assistant"]

    user_text = " ".join(_msg_text(m) for m in user_msgs)
    all_text = " ".join(_msg_text(m) for m in msgs)

    # KWIC hits — user-only slice, word-level ±2 context
    user_words = user_text.lower().split()
    kwic: dict[str, list[list[str]]] = {"hedge": [], "resolution": [], "frustration": []}
    for bucket, wordset in (("hedge", HEDGE_WORDS),
                            ("resolution", RESOLUTION_WORDS),
                            ("frustration", FRUSTRATION_WORDS)):
        for i, w in enumerate(user_words):
            for target in wordset:
                if " " in target:
                    continue  # skip multi-word for simple tokenizer
                if w == target:
                    start = max(0, i - 2)
                    end = min(len(user_words), i + 3)
                    kwic[bucket].append(user_words[start:end])

    # Code blocks — assistant output, since that's where code lands
    asst_text = "\n".join(_msg_text(m) for m in asst_msgs)
    code_blocks = CODE_FENCE.findall(asst_text)
    langs = Counter(lang.lower() or "unspecified" for lang, _ in code_blocks)
    longest = max((body for _, body in code_blocks), key=len, default="")
    repo_scan = scan_blocks_against_repo(code_blocks)

    # Density — by message index (bucketed into deciles since we lack per-msg timestamps)
    buckets = 10
    n = len(msgs)
    density: list[int] = [0] * buckets
    if n > 0:
        for i in range(n):
            bucket = min(buckets - 1, (i * buckets) // n)
            density[bucket] += 1

    # Last user/assistant message (truncated)
    last_user = _msg_text(user_msgs[-1])[:240] if user_msgs else ""
    last_asst = _msg_text(asst_msgs[-1])[:240] if asst_msgs else ""
    first_user = _msg_text(user_msgs[0])[:240] if user_msgs else ""

    cluster_id = clusters.get(convo_id)
    sibling_count = len(by_cluster.get(int(cluster_id), [])) - 1 if cluster_id is not None else 0

    cls = classifications.get(convo_id, {})

    return {
        "convo_id": convo_id,
        "title": title,
        "date": get_date(con, convo_id),
        "size": {
            "total": len(msgs),
            "user": len(user_msgs),
            "assistant": len(asst_msgs),
            "user_chars": len(user_text),
            "total_chars": len(all_text),
        },
        "density": density,
        "code_blocks": {
            "count": len(code_blocks),
            "languages": dict(langs),
            "longest_lines": longest.count("\n") + 1 if longest else 0,
            "longest_preview": longest[:500],
        },
        "repo_scan": repo_scan,
        "kwic": {
            "hedge_hits": len(kwic["hedge"]),
            "resolution_hits": len(kwic["resolution"]),
            "frustration_hits": len(kwic["frustration"]),
            "examples": {k: [" ".join(c) for c in v[:3]] for k, v in kwic.items()},
        },
        "excerpts": {
            "first_user": first_user,
            "last_user": last_user,
            "last_assistant": last_asst,
        },
        "topics": [{"topic": t, "weight": w} for t, w in get_topics(con, convo_id)],
        "classification": {
            "domain": cls.get("domain", "unknown"),
            "outcome": cls.get("outcome", "unknown"),
            "trajectory": cls.get("emotional_trajectory", "unknown"),
        },
        "cluster": {
            "cluster_id": cluster_id,
            "sibling_count": sibling_count,
        },
    }


def render_card_text(card: dict[str, Any]) -> str:
    if "error" in card:
        return f"#{card['convo_id']}: ERROR {card['error']}"

    size = card["size"]
    cb = card["code_blocks"]
    kw = card["kwic"]
    ex = card["excerpts"]
    cl = card["classification"]
    ct = card["cluster"]
    topics = ", ".join(f"{t['topic']}({t['weight']})" for t in card["topics"])

    # density sparkline
    d = card["density"]
    mx = max(d) if d else 1
    chars = " ▁▂▃▄▅▆▇█"
    spark = "".join(chars[min(8, (v * 8 // mx) if mx else 0)] for v in d)

    lines = [
        "=" * 70,
        f"#{card['convo_id']} {card['title']} ({card['date'] or '?'})",
        "-" * 70,
        f"size:        {size['total']} msgs ({size['user']} user / {size['assistant']} asst)",
        f"density:     {spark}  ({size['total_chars']:,} chars total)",
        f"code:        {cb['count']} blocks, langs={cb['languages']}, longest={cb['longest_lines']}L",
        f"repo-scan:   overlap={card['repo_scan']['blocks_overlapping']}/{card['repo_scan']['blocks_total']} (unique={card['repo_scan']['blocks_unique']})",
        f"kwic:        hedge={kw['hedge_hits']} resolution={kw['resolution_hits']} frustration={kw['frustration_hits']}",
        f"class:       domain={cl['domain']} outcome={cl['outcome']} trajectory={cl['trajectory']}",
        f"cluster:     #{ct['cluster_id']} ({ct['sibling_count']} siblings)",
        f"topics:      {topics}",
        "",
        f"first user:  {ex['first_user'][:140]}",
        f"last user:   {ex['last_user'][:140]}",
        f"last asst:   {ex['last_assistant'][:140]}",
    ]
    if kw["examples"]["frustration"]:
        lines.append(f"frustration: {kw['examples']['frustration']}")
    if kw["examples"]["resolution"]:
        lines.append(f"resolution:  {kw['examples']['resolution']}")
    return "\n".join(lines)


def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--convo", help="single convo_id")
    ap.add_argument("--convos", help="comma-separated convo_ids")
    ap.add_argument("--cluster", type=int, help="cluster_id — score all members")
    ap.add_argument("--json", help="write full scored output to this path")
    ap.add_argument("--quiet", action="store_true", help="suppress per-card text")
    args = ap.parse_args()

    memory = load_memory()
    clusters, by_cluster = load_clusters()
    classifications = load_classifications()
    con = sqlite3.connect(str(DB_PATH))

    ids: list[str]
    if args.convo:
        ids = [args.convo]
    elif args.convos:
        ids = [x.strip() for x in args.convos.split(",") if x.strip()]
    elif args.cluster is not None:
        ids = sorted(by_cluster.get(args.cluster, []), key=lambda x: int(x))
        if not ids:
            print(f"cluster {args.cluster}: no members", file=sys.stderr)
            return 1
    else:
        ap.error("one of --convo, --convos, --cluster is required")
        return 2

    cards = [score_thread(cid, memory, con, clusters, by_cluster, classifications) for cid in ids]

    if not args.quiet:
        for c in cards:
            print(render_card_text(c))
            print()
    print(f"\nscored {len(cards)} thread(s)", file=sys.stderr)

    if args.json:
        out = {"generated_at": datetime.now().isoformat(), "count": len(cards), "cards": cards}
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
