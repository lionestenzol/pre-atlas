"""Convert es_scan findings into thread cards.

Reads cycleboard/brain/machine_scan.json and merges fs-loops into
thread_cards.json so the same UI (thread_cards.html) and the same
`atl` CLI can triage filesystem findings alongside conversational
threads.

fs cards share the surface and decide layers with convo cards but
route to a separate actor (fs_actor.py) because they don't have
conversations to mine.

Run as Phase 1.6 of run_daily.py — after es_scan.py, before
wire_cycleboard.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN = BASE / "cycleboard" / "brain"
CARDS_PATH = BASE / "thread_cards.json"
SCAN_PATH = BRAIN / "machine_scan.json"
AUTO_TRIAGE_LOG = BASE / "auto_triage_log.json"


def _proposals_by_loop_id() -> dict[str, dict]:
    """Latest Optogon proposal per loop_id, keyed for quick card enrichment."""
    if not AUTO_TRIAGE_LOG.exists():
        return {}
    try:
        log = json.loads(AUTO_TRIAGE_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict] = {}
    for run in log.get("runs", []):
        for item in run.get("items", []):
            lid = item.get("loop_id")
            if not lid or "skipped" in item:
                continue
            out[lid] = {
                "verdict": item.get("proposed_verdict"),
                "action": item.get("proposed_action"),
                "confidence": item.get("confidence"),
                "rationale": item.get("rationale"),
                "ran_at": run.get("ran_at"),
            }
    return out


def _fs_card_from_scan_item(item: dict, proposals: dict[str, dict]) -> dict:
    """Build a thread-card-shaped object from a machine_scan item.

    Convo cards carry conversation metrics (size, density, code_blocks,
    kwic, topics, cluster, classification). fs cards stub those with
    minimal placeholders and carry source/evidence/severity instead.
    The renderer branches on source == "fs".
    """
    age = item.get("age_days")
    age_label = f"{age}d" if age is not None else "unknown age"
    proposal = proposals.get(item["loop_id"])
    return {
        "convo_id": item["loop_id"],
        "loop_id": item["loop_id"],
        "title": item["title"],
        "date": datetime.now(timezone.utc).date().isoformat(),
        "source": "fs",
        "severity": item.get("severity", "medium"),
        "evidence": item.get("evidence", ""),
        "age_days": age,
        "age_label": age_label,
        "optogon_proposal": proposal,
        # Stub fields so the existing renderer's destructure doesn't crash.
        "size": {"total": 0, "user": 0, "assistant": 0, "user_chars": 0, "total_chars": 0},
        "density": [0] * 10,
        "code_blocks": {"count": 0, "languages": {}, "longest_lines": 0},
        "kwic": {"hedge_hits": 0, "resolution_hits": 0, "frustration_hits": 0},
        "excerpts": {"first_user": "", "last_user": "", "last_assistant": ""},
        "topics": [],
        "classification": {"domain": "fs", "outcome": item.get("severity", "medium")},
        "cluster": {"cluster_id": "fs", "sibling_count": 0},
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not SCAN_PATH.exists():
        print("  [SKIP] machine_scan.json not found — run es_scan.py first")
        return 0
    scan = json.loads(SCAN_PATH.read_text(encoding="utf-8"))
    fs_items = scan.get("items", [])

    if CARDS_PATH.exists():
        cards_doc = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    else:
        cards_doc = {"generated_at": "", "count": 0, "cards": []}
    existing_cards = cards_doc.get("cards", [])

    # Drop all prior fs cards so we re-sync cleanly each run — fs state
    # comes from the filesystem, not from a durable record in this file.
    convo_cards = [c for c in existing_cards if c.get("source") != "fs"]

    proposals = _proposals_by_loop_id()
    fs_cards = [_fs_card_from_scan_item(item, proposals) for item in fs_items]
    merged = convo_cards + fs_cards

    cards_doc["generated_at"] = datetime.now(timezone.utc).isoformat()
    cards_doc["count"] = len(merged)
    cards_doc["cards"] = merged

    atomic_write_json(CARDS_PATH, cards_doc)

    print("\n=== ES -> CARDS ===")
    print(f"  convo cards preserved: {len(convo_cards)}")
    print(f"  fs cards added:        {len(fs_cards)}")
    print(f"  total:                 {len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
