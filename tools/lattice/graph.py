#!/usr/bin/env python3
"""LangGraph spine (LangGraph Skill Lattice, Seq 3).

State is an append-only list of seam.v1 Receipts (`operator.add` reducer).
Every skill/CLI invocation is wrapped in a `langgraph.func.task` -- per Design
Constraint 2 in docs/LANGGRAPH_SKILL_LATTICE_PLAN.md, LangGraph replays a
crashed run from the START OF THE INTERRUPTED NODE, not the crashed line, so a
node that shells out (or calls an SDK) directly would redo that call on every
resume. Only `@task` results are checkpointed and skipped on replay -- proven
by services/atlas-map-api/tests/test_lattice_graph.py, which crashes a node
AFTER its first @task has completed and confirms that task's underlying
function is not called again on resume.

Checkpointed via AsyncSqliteSaver (nodes here are async) with durability="sync"
(an ainvoke()-time kwarg, not compile()-time -- the default "async" durability
has a loss window per the plan's Honest Cost #2).

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from graph import build_chain_graph, StepFn

    steps = {"a": StepFn(name="a", fn=lambda: some_receipt_dict)}
    async with AsyncSqliteSaver.from_conn_string("lattice.sqlite") as saver:
        graph = build_chain_graph(steps, order=["a"], checkpointer=saver)
        await graph.ainvoke({"receipts": []}, {"configurable": {"thread_id": "t1"}}, durability="sync")
"""
from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class State(TypedDict):
    receipts: Annotated[list[dict[str, Any]], operator.add]


@dataclass(frozen=True)
class StepFn:
    """One node's unit of work: a name (also the @task name, for the graph's
    mermaid/debug output) and a zero-arg callable returning a seam.v1 Receipt
    dict (sync or async)."""

    name: str
    fn: Callable[[], Awaitable[dict[str, Any]] | dict[str, Any]]


def build_chain_graph(
    steps: dict[str, StepFn],
    order: list[str],
    checkpointer: Any,
) -> CompiledStateGraph:
    """Compile a linear START -> steps[order[0]] -> ... -> steps[order[-1]] -> END graph.

    Each graph node wraps exactly one @task call, so LangGraph's built-in
    per-superstep checkpointing already covers "resume at the interrupted
    node" for single-task nodes -- but the @task wrapping is what protects a
    node whose function does post-processing AFTER awaiting the task (see the
    two-tasks-in-one-node test, which is the case Design Constraint 2 actually
    warns about: a node re-running its OWN body on resume must not re-invoke
    an already-completed task nested inside it).
    """
    missing = [name for name in order if name not in steps]
    if missing:
        raise ValueError(f"order references unknown steps: {missing}")

    tasks = {name: _make_task(steps[name]) for name in order}

    def _make_node(name: str):
        async def _node(state: State) -> dict[str, Any]:
            receipt = await tasks[name]()
            return {"receipts": [receipt]}

        return _node

    g: StateGraph = StateGraph(State)
    prev = START
    for name in order:
        g.add_node(name, _make_node(name))
        g.add_edge(prev, name)
        prev = name
    g.add_edge(prev, END)
    return g.compile(checkpointer=checkpointer)


def _make_task(step: StepFn):
    @task(name=step.name)
    async def _task() -> dict[str, Any]:
        result = step.fn()
        if hasattr(result, "__await__"):
            result = await result
        return result

    return _task
