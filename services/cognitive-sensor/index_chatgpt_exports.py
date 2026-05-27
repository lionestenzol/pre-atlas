"""index_chatgpt_exports.py — one-shot scanner over the ChatGPT JSON export bundle.

Builds chatgpt_index.json:
    [
      {"title": "...", "uuid": "...", "create_time": 1700000000.0,
       "date": "2025-02-27", "file": "conversations-011.json", "position": 42,
       "nodes": 249},
      ...
    ]

Run once after a fresh export. atlas_query.py's `text <convo_id>` command
uses this to jump directly to the right conversation without rescanning
~800 MB on every call.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

DEFAULT_EXPORT = Path(r"C:\Users\bruke\OneDrive\Desktop\claude-mining\source-chatgpt")
DEFAULT_OUT = Path(__file__).parent / "chatgpt_index.json"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    if not args.export_dir.exists():
        raise SystemExit(f"missing: {args.export_dir}")

    files = sorted(args.export_dir.glob("conversations-*.json"))
    print(f"Scanning {len(files)} export files in {args.export_dir} ...")

    index: list[dict] = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                arr = json.load(f)
        except Exception as e:
            print(f"  WARN skip {fp.name}: {e}")
            continue
        for i, entry in enumerate(arr):
            ct = entry.get("create_time")
            date = time.strftime("%Y-%m-%d", time.localtime(ct)) if ct else None
            index.append({
                "title": entry.get("title") or "",
                "uuid": entry.get("id") or entry.get("conversation_id"),
                "create_time": ct,
                "date": date,
                "file": fp.name,
                "position": i,
                "nodes": len(entry.get("mapping") or {}),
            })
        print(f"  {fp.name}: {len(arr)} convos  (index now {len(index)})")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    print(f"\nWrote {args.out.name}: {len(index):,} conversations indexed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
