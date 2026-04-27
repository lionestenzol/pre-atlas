"""Dump a full ChatGPT conversation from memory_db.json to markdown.

The harvester extracts code blocks, quotes, and summaries, but never the
full transcript. This script pulls the raw back-and-forth so you can read
the whole thread.

Usage:
    python dump_conversation.py 487
    python dump_conversation.py 487 --out my_thread.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.resolve()
MEMORY_PATH = BASE / "memory_db.json"


def _msg_text(msg: dict) -> str:
    """Extract text content from a message regardless of format."""
    if "text" in msg:
        return str(msg["text"] or "")
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
        return "\n".join(parts)
    if isinstance(content, dict):
        parts = content.get("parts") or []
        return "\n".join(str(p) for p in parts if p)
    return str(content)


def dump(convo_id: int, out: Path | None) -> Path:
    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    if convo_id < 0 or convo_id >= len(memory):
        raise SystemExit(f"convo_id {convo_id} out of range (0..{len(memory) - 1})")

    conv = memory[convo_id]
    title = conv.get("title") or f"convo_{convo_id}"
    msgs = conv.get("messages", [])

    lines: list[str] = [
        f"# Conversation #{convo_id}: {title}",
        "",
        f"- messages: {len(msgs)}",
        f"- user: {sum(1 for m in msgs if m.get('role') == 'user')}",
        f"- assistant: {sum(1 for m in msgs if m.get('role') == 'assistant')}",
        "",
        "---",
        "",
    ]

    for i, m in enumerate(msgs):
        role = m.get("role", "?").upper()
        text = _msg_text(m).strip()
        if not text:
            continue
        lines.append(f"## [{i}] {role}")
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("---")
        lines.append("")

    if out is None:
        harvest_dirs = list((BASE / "harvest").glob(f"{convo_id}_*"))
        if harvest_dirs:
            out = harvest_dirs[0] / "conversation.md"
        else:
            out = BASE / f"conversation_{convo_id}.md"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("convo_id", type=int)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    path = dump(args.convo_id, args.out)
    size_kb = path.stat().st_size / 1024
    print(f"wrote {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
