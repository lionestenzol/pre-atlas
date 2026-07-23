#!/usr/bin/env python3
"""Bandit node (LangGraph Skill Lattice, Seq 4).

Design Constraint 1 (docs/LANGGRAPH_SKILL_LATTICE_PLAN.md): the Thompson draw must
happen INSIDE A NODE, never in an edge function. LangGraph edges are plain Python
functions re-evaluated against state -- a random draw there would re-draw
differently on every replay, corrupting routing determinism. A node's result IS
checkpointed, so the draw happens exactly once; its result becomes durable state
(a seam.v1 Receipt); the routing edge is then a PURE function that just reads the
already-decided arm back out of state.

Reads the SAME ledger combo.py (~/.claude/scripts/ledger/combo.py) already scores:
Thompson sampling over tool-COMBINATION Beta arms (cofire "a+b" / seq "a>b"),
cold-start safe (Beta(1,1) prior -- pick_combo returns [] on an empty ledger).

    from bandit import make_bandit_node, route
    b = StateGraph(BanditState)
    b.add_node("bandit", make_bandit_node(seed=0))
    b.add_conditional_edges("bandit", route, {"code-recon": "code-recon", ..., "done": END})
"""
from __future__ import annotations

import hashlib
import json
import operator
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, TypedDict

from langgraph.func import task

_LEDGER_DIR = Path(os.environ.get(
    "LEDGER_SCRIPTS_DIR", str(Path.home() / ".claude" / "scripts" / "ledger")))
if str(_LEDGER_DIR) not in sys.path:
    sys.path.insert(0, str(_LEDGER_DIR))
import combo  # noqa: E402


class BanditState(TypedDict):
    receipts: Annotated[list[dict[str, Any]], operator.add]
    next_combo: str | None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt(tool: str, data: dict[str, Any]) -> dict[str, Any]:
    """Same seam.v1 shape as everywhere else in the lattice (matches
    atlas_map_api.seam.Receipt / skill_nodes._content_sha256's convention:
    canonical sorted-key JSON, sha256 hex, content-addressing the arm itself
    so an identical draw on replay produces an identical sha256)."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return {
        "seam_version": "v1",
        "tool": tool,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "produced_at": _utc_now_iso(),
        "status": "ok",
        "data": data,
        "error": None,
    }


def _default_load_combos() -> list[dict]:
    return combo.build_combos(combo.router.load_rows())


def make_bandit_task(
    *,
    seed: int | None = None,
    load_combos: Callable[[], list[dict]] | None = None,
):
    """The draw itself, wrapped in @task so it's checkpointed and never re-run on
    resume (Design Constraint 2) -- separate from make_bandit_node so a test can
    call the draw in isolation without a full graph."""
    _load = load_combos or _default_load_combos

    @task(name="bandit_draw")
    async def _draw() -> dict[str, Any]:
        combos = _load()
        ranked = combo.pick_combo(combos, seed=seed)
        if not ranked:
            return {"combo": None, "kind": None, "skills": None, "score": None,
                     "reason": "cold start -- no combos in ledger yet"}
        key, score, arm = ranked[0]
        return {"combo": key, "kind": arm["kind"], "skills": list(arm["skills"]), "score": score}

    return _draw


def make_bandit_node(*, seed: int | None = None, load_combos: Callable[[], list[dict]] | None = None):
    """The graph NODE (not edge) -- draws once, records the arm as a receipt,
    and writes it to state.next_combo for the routing edge to read back."""
    draw_task = make_bandit_task(seed=seed, load_combos=load_combos)

    async def bandit_node(state: BanditState) -> dict[str, Any]:
        arm = await draw_task()
        return {"receipts": [_receipt("bandit", arm)], "next_combo": arm["combo"]}

    return bandit_node


def route(state: BanditState) -> str:
    """Pure and deterministic: no randomness, no ledger read -- just reads the
    arm the bandit NODE already decided and wrote to state. Safe to re-evaluate
    any number of times (LangGraph does, internally) without corrupting anything."""
    return state.get("next_combo") or "done"
