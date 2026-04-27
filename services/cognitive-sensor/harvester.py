"""
harvester — extract value from a conversation before any verdict is applied.

Every verdict (except REVIEW) triggers extraction. Writes to:
  harvest/<convo_id>/
    ├─ code_blocks.md     ← all unique (not-in-repo) blocks
    ├─ key_quotes.md      ← context around resolution + frustration words
    ├─ final_output.md    ← last user msg + last assistant msg
    ├─ summary.md         ← stats + topics + verdict
    └─ manifest.json      ← machine-readable index

Usage:
  python harvester.py --convo 81 --verdict MINE
  python harvester.py --from-decisions thread_decisions.json
  python harvester.py --convo 360                 # verdict defaults to "pending"
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from thread_scorer import (
    BASE, DB_PATH, CODE_FENCE,
    HEDGE_WORDS, RESOLUTION_WORDS, FRUSTRATION_WORDS,
    load_memory, load_clusters, load_classifications,
    score_thread, scan_blocks_against_repo, _code_signature,
    _get_repo_sigs, _fix_stdout, _msg_text
)

HARVEST_ROOT = BASE / "harvest"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _kwic_context_from_messages(messages: list[dict], wordset: set[str],
                                role: str | None = None, window: int = 8) -> list[dict]:
    """Return all ±window-word contexts where wordset hits. Role='user' to filter."""
    out: list[dict] = []
    for idx, msg in enumerate(messages):
        if role and msg.get("role") != role:
            continue
        text = _msg_text(msg)
        if not text:
            continue
        words = text.split()
        lowered = [w.lower() for w in words]
        for i, w in enumerate(lowered):
            if w in wordset:
                start = max(0, i - window)
                end = min(len(words), i + window + 1)
                context = " ".join(words[start:end])
                out.append({"msg_idx": idx, "role": msg.get("role"), "hit": w, "context": context})
    return out


def _unique_blocks(blocks: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split blocks into (unique-vs-repo, in-repo)."""
    repo_sigs = _get_repo_sigs()
    unique: list[tuple[str, str]] = []
    in_repo: list[tuple[str, str]] = []
    for lang, body in blocks:
        sig = _code_signature(body)
        if len(sig) < 20:
            unique.append((lang, body))
            continue
        hit = any(sig[:40] in rs or rs[:40] in sig for rs in repo_sigs) if repo_sigs else False
        (in_repo if hit else unique).append((lang, body))
    return unique, in_repo


