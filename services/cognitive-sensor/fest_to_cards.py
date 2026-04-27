"""Convert festival tasks into thread cards.

Walks the WSL fest tree (/root/festival-project/festivals) and emits one
thread card per open task so the universal triage inbox surfaces planned
work alongside conversational threads (source:"conv") and filesystem
findings (source:"fs").

Cards carry source:"fest" plus festival_id + phase + sequence + task_num
so a future `fest_actor.py` can close the loop back to `fest complete`.

Run as Phase 1.8 of run_daily.py, after es_to_cards.py.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
CARDS_PATH = BASE / "thread_cards.json"

DEFAULT_LIFECYCLES = ("active", "ready")
GATE_SLUGS = frozenset({"testing", "review", "iterate", "fest_commit", "quality"})

# Walker runs inside WSL (Ubuntu has python3 by default) so we get a
# structured JSON dump in one subprocess call instead of N file reads
# over a slow WSL UNC mount.
_WSL_WALKER = r'''
import json, re, sys
from pathlib import Path

FEST_ROOT = Path("/root/festival-project/festivals")
TASK_RE = re.compile(r"^(\d{2})_([a-z0-9_]+)\.md$")
PHASE_RE = re.compile(r"^(\d{3})_[A-Z0-9_]+$")
SEQ_RE = re.compile(r"^(\d{2})_[a-z0-9_]+$")

def parse_task(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"title": path.stem, "objective": ""}
    title = path.stem
    objective = ""
    lines = text.splitlines()
    for line in lines[:5]:
        s = line.strip()
        if s.startswith("# Task:"):
            title = s.removeprefix("# Task:").strip() or title
            break
        if s.startswith("# "):
            title = s.removeprefix("# ").strip() or title
            break
    in_obj = False
    for line in lines:
        s = line.strip()
        if s.startswith("## Objective"):
            in_obj = True
            continue
        if in_obj:
            if s.startswith("##"):
                break
            if s:
                objective = s
                break
    return {"title": title, "objective": objective}

def walk(lifecycles):
    out = []
    for lifecycle in lifecycles:
        lc_root = FEST_ROOT / lifecycle
        if not lc_root.is_dir():
            continue
        for fest_dir in sorted(lc_root.iterdir()):
            if not fest_dir.is_dir() or fest_dir.name.startswith("."):
                continue
            fest_name = fest_dir.name
            fest_id = fest_name.rsplit("-", 1)[-1] if "-" in fest_name else fest_name
            for phase_dir in sorted(fest_dir.iterdir()):
                if not phase_dir.is_dir() or not PHASE_RE.match(phase_dir.name):
                    continue
                for seq_dir in sorted(phase_dir.iterdir()):
                    if not seq_dir.is_dir() or not SEQ_RE.match(seq_dir.name):
                        continue
                    for task_file in sorted(seq_dir.iterdir()):
                        if not task_file.is_file():
                            continue
                        m = TASK_RE.match(task_file.name)
                        if not m:
                            continue
                        task_num, task_slug = m.group(1), m.group(2)
                        parsed = parse_task(task_file)
                        out.append({
                            "lifecycle": lifecycle,
                            "festival_name": fest_name,
                            "festival_id": fest_id,
                            "phase": phase_dir.name,
                            "sequence": seq_dir.name,
                            "task_num": task_num,
                            "task_slug": task_slug,
                            "task_path": str(task_file),
                            "title": parsed["title"],
                            "objective": parsed["objective"],
                        })
    return out

print(json.dumps({"tasks": walk(sys.argv[1:] or ["active", "ready"])}))
'''


def _walk_fest_tree(lifecycles: tuple[str, ...]) -> list[dict]:
    """Run the embedded walker inside WSL and return parsed task rows."""
    try:
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "python3", "-c", _WSL_WALKER, *lifecycles],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("wsl executable not found - skipping fest scan")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("wsl walker timed out - skipping fest scan")
        return []
    if proc.returncode != 0:
        logger.warning("wsl walker failed (rc=%s): %s", proc.returncode, proc.stderr[:200])
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        logger.warning("wsl walker returned non-JSON: %r", proc.stdout[:200])
        return []
    return payload.get("tasks", [])


def _loop_id(row: dict) -> str:
    return f"fest:{row['festival_id']}:{row['phase']}:{row['sequence']}:{row['task_num']}"


def _fest_card_from_row(row: dict, today: str) -> dict:
    """Build a thread-card-shaped object from a fest walker row.

    Stubs all convo-card fields (size/density/kwic/etc.) with zeros so
    the existing renderer destructure stays safe. UI branches on
    source == "fest" to render festival metadata instead.
    """
    slug = row["task_slug"]
    if slug in GATE_SLUGS:
        return {}
    loop_id = _loop_id(row)
    evidence = row.get("objective") or f"{row['phase']} / {row['sequence']}"
    return {
        "convo_id": loop_id,
        "loop_id": loop_id,
        "title": row["title"],
        "date": today,
        "source": "fest",
        "severity": "medium",
        "evidence": evidence,
        "festival_id": row["festival_id"],
        "festival_name": row["festival_name"],
        "lifecycle": row["lifecycle"],
        "phase": row["phase"],
        "sequence": row["sequence"],
        "task_num": row["task_num"],
        "task_slug": row["task_slug"],
        "task_path": row["task_path"],
        "age_days": None,
        "age_label": "fest task",
        "optogon_proposal": None,
        "size": {"total": 0, "user": 0, "assistant": 0, "user_chars": 0, "total_chars": 0},
        "density": [0] * 10,
        "code_blocks": {"count": 0, "languages": {}, "longest_lines": 0},
        "kwic": {"hedge_hits": 0, "resolution_hits": 0, "frustration_hits": 0},
        "excerpts": {"first_user": "", "last_user": "", "last_assistant": ""},
        "topics": [],
        "classification": {"domain": "fest", "outcome": row["lifecycle"]},
        "cluster": {"cluster_id": f"fest:{row['festival_id']}", "sibling_count": 0},
    }


def main(lifecycles: tuple[str, ...] = DEFAULT_LIFECYCLES) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    rows = _walk_fest_tree(lifecycles)

    if CARDS_PATH.exists():
        cards_doc = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    else:
        cards_doc = {"generated_at": "", "count": 0, "cards": []}
    existing_cards = cards_doc.get("cards", [])

    # Drop prior fest cards and re-sync cleanly — the fest tree is the
    # source of truth, same pattern as es_to_cards drops fs cards.
    non_fest_cards = [c for c in existing_cards if c.get("source") != "fest"]

    today = datetime.now(timezone.utc).date().isoformat()
    fest_cards = [c for c in (_fest_card_from_row(r, today) for r in rows) if c]
    merged = non_fest_cards + fest_cards

    cards_doc["generated_at"] = datetime.now(timezone.utc).isoformat()
    cards_doc["count"] = len(merged)
    cards_doc["cards"] = merged

    atomic_write_json(CARDS_PATH, cards_doc)

    by_fest: dict[str, int] = {}
    for c in fest_cards:
        by_fest[c["festival_name"]] = by_fest.get(c["festival_name"], 0) + 1

    print("\n=== FEST -> CARDS ===")
    print(f"  non-fest cards preserved: {len(non_fest_cards)}")
    print(f"  fest cards added:         {len(fest_cards)}")
    print(f"  total:                    {len(merged)}")
    if by_fest:
        print("  per-festival breakdown:")
        for name, count in sorted(by_fest.items()):
            print(f"    {name:<40} {count:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
