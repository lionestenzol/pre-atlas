"""
export_markdown — per-convo round-trippable Markdown files.

Port of chatgpt_json_to_markdown_3.py (Jan 2025 toolchain), adapted to:
  - Read from memory_db.json (1397 convos) instead of the raw OpenAI export
  - Use the 6-domain taxonomy from conversation_classifications.json
  - Write into services/cognitive-sensor/markdown_output/<domain>/<slug>.md
  - Embed HTML metadata comments so md→json reconstruction is possible

Usage:
  python export_markdown.py --convo 81
  python export_markdown.py --convos 81,87,78,360,255,316,317
  python export_markdown.py --cluster 121
  python export_markdown.py --all                 # all 1397
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).parent.resolve()
MEMORY_PATH = BASE / "memory_db.json"
CLASSIFICATIONS_PATH = BASE / "conversation_classifications.json"
CLUSTERS_PATH = BASE / "atlas_clusters.json"
OUT_ROOT = BASE / "markdown_output"

ICONS = {"user": "🧑", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(s: str, max_len: int = 60) -> str:
    s = _slug_re.sub("-", (s or "untitled").lower()).strip("-")
    return (s[:max_len] or "untitled").rstrip("-")


def escape_md(text: str) -> str:
    """Escape characters that would break blockquote rendering."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _msg_text(msg: dict) -> str:
    raw = msg.get("text", "")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        parts = raw.get("parts", [])
        if parts:
            return " ".join(str(p) for p in parts if isinstance(p, str))
    return ""


def render_md(convo_id: str, conv: dict, classification: dict,
              cluster_id: int | None) -> str:
    title = conv.get("title", f"convo_{convo_id}")
    msgs = conv.get("messages", [])
    meta = {
        "convo_id": convo_id,
        "title": title,
        "message_count": len(msgs),
        "domain": classification.get("domain", "unknown"),
        "outcome": classification.get("outcome", "unknown"),
        "trajectory": classification.get("emotional_trajectory", "unknown"),
        "cluster_id": cluster_id,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }

    lines: list[str] = [
        f"<!-- metadata: {json.dumps(meta, ensure_ascii=False)} -->",
        "",
        f"# {title}",
        "",
        f"**convo_id:** `{convo_id}` · **domain:** `{meta['domain']}` "
        f"· **outcome:** `{meta['outcome']}` · **messages:** {meta['message_count']}",
        "",
        "---",
        "",
    ]

    for i, msg in enumerate(msgs):
        role = msg.get("role", "unknown")
        text = _msg_text(msg)
        if not text.strip() and role == "system":
            continue  # skip empty system prompts
        icon = ICONS.get(role, "•")
        node = {"idx": i, "role": role, "chars": len(text)}
        lines.append(f"<!-- node: {json.dumps(node)} -->")
        lines.append(f"### {icon} {role}")
        lines.append("")
        # render as blockquote, escaping
        for block_line in escape_md(text).split("\n"):
            lines.append(f"> {block_line}" if block_line else ">")
        lines.append("")

    return "\n".join(lines)


def parse_md(md: str) -> dict[str, Any]:
    """Reverse of render_md — reconstructs {metadata, messages}."""
    meta_match = re.search(r"<!-- metadata: (.+?) -->", md)
    metadata = json.loads(meta_match.group(1)) if meta_match else {}
    messages: list[dict] = []
    node_re = re.compile(r"<!-- node: (.+?) -->\n### .+? (\w+)\n\n((?:>.*\n?)*)", re.MULTILINE)
    for m in node_re.finditer(md):
        _node = json.loads(m.group(1))
        role = m.group(2)
        body = m.group(3)
        text = "\n".join(line[2:] if line.startswith("> ") else line[1:] if line.startswith(">") else line
                         for line in body.rstrip("\n").split("\n"))
        messages.append({"role": role, "text": text})
    return {"metadata": metadata, "messages": messages}


def load_memory() -> list[dict]:
    return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))


def load_classifications() -> dict[str, dict]:
    if not CLASSIFICATIONS_PATH.exists():
        return {}
    d = json.loads(CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
    convos = d.get("conversations", d) if isinstance(d, dict) else d
    if isinstance(convos, list):
        return {str(c.get("convo_id", i)): c for i, c in enumerate(convos)}
    return {}


def load_clusters() -> dict[str, int]:
    if not CLUSTERS_PATH.exists():
        return {}
    d = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    return {str(k): v for k, v in d.get("convo_cluster_assignments", {}).items()}


def export_one(convo_id: str, memory: list[dict], classifications: dict,
               clusters: dict) -> Path | None:
    idx = int(convo_id)
    if idx < 0 or idx >= len(memory):
        print(f"#{convo_id}: out of range", file=sys.stderr)
        return None

    conv = memory[idx]
    cls = classifications.get(convo_id, {})
    cluster_id = clusters.get(convo_id)
    domain = cls.get("domain", "unknown") or "unknown"

    out_dir = OUT_ROOT / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(conv.get("title", ""))
    out_path = out_dir / f"{convo_id}_{slug}.md"

    md = render_md(convo_id, conv, cls, cluster_id)
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--convo", help="single convo_id")
    ap.add_argument("--convos", help="comma-separated convo_ids")
    ap.add_argument("--cluster", type=int, help="all members of a cluster")
    ap.add_argument("--all", action="store_true", help="all 1397 convos (slow)")
    ap.add_argument("--verify-roundtrip", action="store_true",
                    help="parse back the written .md and compare message count")
    args = ap.parse_args()

    memory = load_memory()
    classifications = load_classifications()
    clusters = load_clusters()

    ids: list[str]
    if args.convo:
        ids = [args.convo]
    elif args.convos:
        ids = [x.strip() for x in args.convos.split(",") if x.strip()]
    elif args.cluster is not None:
        ids = sorted([k for k, v in clusters.items() if v == args.cluster], key=int)
        if not ids:
            print(f"cluster {args.cluster}: no members", file=sys.stderr)
            return 1
    elif args.all:
        ids = [str(i) for i in range(len(memory))]
    else:
        ap.error("one of --convo, --convos, --cluster, --all is required")
        return 2

    written = 0
    for cid in ids:
        path = export_one(cid, memory, classifications, clusters)
        if path:
            written += 1
            if args.verify_roundtrip:
                parsed = parse_md(path.read_text(encoding="utf-8"))
                orig = memory[int(cid)]["messages"]
                # Expected excludes empty system messages (which export_one skips)
                expected = sum(1 for m in orig if not (m.get("role") == "system" and not _msg_text(m).strip()))
                got = len(parsed["messages"])
                flag = "OK" if got == expected else "MISMATCH"
                print(f"  {flag}: #{cid} wrote {got}/{expected} msgs -> {path.relative_to(BASE)}")
            else:
                print(f"  wrote {path.relative_to(BASE)}")

    print(f"\nexported {written}/{len(ids)} convos to {OUT_ROOT.relative_to(BASE)}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
