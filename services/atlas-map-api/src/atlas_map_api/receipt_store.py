"""Durable store for seam.v1 Receipts minted by /seam/call.

Every /seam/call invocation mints a Receipt (seam.py) and, until now, threw it
away the moment it was returned to the caller -- fine for a single interactive
call, but the LangGraph Skill Lattice plan (docs/LANGGRAPH_SKILL_LATTICE_PLAN.md,
Seq 1) needs a chain's receipts to survive a crash and be replayable by
`run_id` (the eventual LangGraph `thread_id`). This module is that durability
layer: one append-only JSONL file, one line per Receipt, each tagged with the
run_id that grouped it.

Append-only, not read-modify-write like call_counter's row-per-key JSON --
receipts accumulate and are never updated in place, so a lock-guarded append
is enough; there is no read-before-write race to defend against.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def _store_path(repo_root: Path) -> Path:
    return repo_root / "services" / "atlas-map-api" / "var" / "receipts.jsonl"


def append(repo_root: Path, run_id: str, receipt: dict[str, Any]) -> None:
    """Persist one Receipt under its run_id. Fire-and-forget: never raises --
    a store bug must not be able to break a live /seam/call response."""
    path = _store_path(repo_root)
    row = {"run_id": run_id, **receipt}
    try:
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError:
        pass  # disk hiccup -- persistence is best-effort, not load-bearing for the live call


def read(repo_root: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    """All persisted rows, oldest first. Filters to one run_id when given."""
    path = _store_path(repo_root)
    if not path.is_file():
        return []
    with _LOCK:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # a corrupt line never blocks reading the rest of the store
        if run_id is None or row.get("run_id") == run_id:
            rows.append(row)
    return rows