def harvest_one(convo_id: str, verdict: str, memory: list[dict],
                con: sqlite3.Connection, clusters, by_cluster,
                classifications) -> dict:
    idx = int(convo_id)
    if idx < 0 or idx >= len(memory):
        return {"convo_id": convo_id, "error": "out_of_range"}

    conv = memory[idx]
    title = conv.get("title") or f"convo_{convo_id}"
    msgs = conv.get("messages", [])
    asst = [m for m in msgs if m.get("role") == "assistant"]
    user = [m for m in msgs if m.get("role") == "user"]

    asst_text = "\n".join(_msg_text(m) for m in asst)
    all_blocks = CODE_FENCE.findall(asst_text)
    unique_blocks, repo_blocks = _unique_blocks(all_blocks)

    resolution_hits = _kwic_context_from_messages(msgs, RESOLUTION_WORDS, role="user", window=10)
    frustration_hits = _kwic_context_from_messages(msgs, FRUSTRATION_WORDS, role="user", window=10)

    last_user = _msg_text(user[-1]) if user else ""
    last_asst = _msg_text(asst[-1]) if asst else ""
    first_user = _msg_text(user[0]) if user else ""

    card = score_thread(convo_id, memory, con, clusters, by_cluster, classifications)

    out_dir = HARVEST_ROOT / f"{convo_id}_{_slug(title)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. code_blocks.md
    cb_lines = [
        f"# Code Blocks — #{convo_id} {title}",
        "",
        f"- convo_id: `{convo_id}`",
        f"- total blocks: {len(all_blocks)}",
        f"- unique (not in repo): {len(unique_blocks)}",
        f"- already in repo: {len(repo_blocks)}",
        f"- date: {card.get('date')}",
        "",
        "## Unique blocks (worth harvesting)",
        "",
    ]
    for i, (lang, body) in enumerate(unique_blocks, 1):
        cb_lines.append(f"### Block {i} ({lang or 'unspecified'}, {body.count(chr(10))+1} lines)")
        cb_lines.append("")
        cb_lines.append(f"```{lang}")
        cb_lines.append(body.rstrip("\n"))
        cb_lines.append("```")
        cb_lines.append("")
    if repo_blocks:
        cb_lines.append("## Blocks already in repo (skipped detail)")
        cb_lines.append("")
        for lang, body in repo_blocks:
            first = body.split("\n", 1)[0][:120]
            cb_lines.append(f"- ({lang}) {first}")
    _write(out_dir / "code_blocks.md", "\n".join(cb_lines))

    # 2. key_quotes.md
    kq_lines = [
        f"# Key Quotes — #{convo_id} {title}",
        "",
        f"## Resolution hits ({len(resolution_hits)})",
        "",
    ]
    for h in resolution_hits[:50]:
        kq_lines.append(f"- **{h['hit']}** · `msg {h['msg_idx']}` · {h['context']}")
    kq_lines.append("")
    kq_lines.append(f"## Frustration hits ({len(frustration_hits)})")
    kq_lines.append("")
    for h in frustration_hits[:50]:
        kq_lines.append(f"- **{h['hit']}** · `msg {h['msg_idx']}` · {h['context']}")
    _write(out_dir / "key_quotes.md", "\n".join(kq_lines))

    # 3. final_output.md
    fo_lines = [
        f"# Final Output — #{convo_id} {title}",
        "",
        "## First user message",
        "",
        "> " + first_user.replace("\n", "\n> ")[:2000],
        "",
        "## Last user message",
        "",
        "> " + last_user.replace("\n", "\n> ")[:2000],
        "",
        "## Last assistant message",
        "",
        last_asst[:5000],
    ]
    _write(out_dir / "final_output.md", "\n".join(fo_lines))

    # 4. summary.md
    topics = card.get("topics", [])
    cb = card["code_blocks"]
    rs = card["repo_scan"]
    kw = card["kwic"]
    ct = card["cluster"]
    cl = card["classification"]

    sm_lines = [
        f"# Summary — #{convo_id} {title}",
        "",
        f"**verdict:** `{verdict}`",
        f"**harvested_at:** {datetime.now().isoformat(timespec='seconds')}",
        f"**date:** {card.get('date')}",
        "",
        "## Size",
        "",
        f"- total msgs: {card['size']['total']}  (user: {card['size']['user']} · asst: {card['size']['assistant']})",
        f"- total chars: {card['size']['total_chars']:,}",
        "",
        "## Code",
        "",
        f"- blocks: {cb['count']}  ({rs['blocks_unique']} unique, {rs['blocks_overlapping']} in repo)",
        f"- languages: {cb['languages']}",
        f"- longest: {cb['longest_lines']} lines",
        "",
        "## Signals",
        "",
        f"- hedge: {kw['hedge_hits']}",
        f"- resolution: {kw['resolution_hits']}",
        f"- frustration: {kw['frustration_hits']}",
        "",
        "## Context",
        "",
        f"- cluster: #{ct['cluster_id']} ({ct['sibling_count']} siblings)",
        f"- classification: domain={cl['domain']} · outcome={cl['outcome']} · trajectory={cl['trajectory']}",
        f"- topics: " + ", ".join(f"{t['topic']}({t['weight']})" for t in topics),
    ]
    _write(out_dir / "summary.md", "\n".join(sm_lines))

    # 5. manifest.json — machine-readable
    # Preserve lifecycle state across re-harvests (don't clobber BUILDING → HARVESTED).
    existing_manifest_path = out_dir / "manifest.json"
    existing: dict = {}
    if existing_manifest_path.exists():
        try:
            existing = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    manifest = {
        "convo_id": convo_id,
        "title": title,
        "verdict": verdict,
        "status": existing.get("status", "HARVESTED"),
        "harvested_at": datetime.now().isoformat(timespec="seconds"),
        "harvest_dir": str(out_dir.relative_to(BASE)),
        "stats": {
            "total_blocks": cb["count"],
            "unique_blocks": rs["blocks_unique"],
            "in_repo_blocks": rs["blocks_overlapping"],
            "resolution_hits": kw["resolution_hits"],
            "frustration_hits": kw["frustration_hits"],
            "total_messages": card["size"]["total"],
            "total_chars": card["size"]["total_chars"],
        },
        "outputs": {
            "code_blocks": "code_blocks.md",
            "key_quotes": "key_quotes.md",
            "final_output": "final_output.md",
            "summary": "summary.md",
        },
    }
    # Preserve any lifecycle-related fields written by later commands.
    for preserved in (
        "artifact_path",
        "building_started_at",
        "reviewed_at",
        "coverage_score",
        "done_at",
        "status_history",
    ):
        if preserved in existing:
            manifest[preserved] = existing[preserved]
    _write(out_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return manifest


_slug_re = re.compile(r"[^a-z0-9]+")


def _slug(s: str, max_len: int = 45) -> str:
    s = _slug_re.sub("-", (s or "untitled").lower()).strip("-")
    return (s[:max_len] or "untitled").rstrip("-")


def run_from_decisions(decisions_path: Path, memory, con, clusters, by_cluster,
                       classifications) -> list[dict]:
    data = json.loads(decisions_path.read_text(encoding="utf-8"))
    results: list[dict] = []
    for row in data.get("decisions", []):
        cid = str(row.get("convo_id", ""))
        verdict = row.get("verdict", "pending")
        if not cid:
            continue
        if verdict == "REVIEW":
            print(f"  skip #{cid} (REVIEW — no harvest)", file=sys.stderr)
            continue
        m = harvest_one(cid, verdict, memory, con, clusters, by_cluster, classifications)
        if "error" in m:
            print(f"  ERROR #{cid}: {m['error']}", file=sys.stderr)
        else:
            st = m["stats"]
            print(f"  harvested #{cid:>4} [{verdict:<8}] "
                  f"blocks={st['unique_blocks']:>4}/{st['total_blocks']:<4} "
                  f"res={st['resolution_hits']:<3} frust={st['frustration_hits']:<3} "
                  f"-> {m['harvest_dir']}", file=sys.stderr)
        results.append(m)
    return results


def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--convo", help="single convo_id")
    ap.add_argument("--verdict", default="pending",
                    choices=["MINE", "KEEP", "CLOSE", "ARCHIVE", "REVIEW", "pending"])
    ap.add_argument("--from-decisions", help="path to thread_decisions.json")
    args = ap.parse_args()

    memory = load_memory()
    clusters, by_cluster = load_clusters()
    classifications = load_classifications()
    con = sqlite3.connect(str(DB_PATH))

    if args.from_decisions:
        path = Path(args.from_decisions)
        if not path.is_absolute():
            path = BASE / path
        if not path.exists():
            print(f"{path}: not found", file=sys.stderr)
            return 1
        results = run_from_decisions(path, memory, con, clusters, by_cluster, classifications)
        print(f"\nharvested {len(results)} threads", file=sys.stderr)
    elif args.convo:
        m = harvest_one(args.convo, args.verdict, memory, con, clusters, by_cluster, classifications)
        if "error" in m:
            print(f"ERROR: {m['error']}", file=sys.stderr)
            return 1
        print(json.dumps(m, indent=2, ensure_ascii=False))
    else:
        ap.error("need --convo or --from-decisions")
        return 2

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
