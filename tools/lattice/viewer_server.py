#!/usr/bin/env python3
"""Lattice run viewer (LangGraph Skill Lattice, Seq 6).

Renders a `build_chain_graph` run LIVE in the browser: node colors change
gray -> green/red as each `@task`-wrapped step actually completes, streamed
via Server-Sent Events off `graph.astream(..., stream_mode="updates")`.

Reuses the vendored `cytoscape.min.js` + `cytoscape-dagre.js` already proven
in `apps/lattice/` (assemble-first: the LIBRARY is reused via a read-only
static mount; `apps/lattice/index.html` itself is NOT touched -- it's a large,
unrelated production surface (work-item viewmodel UI, its own locked 3-week
plan, Replicache write-paths to delta-kernel) that has nothing to do with
watching a LangGraph run execute. Forking or extending it for this would be
scope creep into a system with its own moat; a small standalone viewer here
is the actual assemble-first move -- reuse the dependency, not the app).

    python viewer_server.py               # serves http://127.0.0.1:8902

Two run modes, both driving the SAME graph.astream/SSE mechanism (so the
live-update wiring is proven identically either way):
  - demo: synthetic steps (no API cost) -- for verifying the mechanism itself.
  - real: skill_nodes.invoke_skill, same as run_chain.py -- costs real budget.

Checkpoints persist to viewer_runs.sqlite (next to this file, gitignored).
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graph import StepFn, build_chain_graph  # noqa: E402
from schemas import SKILL_SCHEMAS  # noqa: E402
from skill_nodes import DEFAULT_MAX_BUDGET_USD, DEFAULT_MAX_TURNS, invoke_skill  # noqa: E402
from ledger_feed import append_ledger  # noqa: E402
from demo_steps import demo_step  # noqa: E402

DB_PATH = str(_HERE / "viewer_runs.sqlite")
VENDOR_DIR = _HERE.parent.parent / "apps" / "lattice"

app = FastAPI(title="lattice-viewer")
app.mount("/vendor", StaticFiles(directory=str(VENDOR_DIR)), name="vendor")

# thread_id -> asyncio.Queue of SSE-ready event dicts, one run at a time per thread_id.
_QUEUES: dict[str, asyncio.Queue] = {}
# thread_id -> {"nodes": [...], "edges": [...]} from get_graph().to_json(), set at run start
# so the frontend can build the initial (all-pending) Cytoscape elements immediately.
_STRUCTURES: dict[str, dict[str, Any]] = {}


class RunRequest(BaseModel):
    thread_id: str | None = None
    pairs: list[list[str]] = []          # [[skill, prompt], ...] -- ignored if demo=True
    demo: bool = False
    max_turns: int = DEFAULT_MAX_TURNS
    max_budget: float = DEFAULT_MAX_BUDGET_USD


def _node_names(skills: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    names = []
    for s in skills:
        seen[s] = seen.get(s, 0) + 1
        names.append(s if seen[s] == 1 else f"{s}_{seen[s]}")
    return names


def _real_step(skill: str, prompt: str, *, max_turns: int, max_budget_usd: float):
    async def _fn() -> dict[str, Any]:
        receipt = await invoke_skill(skill, prompt, max_turns=max_turns, max_budget_usd=max_budget_usd)
        return receipt.model_dump()

    return _fn


def _is_node_update(value: Any) -> bool:
    """stream_mode='updates' fires once for the inner @task AND once for the node
    that awaits it, both keyed by the same name. Only the node-level update has
    the {"receipts": [...]} state-patch shape; the task-level one is the raw
    receipt dict. We only want to tell the browser about node completions."""
    return isinstance(value, dict) and "receipts" in value


async def _run_and_stream(thread_id: str, steps: dict[str, StepFn], order: list[str]) -> None:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    queue = _QUEUES[thread_id]
    try:
        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as saver:
            graph = build_chain_graph(steps, order=order, checkpointer=saver)
            _STRUCTURES[thread_id] = graph.get_graph().to_json()
            config = {"configurable": {"thread_id": thread_id}}
            all_receipts: list[dict[str, Any]] = []
            async for update in graph.astream({"receipts": []}, config,
                                                stream_mode="updates", durability="sync"):
                for node_name, value in update.items():
                    if not _is_node_update(value):
                        continue
                    receipt = value["receipts"][-1]
                    all_receipts.append(receipt)
                    await queue.put({"node": node_name, "status": receipt["status"],
                                      "tool": receipt["tool"], "sha256": receipt["sha256"]})
        n_fed = append_ledger(all_receipts, thread_id)
        await queue.put({"event": "done", "ledger_rows_fed": n_fed})
    except Exception as e:  # noqa: BLE001 -- report the failure to the browser, don't just die silently
        await queue.put({"event": "error", "message": str(e)})
        await queue.put({"event": "done", "ledger_rows_fed": 0})


@app.post("/run")
async def start_run(req: RunRequest) -> dict[str, Any]:
    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    if thread_id in _QUEUES:
        raise HTTPException(409, f"thread_id {thread_id!r} already has a run in flight")

    if req.demo:
        names = ["demo-a", "demo-b", "demo-c"]
        steps = {
            "demo-a": StepFn(name="demo-a", fn=demo_step("demo-a")),
            "demo-b": StepFn(name="demo-b", fn=demo_step("demo-b")),
            "demo-c": StepFn(name="demo-c", fn=demo_step("demo-c", fail=True)),
        }
    else:
        if not req.pairs:
            raise HTTPException(400, "pairs required unless demo=true")
        unknown = [skill for skill, _ in req.pairs if skill not in SKILL_SCHEMAS]
        if unknown:
            raise HTTPException(400, f"unknown skill(s) {unknown} -- known: {sorted(SKILL_SCHEMAS)}")
        names = _node_names([skill for skill, _ in req.pairs])
        steps = {
            name: StepFn(name=name, fn=_real_step(skill, prompt, max_turns=req.max_turns,
                                                     max_budget_usd=req.max_budget))
            for name, (skill, prompt) in zip(names, req.pairs)
        }

    _QUEUES[thread_id] = asyncio.Queue()
    asyncio.create_task(_run_and_stream(thread_id, steps, names))
    return {"thread_id": thread_id, "nodes": names}


@app.get("/structure/{thread_id}")
async def get_structure(thread_id: str) -> dict[str, Any]:
    for _ in range(50):  # up to ~5s: /run's background task needs one tick to populate this
        if thread_id in _STRUCTURES:
            return _STRUCTURES[thread_id]
        await asyncio.sleep(0.1)
    raise HTTPException(404, f"no structure yet for thread_id {thread_id!r}")


@app.get("/stream/{thread_id}")
async def stream(thread_id: str) -> StreamingResponse:
    if thread_id not in _QUEUES:
        raise HTTPException(404, f"no run in flight for thread_id {thread_id!r}")

    async def event_gen():
        queue = _QUEUES[thread_id]
        try:
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("event") == "done":
                    break
        finally:
            _QUEUES.pop(thread_id, None)
            _STRUCTURES.pop(thread_id, None)

    return StreamingResponse(event_gen(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache"})


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (_HERE / "viewer.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8902)
