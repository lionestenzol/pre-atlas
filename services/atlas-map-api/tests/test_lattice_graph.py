"""Tests for tools/lattice/graph.py -- the LangGraph spine (Seq 3).

Hermetic: every step is a plain Python callable (no real skill/SDK/network
call), so these prove the DURABILITY MECHANISM itself -- resume-at-crash-point,
no re-execution of completed @task work -- independent of what a step actually
does. Seq 2's skill_nodes.invoke_skill is exactly the kind of callable a real
StepFn.fn would wrap; that wiring is a one-line adapter, not exercised here.

Nodes in graph.py are async (they `await` @task calls), so every checkpointer
here is AsyncSqliteSaver + ainvoke -- the sync SqliteSaver raises
NotImplementedError against an async graph (confirmed against the installed
langgraph-checkpoint-sqlite 3.1.0, not assumed).
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def _load_lattice_module(name: str):
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


graph_mod = _load_lattice_module("graph")


def _receipt(tool: str, data: dict) -> dict:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return {
        "seam_version": "v1",
        "tool": tool,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "status": "ok",
        "data": data,
        "error": None,
    }


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def run(coro):
    """Drive an async test body from a plain (non-pytest-asyncio) test function."""
    return asyncio.run(coro)


# ---- linear chain: normal run, no crash -----------------------------------
def test_linear_chain_accumulates_receipts_in_order():
    calls = []

    def step_a():
        calls.append("a")
        return _receipt("a", {"n": 1})

    def step_b():
        calls.append("b")
        return _receipt("b", {"n": 2})

    steps = {
        "a": graph_mod.StepFn(name="a", fn=step_a),
        "b": graph_mod.StepFn(name="b", fn=step_b),
    }

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            g = graph_mod.build_chain_graph(steps, order=["a", "b"], checkpointer=saver)
            return await g.ainvoke({"receipts": []}, _thread_config("t1"), durability="sync")

    result = run(body())
    assert calls == ["a", "b"]
    assert [r["tool"] for r in result["receipts"]] == ["a", "b"]


# ---- resume at the interrupted NODE (Pregel-level durability) -------------
def test_crash_in_node_b_then_resume_does_not_rerun_node_a():
    calls = []
    attempt = {"n": 0}

    def step_a():
        calls.append("a")
        return _receipt("a", {"n": 1})

    def step_b():
        attempt["n"] += 1
        if attempt["n"] == 1:
            raise RuntimeError("simulated crash mid-chain")
        calls.append("b")
        return _receipt("b", {"n": 2})

    steps = {
        "a": graph_mod.StepFn(name="a", fn=step_a),
        "b": graph_mod.StepFn(name="b", fn=step_b),
    }

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            g = graph_mod.build_chain_graph(steps, order=["a", "b"], checkpointer=saver)
            config = _thread_config("t2")

            with pytest.raises(RuntimeError, match="simulated crash mid-chain"):
                await g.ainvoke({"receipts": []}, config, durability="sync")

            assert calls == ["a"]  # node b's crash didn't lose node a's completed work

            # graph.invoke(None, config) (here: ainvoke) = resume from the checkpoint
            return await g.ainvoke(None, config, durability="sync")

    result = run(body())
    assert calls == ["a", "b"]  # node a NOT re-run
    assert [r["tool"] for r in result["receipts"]] == ["a", "b"]


# ---- the case Design Constraint 2 actually warns about: TWO @tasks inside
# ONE node. A crash after the first task's result is checkpointed must not
# re-invoke that task's underlying function when the node body re-runs from
# its top on resume. ----------------------------------------------------------
def test_two_tasks_in_one_node_first_task_not_rerun_after_node_restarts():
    task_a_calls = []
    task_b_attempts = {"n": 0}

    @graph_mod.task(name="inner_a")
    async def inner_a() -> dict:
        task_a_calls.append(1)
        return _receipt("inner_a", {"n": 1})

    @graph_mod.task(name="inner_b")
    async def inner_b() -> dict:
        task_b_attempts["n"] += 1
        if task_b_attempts["n"] == 1:
            raise RuntimeError("simulated crash between tasks")
        return _receipt("inner_b", {"n": 2})

    async def combo_node(state: graph_mod.State) -> dict:
        ra = await inner_a()
        rb = await inner_b()
        return {"receipts": [ra, rb]}

    g = graph_mod.StateGraph(graph_mod.State)
    g.add_node("combo", combo_node)
    g.add_edge(graph_mod.START, "combo")
    g.add_edge("combo", graph_mod.END)

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            compiled = g.compile(checkpointer=saver)
            config = _thread_config("t3")

            with pytest.raises(RuntimeError, match="simulated crash between tasks"):
                await compiled.ainvoke({"receipts": []}, config, durability="sync")

            assert task_a_calls == [1]  # inner_a's real work ran exactly once so far

            return await compiled.ainvoke(None, config, durability="sync")

    result = run(body())
    # The node body re-ran from its top (inner_a() was called again as a
    # Python statement) but the underlying task function was NOT re-executed:
    assert task_a_calls == [1]
    assert task_b_attempts["n"] == 2  # inner_b genuinely retried (it never completed before the crash)
    assert [r["tool"] for r in result["receipts"]] == ["inner_a", "inner_b"]


# ---- receipt CIDs are identical (not regenerated) across the crash/resume
# boundary -- the plan's own DoD phrasing for Seq 3. -------------------------
def test_receipt_sha256_identical_across_crash_and_resume():
    attempt = {"n": 0}

    def step_a():
        return _receipt("a", {"payload": "fixed content"})

    def step_b():
        attempt["n"] += 1
        if attempt["n"] == 1:
            raise RuntimeError("crash")
        return _receipt("b", {"payload": "other content"})

    steps = {
        "a": graph_mod.StepFn(name="a", fn=step_a),
        "b": graph_mod.StepFn(name="b", fn=step_b),
    }

    async def body():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as saver:
            g = graph_mod.build_chain_graph(steps, order=["a", "b"], checkpointer=saver)
            config = _thread_config("t4")
            with pytest.raises(RuntimeError):
                await g.ainvoke({"receipts": []}, config, durability="sync")
            return await g.ainvoke(None, config, durability="sync")

    result = run(body())
    receipt_a = next(r for r in result["receipts"] if r["tool"] == "a")
    assert receipt_a["sha256"] == hashlib.sha256(
        json.dumps({"payload": "fixed content"}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ---- kill-the-PROCESS realism: reopen a fresh AsyncSqliteSaver against the
# same on-disk file (a new connection, as a real restarted process would
# have), not the same in-memory Python object. --------------------------------
def test_resume_survives_a_fresh_saver_instance_against_the_same_file(tmp_path):
    db_path = str(tmp_path / "lattice_seq3_test.sqlite")
    calls = []
    attempt = {"n": 0}

    def step_a():
        calls.append("a")
        return _receipt("a", {"n": 1})

    def step_b():
        attempt["n"] += 1
        if attempt["n"] == 1:
            raise RuntimeError("process died here")
        calls.append("b")
        return _receipt("b", {"n": 2})

    steps = {
        "a": graph_mod.StepFn(name="a", fn=step_a),
        "b": graph_mod.StepFn(name="b", fn=step_b),
    }
    config = _thread_config("t5")

    async def crash_phase():
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver1:
            g1 = graph_mod.build_chain_graph(steps, order=["a", "b"], checkpointer=saver1)
            with pytest.raises(RuntimeError, match="process died here"):
                await g1.ainvoke({"receipts": []}, config, durability="sync")
        # saver1's connection is now closed -- simulates the process exiting.

    async def resume_phase():
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver2:  # a genuinely new connection/object
            g2 = graph_mod.build_chain_graph(steps, order=["a", "b"], checkpointer=saver2)
            return await g2.ainvoke(None, config, durability="sync")

    run(crash_phase())
    assert calls == ["a"]

    result = run(resume_phase())
    assert calls == ["a", "b"]  # step_a not re-run even from a fresh saver + fresh graph object
    assert [r["tool"] for r in result["receipts"]] == ["a", "b"]
