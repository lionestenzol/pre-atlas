#!/usr/bin/env python3
"""Ledger feed: append lattice graph-run receipts to the SAME tool-outcomes.jsonl
ledger combo.py scores (LangGraph Skill Lattice, Seq 5).

Mirrors tools/seam/run.py's `_append_ledger`/`_ledger_rows` EXACTLY -- same row
schema, same objective-reward convention (a receipt counts as a win iff
`status == "ok"` AND it produced a join key/`sha256`, else a loss), same
`SEAM_LEDGER=1` / `SEAM_LEDGER_PATH` gating. Reused, not reinvented -- that
mechanism already exists and is proven (assemble-first; see
~/.claude/rules/common/code-as-furniture.md).

DECISION on the plan's "OPEN QUESTION FOR SEQ 3"
(docs/LANGGRAPH_SKILL_LATTICE_PLAN.md): should the JSONL ledger `combo.py`
reads simply BE `graph.get_state_history()` across threads, instead of a
separate file? **No -- the JSONL ledger stays the canonical reward store.**
It is NOT replaced by `get_state_history()`. Three reasons, checked against
source before deciding, not assumed:

  1. COVERAGE. The ledger aggregates every skill invocation across every
     session -- interactive (mined by backfill.py from session transcripts)
     AND seam's objective rows AND now lattice's. `get_state_history()` is
     scoped to a single LangGraph thread_id. Swapping the ledger for it
     would blind combo.py to the much larger volume of non-lattice usage
     (209 real rows exist today; lattice has produced a handful).
  2. REWARD SEMANTICS. A checkpointed Receipt only carries status/error --
     it has no reward field. The ledger's reward is either sentiment +
     shipped/retried fusion (interactive rows, router._row_reward) or the
     objective ok+sha256 convention seam already established
     (tools/seam/run.py:_receipt_ok). Neither is derivable from a LangGraph
     checkpoint alone.
  3. COUPLING. combo.py is deliberately stdlib-only and ledger-format-
     agnostic (its own docstring: "stdlib only"). Coupling it to LangGraph's
     internal checkpoint schema would tie a small, stable, proven reward
     store to a fast-moving library internal for no benefit.

  Unification means what the plan's own Seq 5 DoD already implies: lattice
  runs FEED the same ledger seam already feeds, using the same schema --
  one substrate, multiple writers -- not "replace the substrate."

Rows here are 'seq' (a>b) shaped, not 'cofire', by construction: each
lattice node fires in a DETERMINED ORDER (that's the whole point of a chain
graph), unlike seam's fan-out pipeline where receipts genuinely co-occur in
one turn. Giving each row a DISTINCT `request` (unlike seam's one-shared-
request-per-manifest) keeps them as separate turns, so
combo.build_combos's seq-window derivation reads the chain as a>b
transitions in execution order, which is what actually happened.

The bandit node's own receipt (tool="bandit") is EXCLUDED: it's routing
metadata, not a skill firing. Bandit always immediately precedes whatever
it routed to by construction, so "bandit>code-recon" is not a learnable
transition -- it would just pollute genuine skill-to-skill combos with a
relationship that's structural, not informative.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

EXCLUDED_TOOLS = {"bandit"}


def _ledger_path() -> Path:
    return Path(os.environ.get(
        "SEAM_LEDGER_PATH", str(Path.home() / ".claude" / "logs" / "tool-outcomes.jsonl")))


def _next_invocation_index(path: Path, session: str) -> int:
    """Max existing invocation_index for `session`, +1 (monotonic per session,
    matching backfill.py's and seam's convention exactly)."""
    hi = -1
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("session") == session:
                        idx = r.get("invocation_index")
                        if isinstance(idx, int) and idx > hi:
                            hi = idx
        except OSError:
            pass
    return hi + 1


def _receipt_ok(r: dict[str, Any]) -> bool:
    """Same bar as seam's _receipt_ok: the tool RAN (status ok) AND produced a
    join key (sha256) -- a tool that ran but content-addressed nothing didn't
    deliver, so it must not count as a win."""
    return r.get("status") == "ok" and bool(r.get("sha256"))


def ledger_rows(receipts: list[dict[str, Any]], thread_id: str, base_index: int) -> list[dict[str, Any]]:
    """One objective row per lattice-graph receipt, excluding bandit routing
    receipts, matching tools/seam/run.py's `_ledger_rows` schema exactly so
    combo.py reads lattice rows and seam rows identically."""
    session = f"lattice:{thread_id}"
    rows: list[dict[str, Any]] = []
    off = 0
    for r in receipts:
        tool = r.get("tool")
        if not tool or tool in EXCLUDED_TOOLS:
            continue
        ok_r = _receipt_ok(r)
        reward = 1.0 if ok_r else -1.0
        idx = base_index + off
        rows.append({
            "session": session,
            "cwd": None,
            "skill": tool,
            "source": "lattice",
            "invocation_index": idx,
            "request": f"lattice:{thread_id}:{tool}:{idx}",  # distinct per node -> seq, not cofire
            "n_tools_in_turn": 1,
            "reward": "objective_ok" if ok_r else "objective_error",
            "score": reward,
            "shipped": False,
            "retried": False,
            "reward_score": reward,                # router._row_reward reads this first
            "next_user": None,
            "has_feedback": True,
        })
        off += 1
    return rows


def append_ledger(receipts: list[dict[str, Any]], thread_id: str) -> int:
    """Append lattice receipts to the ledger. No-op unless SEAM_LEDGER=1 (same
    gate as seam's _append_ledger -- exploratory/test graph runs never pollute
    the real ledger by default). Fail-safe: a ledger write error never raises
    -- this is telemetry, not a load-bearing return path for the graph run.
    Returns the number of rows written (0 when gated off, no real receipts
    after filtering, or on error)."""
    if os.environ.get("SEAM_LEDGER") != "1":
        return 0
    try:
        if not receipts:
            return 0
        path = _ledger_path()
        session = f"lattice:{thread_id}"
        rows = ledger_rows(receipts, thread_id, _next_invocation_index(path, session))
        if not rows:
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)
    except Exception as e:  # noqa: BLE001 -- telemetry must never break a graph run
        print(f"lattice: ledger feed skipped (non-fatal): {e!r}", file=sys.stderr)
        return 0
