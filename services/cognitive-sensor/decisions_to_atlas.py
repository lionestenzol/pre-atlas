"""Mirror triage verdicts back into Atlas state.

Reads thread_decisions.json, collects every convo_id with a terminal
verdict (CLOSE/ARCHIVE/DROP), and prunes matching entries from
governance_state.open_loops and loops_latest.json so CycleBoard
stops surfacing them.

This is the missing seam that links Layer 2 (decide) back to Atlas
state. Without this, closed loops reappear on the next run because
loops.py/es_scan.py regenerate from source without consulting
decisions.

Runs as Phase 4.7 of run_daily.py — after fs_actor, before
cycleboard_push.
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
DECISIONS_PATH = BASE / "thread_decisions.json"
GOVERNANCE_PATH = BRAIN / "governance_state.json"
LOOPS_PATH = BASE / "loops_latest.json"
TERMINAL_VERDICTS = {"CLOSE", "ARCHIVE", "DROP"}


def _closed_ids() -> set[str]:
    if not DECISIONS_PATH.exists():
        return set()
    data = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    decisions = data.get("decisions", [])
    return {
        str(entry.get("convo_id"))
        for entry in decisions
        if entry.get("verdict") in TERMINAL_VERDICTS and entry.get("convo_id") is not None
    }


def _prune_governance(closed: set[str]) -> int:
    if not GOVERNANCE_PATH.exists():
        return 0
    gov = json.loads(GOVERNANCE_PATH.read_text(encoding="utf-8"))
    open_loops = gov.get("open_loops", [])
    if not isinstance(open_loops, list):
        return 0
    before = len(open_loops)
    kept = [
        loop
        for loop in open_loops
        if str(loop.get("convo_id") or loop.get("loop_id") or loop.get("id")) not in closed
    ]
    removed = before - len(kept)
    if removed:
        gov["open_loops"] = kept
        gov["open_loops_updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write_json(GOVERNANCE_PATH, gov)
    return removed


def _prune_loops_latest(closed: set[str]) -> int:
    if not LOOPS_PATH.exists():
        return 0
    loops = json.loads(LOOPS_PATH.read_text(encoding="utf-8"))
    if not isinstance(loops, list):
        return 0
    before = len(loops)
    kept = [
        loop
        for loop in loops
        if str(loop.get("convo_id") or loop.get("loop_id")) not in closed
    ]
    removed = before - len(kept)
    if removed:
        atomic_write_json(LOOPS_PATH, kept)
    return removed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    closed = _closed_ids()
    if not closed:
        print("\n=== DECISIONS -> ATLAS ===")
        print("  no terminal verdicts to mirror")
        return 0

    removed_gov = _prune_governance(closed)
    removed_loops = _prune_loops_latest(closed)

    print("\n=== DECISIONS -> ATLAS ===")
    print(f"  closed verdicts tracked: {len(closed)}")
    print(f"  pruned from open_loops:   {removed_gov}")
    print(f"  pruned from loops_latest: {removed_loops}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
