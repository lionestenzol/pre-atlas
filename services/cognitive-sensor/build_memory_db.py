"""build_memory_db.py — rebuild memory_db.json from one or more ChatGPT export bundles.

The cognitive-sensor pipeline reads memory_db.json. Until now there was no
checked-in builder, so the file was a frozen Jan-2026 snapshot covering only
Aug 2024 → March 2025. This script regenerates it from the live exports,
dedupes by UUID across multiple bundles, recovers conversations that were
deleted from later exports, and emits both:

    memory_db.json      — normalized [{title, messages: [{role, text}, ...]}]
    conversations.json  — raw merged export (for init_convo_time.py)

Both are sorted newest-first (matching the existing memory_db.json convention).

Usage:
    python build_memory_db.py [--sources path1 path2 ...] [--no-backup]
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.resolve()

# All known ChatGPT export bundles on this machine (most-recent first).
# The newer export wins on UUID collisions; older exports contribute
# only conversations that the newer export doesn't have (= deleted-recovered).
DEFAULT_SOURCES = [
    # Recent export (May 2026) — split into 66 files
    Path(r"C:\Users\bruke\OneDrive\Desktop\claude-mining\source-chatgpt"),
    # March 2025 snapshot — single file (the original source of memory_db.json)
    Path(r"C:\Users\bruke\Legacy\8423c2598d1850b1b07b3dea7436ffc88813b8ea376e3ce3af159a55b612a31b-2025-03-12-11-15-28-022f7253a95d4f94b847356d247b4a8a\conversations.json"),
    # Jan 2025 snapshot — single file
    Path(r"C:\Users\bruke\OneDrive\Desktop\8423c2598d1850b1b07b3dea7436ffc88813b8ea376e3ce3af159a55b612a31b-2025-01-29-02-18-30-021606fe377447108c7c3ee4275bf457\conversations.json"),
    # Earliest known export — Sep 2024 snapshot
    Path(r"C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\conversations.json"),
]


def _load_export(path: Path) -> list[dict[str, Any]]:
    """Load conversations from one path — either a single .json or a dir of conversations-*.json."""
    if not path.exists():
        return []
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # Directory: collect every conversations-*.json
    merged: list[dict[str, Any]] = []
    for fp in sorted(path.glob("conversations-*.json")):
        try:
            with open(fp, encoding="utf-8") as f:
                merged.extend(json.load(f))
        except Exception as e:
            print(f"  WARN skip {fp.name}: {e}")
    return merged


def _walk_mapping(entry: dict[str, Any]) -> list[dict[str, str]]:
    """Turn ChatGPT's tree-of-nodes 'mapping' into chronological [{role, text}, ...]."""
    mapping = entry.get("mapping") or {}
    messages: list[tuple[float, dict[str, str]]] = []
    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue
        role = (msg.get("author") or {}).get("role")
        if not role:
            continue
        content = msg.get("content") or {}
        parts = content.get("parts") or []
        text = "\n".join(p for p in parts if isinstance(p, str)).strip()
        if not text:
            continue
        ts = msg.get("create_time") or 0.0
        messages.append((ts, {"role": role, "text": text}))
    messages.sort(key=lambda m: m[0])
    return [m[1] for m in messages]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", nargs="+", type=Path, default=DEFAULT_SOURCES,
                   help="Export bundles (dirs or single .json files), newest-first priority")
    p.add_argument("--out-memory", type=Path, default=BASE / "memory_db.json")
    p.add_argument("--out-raw", type=Path, default=BASE / "conversations.json")
    p.add_argument("--no-backup", action="store_true", help="Skip backing up existing memory_db.json")
    args = p.parse_args()

    # 1. Backup existing memory_db.json
    if args.out_memory.exists() and not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.out_memory.with_suffix(f".{stamp}.bak.json")
        print(f"Backing up existing {args.out_memory.name} -> {backup.name}")
        shutil.copy2(args.out_memory, backup)

    # 2. Merge sources — newer wins on UUID collisions
    by_uuid: dict[str, dict[str, Any]] = {}
    source_provenance: dict[str, str] = {}

    for src_idx, src in enumerate(args.sources):
        entries = _load_export(src)
        label = src.name if src.is_dir() else src.parent.name + "/" + src.name
        print(f"\n[source {src_idx}] {label}: {len(entries):,} entries", flush=True)
        added = 0
        skipped = 0
        for e in entries:
            uid = e.get("id") or e.get("conversation_id")
            if not uid:
                continue
            if uid in by_uuid:
                skipped += 1
                continue  # newer source already won
            by_uuid[uid] = e
            source_provenance[uid] = label
            added += 1
        kind = "primary" if src_idx == 0 else "recovered from older source"
        print(f"  -> {added:,} {kind}, {skipped:,} already covered by newer source", flush=True)

    print(f"\nTotal unique conversations across all sources: {len(by_uuid):,}")

    # 3. Sort newest-first (by create_time) — matches existing memory_db.json convention
    sorted_entries = sorted(
        by_uuid.values(),
        key=lambda e: -(e.get("create_time") or 0.0),
    )

    # 4. Build normalized memory_db.json (just title + messages)
    print("\nWalking mapping graphs (extracting ordered messages)...")
    t0 = time.time()
    memory_db: list[dict[str, Any]] = []
    for i, entry in enumerate(sorted_entries):
        if i and i % 1000 == 0:
            print(f"  {i:,}/{len(sorted_entries):,} ({(time.time()-t0):.0f}s)")
        msgs = _walk_mapping(entry)
        memory_db.append({
            "title": entry.get("title") or "(untitled)",
            "messages": msgs,
        })

    # 5. Write both outputs
    print(f"\nWriting {args.out_memory.name} ...")
    with open(args.out_memory, "w", encoding="utf-8") as f:
        json.dump(memory_db, f, ensure_ascii=False)
    print(f"  {args.out_memory.stat().st_size / 1024 / 1024:.1f} MB, {len(memory_db):,} convos")

    print(f"\nWriting {args.out_raw.name} (for init_convo_time.py) ...")
    with open(args.out_raw, "w", encoding="utf-8") as f:
        json.dump(sorted_entries, f, ensure_ascii=False)
    print(f"  {args.out_raw.stat().st_size / 1024 / 1024:.1f} MB")

    # 6. Stats summary
    total_msgs = sum(len(c["messages"]) for c in memory_db)
    ts = [e.get("create_time") for e in sorted_entries if e.get("create_time")]
    if ts:
        print(f"\nDate range: {time.strftime('%Y-%m-%d', time.localtime(min(ts)))}"
              f" -> {time.strftime('%Y-%m-%d', time.localtime(max(ts)))}")
    print(f"Total messages across all conversations: {total_msgs:,}")
    print(f"\nDone. Next steps:")
    print(f"  python init_titles.py")
    print(f"  python init_convo_time.py")
    print(f"  python init_results_db.py")
    print(f"  python init_topics.py")
    print(f"  python init_message_embeddings.py   # SLOW (~1 hr for full re-embed)")
    print(f"  python build_cognitive_atlas.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
