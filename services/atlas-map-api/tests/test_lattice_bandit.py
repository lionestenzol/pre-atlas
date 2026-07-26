"""Tests for tools/lattice/bandit.py -- the bandit node (Seq 4).

Hermetic: `load_combos` is always injected with a fixed, in-memory combos list --
none of these touch the real ~/.claude/logs/tool-outcomes.jsonl ledger. Proves
Design Constraint 1 directly: the Thompson draw happens once inside a NODE (not
the conditional edge), gets recorded as a seam.v1 Receipt, and replaying the
same thread_id after a downstream crash returns the SAME arm -- not a fresh
draw -- because `route()` only ever reads back what the node already decided.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph


def _load_lattice_module(name: str):
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


bandit_mod = _load_lattice_module("bandit")

# A fixed 2-arm combo set: "code-recon+groundwork" (cofire) heavily favored (many
# wins), "code-recon>weapon" (seq) cold. Thompson sampling with seed=0 against this
# fixed input is deterministic -- pytest just needs to observe what it produces,
# not hardcode LangGraph/random internals.
FIXED_COMBOS = (
    [{"combo": "code-recon+groundwork", "kind": "cofire",
      "skills": ("code-recon", "groundwork"), "reward_score": 1.0, "session": "s1"}] * 8
    + [{"combo": "code-recon>weapon", "kind": "seq",
        "skills": ("code-recon", "weapon"), "reward_score": -1.0, "session": "s2"}] * 2
)


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def run(coro):
    return asyncio.run(coro)


def _expected_top_combo() -> str:
    """Ground truth: what bandit.py's own draw (combo.pick_combo) actually picks
    for FIXED_COMBOS at seed=0 -- computed via the same code path under test, not
    hand-derived, since the point is proving the WIRING (node/receipt/route), not
    re-deriving Thompson sampling math."""
    import combo
    ranked = combo.pick_combo(list(FIXED_COMBOS), seed=0)
    return ranked[0][0]


def _build_routed_graph(*, seed, load_combos, echo_calls, fail_once_on=None):
    """bandit -> conditional route -> {expected combo: echo node, other: echo node, done: END}."""
    fail_once_on = fail_once_on or {}

    def _make_echo(name):
        attempts = {"n": 0}

        async def _echo(state) -> dict:
            attempts["n"] += 1
            if name in fail_once_on and attempts["n"] == 1:
                raise RuntimeError(f"simulated crash in {name}")
            echo_calls.append(name)
            return {"receipts": [{"tool": name, "status": "ok", "data": {}, "sha256": None,
                                    "error": None, "seam_version": "v1", "produced_at": ""}]}

        return _echo

    g = StateGraph(bandit_mod.BanditState)
    g.add_node("bandit", bandit_mod.make_bandit_node(seed=seed, load_combos=load_combos))
    g.add_node("code-recon+groundwork", _make_echo("code-recon+groundwork"))
    g.add_node("code-recon>weapon", _make_echo("code-recon>weapon"))
    g.add_edge(START, "bandit")
    g.add_conditional_edges("bandit", bandit_mod.route, {
        "code-recon+groundwork": "code-recon+groundwork",
        "code-recon>weapon": "code-recon>weapon",
        "done": END,
    })
    g.add_edge("code-recon+groundwork", END)
    g.add_edge("code-recon>weapon", END)
    return g


# ---- the draw itself is a plain function call, provably free of graph magic ---
def test_pick_combo_is_reproducible_for_a_fixed_seed_and_combos():
    import combo
    ranked_a = combo.pick_combo(list(FIXED_COMBOS), seed=0)
    ranked_b = combo.pick_combo(list(FIXED_COMBOS), seed=0)
    assert ranked_a[0][0] == ranked_b[0][0]


# ---- route() is pure: no randomness, no ledger, just a dict read --------------
def test_route_is_a_pure_state_read():
    assert bandit_mod.route({"receipts": [], "next_combo": "code-recon+groundwork"}) == "code-recon+groundwork"
    assert bandit_mod.route({"receipts": [], "next_combo": None}) == "done"
    assert bandit_mod.route({"receipts": []}) == "done"  # missing key -> cold-start-safe default


# ---- cold start: empty ledger -> next_combo None -> routes to "done" ----------
def test_cold_start_empty_combos_routes_to_done():
    echo_calls = []
    g = _build_routed_graph(seed=0, load_combos=lambda: [], echo_calls=echo_calls)

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            compiled = g.compile(checkpointer=saver)
            return await compiled.ainvoke({"receipts": [], "next_combo": None},
                                            _thread_config("cold"), durability="sync")

    result = run(body())
    assert echo_calls == []  # neither echo node fired
    bandit_receipt = next(r for r in result["receipts"] if r["tool"] == "bandit")
    assert bandit_receipt["data"]["combo"] is None
    assert bandit_receipt["data"]["reason"] == "cold start -- no combos in ledger yet"


# ---- the drawn arm is recorded as a receipt, and routing follows it -----------
def test_bandit_node_records_receipt_and_route_follows_it():
    expected = _expected_top_combo()
    echo_calls = []
    g = _build_routed_graph(seed=0, load_combos=lambda: list(FIXED_COMBOS), echo_calls=echo_calls)

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            compiled = g.compile(checkpointer=saver)
            return await compiled.ainvoke({"receipts": [], "next_combo": None},
                                            _thread_config("t1"), durability="sync")

    result = run(body())
    bandit_receipt = next(r for r in result["receipts"] if r["tool"] == "bandit")
    assert bandit_receipt["data"]["combo"] == expected
    assert bandit_receipt["sha256"] and len(bandit_receipt["sha256"]) == 64
    assert echo_calls == [expected]  # route() sent execution to the node the draw picked


# ---- THE Seq 4 DoD: replaying the same thread_id after a crash produces the
# SAME arm -- not a fresh draw -- because the draw lives in a node, not the edge.
def test_replay_after_downstream_crash_produces_the_same_arm_not_a_fresh_draw():
    expected = _expected_top_combo()
    draw_calls = []
    echo_calls = []

    def counting_load_combos():
        draw_calls.append(1)
        return list(FIXED_COMBOS)

    g = _build_routed_graph(
        seed=0, load_combos=counting_load_combos, echo_calls=echo_calls,
        fail_once_on={expected},
    )
    config = _thread_config("t2")

    async def crash_then_resume():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            compiled = g.compile(checkpointer=saver)
            with pytest.raises(RuntimeError, match="simulated crash"):
                await compiled.ainvoke({"receipts": [], "next_combo": None}, config, durability="sync")

            # bandit already ran once and its receipt is checkpointed
            assert draw_calls == [1]

            result = await compiled.ainvoke(None, config, durability="sync")  # resume
            return result, saver

    result, _saver = run(crash_then_resume())

    # The bandit's draw was NOT re-invoked on resume (draw_calls still has one entry) --
    # this is the mechanism-level proof that the arm wasn't redrawn.
    assert draw_calls == [1]
    bandit_receipts = [r for r in result["receipts"] if r["tool"] == "bandit"]
    assert len(bandit_receipts) == 1  # not duplicated by the resume, either
    assert bandit_receipts[0]["data"]["combo"] == expected
    assert echo_calls == [expected]  # the downstream node genuinely retried and succeeded


# ---- literal DoD wording: get_state_history() shows the drawn arm recorded ----
def test_state_history_shows_the_drawn_arm_as_a_receipt():
    expected = _expected_top_combo()
    echo_calls = []
    g = _build_routed_graph(seed=0, load_combos=lambda: list(FIXED_COMBOS), echo_calls=echo_calls)
    config = _thread_config("t3")

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            compiled = g.compile(checkpointer=saver)
            await compiled.ainvoke({"receipts": [], "next_combo": None}, config, durability="sync")
            history = [snap async for snap in compiled.aget_state_history(config)]
            return history

    history = run(body())
    assert history, "expected at least one checkpointed state snapshot"
    combos_seen = {
        r["data"]["combo"]
        for snap in history
        for r in snap.values.get("receipts", [])
        if r["tool"] == "bandit"
    }
    assert combos_seen == {expected}
