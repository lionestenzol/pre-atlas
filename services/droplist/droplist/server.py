"""DropList HTTP read-only API surface. See BIBLE.md §17 for the protocol."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from . import (  # noqa: F401 — atlas_signal/dag_builder kept for v2 mutation surface
    atlas_signal,
    auth,
    clock,
    command_brief,
    dag_builder,
    dag_update,
    dispatcher,
    entities,
    intake,
    state,
    storage,
)

# Lattice surface lives on delta-kernel (services/delta-kernel/src/api/server.ts
# routes /api/lattice/viewmodel + /api/lattice/correct, backed by
# atlas/lattice-projection.ts). apps/lattice/index.html hardcodes that base URL.
# DropList feeds Lattice indirectly via PKT-006's Signal.v1 emission to
# delta-kernel — not by exposing a parallel /api/lattice/* surface.
# See BIBLE.md §13 OQ-18 and PACKETS/007.

# ---------------------------------------------------------------------------
# Brick 2: optional self-advancing daemon thread, gated by DROPLIST_DAEMON=1.
#
# This adds NO endpoint and NO mutation route — the read-only HTTP surface
# stays read-only. It only runs the SAME daemon._run_once() loop the standalone
# `python -m droplist.daemon` runs, on a background daemon thread, so an
# always-on `droplist-ui` process is self-advancing without a separate cron
# entry. With DROPLIST_DAEMON unset the server is byte-identical to before.
# Uses the modern FastAPI lifespan (not the deprecated @app.on_event) so no
# deprecated path is left to rot — see ~/.claude/rules/common/code-as-furniture.md.
# ---------------------------------------------------------------------------

#: Module-level sentinel: None until the gated startup hook spawns the loop.
#: The gating test asserts this stays None when DROPLIST_DAEMON is unset.
_daemon_thread: Optional[threading.Thread] = None


def _maybe_start_daemon() -> None:
    """Spawn the daemon loop on a background thread iff DROPLIST_DAEMON=1.

    Called from the lifespan startup phase, and directly by the gating test.
    Idempotent: never spawns a second loop while one is alive.
    """
    global _daemon_thread
    if os.environ.get("DROPLIST_DAEMON") != "1":
        return
    if _daemon_thread is not None and _daemon_thread.is_alive():
        return  # already running; never spawn a second loop
    from . import daemon  # local import keeps daemon out of the read path by default
    interval = float(os.environ.get("DROPLIST_DAEMON_INTERVAL", daemon._DEFAULT_INTERVAL))
    _daemon_thread = threading.Thread(
        target=daemon.run_loop, kwargs={"interval": interval},
        name="droplist-daemon", daemon=True)
    _daemon_thread.start()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    auth.load_or_create_token()  # resolve/persist the shared write secret at startup
    _maybe_start_daemon()
    yield
    # The daemon thread is a daemon=True thread; it dies with the interpreter.
    # No explicit join — run_loop is KeyboardInterrupt-clean and stateless.


app = FastAPI(title="DropList API", version="0.1.0", lifespan=_lifespan)

# CORS allowlist (Task B, 2026-06-25). Was allow_origins=["*"], which let a tab
# at ANY origin read this API's responses — a DNS-rebind/foreign-origin write
# vector. Now: localhost only by default, plus comma-separated deploy origins via
# DROPLIST_ALLOWED_ORIGINS. The X-Atlas-Token guard (auth.py) is the real lock on
# writes; this narrows who can even talk to the surface from a browser.
# See ~/.claude/rules/common/code-as-furniture.md — open CORS fixed inline.
_DEFAULT_ORIGINS = ["http://localhost:3073", "http://127.0.0.1:3073"]
_ENV_ORIGINS = [
    o.strip() for o in os.environ.get("DROPLIST_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _ENV_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Atlas-Token"],
)


def _packets_by_drop() -> dict:
    return {p.get("drop_id", ""): p for p in storage.read_all(storage.PACKETS)}


def _dag_dir() -> Path:
    return Path(storage.DATA_DIR) / "dags"


# ---------------------------------------------------------------------------
# UI front door (ship Task A, 2026-06-25). The built single-page UIs already
# self-wire to THIS same origin (ui/line.html -> GET /api/now at line.html:1614;
# ui/chain.html -> GET /api/dag/sample at chain.html:323), but the server only
# ever exposed JSON — so the UI existed and was unreachable, the #1 ship blocker
# from DROPLIST_SHIP_SPEC_2026-06-25.md. Serving them here closes that gap with
# zero client config. See ~/.claude/rules/common/code-as-furniture.md.
# ---------------------------------------------------------------------------
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"


def _serve_ui(filename: str) -> HTMLResponse:
    """Serve a UI page with the write token injected as ``window.__DL_TOKEN__``.

    The same-origin page reads it to authenticate its calls to the Anthropic
    proxy (Task B). A cross-origin (DNS-rebind) tab CANNOT read this response
    body — CORS makes it opaque — so the token isn't leaked to an attacker tab;
    a same-origin local process that can GET this page could already read the
    gitignored token file, so the bar is unchanged. See auth.py and
    ~/.claude/rules/common/code-as-furniture.md."""
    html = (_UI_DIR / filename).read_text(encoding="utf-8")
    inject = f"<script>window.__DL_TOKEN__={json.dumps(auth.current_token())};</script>"
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
def ui_now() -> HTMLResponse:
    """Serve the NOW screen (ui/line.html) — self-wires to GET /api/now."""
    return _serve_ui("line.html")


@app.get("/chain", response_class=HTMLResponse)
def ui_chain() -> HTMLResponse:
    """Serve the DAG/chain view (ui/chain.html) — self-wires to GET /api/dag/sample."""
    return _serve_ui("chain.html")


# ---------------------------------------------------------------------------
# Server-side Anthropic proxy (Task B, 2026-06-25). The UIs used to POST straight
# to api.anthropic.com from the browser — which both fails (CORS) and is a
# client-side API-key path. This route holds the key server-side
# (ANTHROPIC_API_KEY) and forwards the messages payload, so NO key ships to the
# client (grep ui/ for sk-ant/api.anthropic.com comes back clean). Guarded by the
# write token because it spends money. urllib in a threadpool = zero new deps and
# never blocks the event loop. See ~/.claude/rules/common/code-as-furniture.md.
# ---------------------------------------------------------------------------
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


def _forward_anthropic(payload: bytes) -> tuple[int, bytes]:
    """Blocking POST to Anthropic with the server-side key. Runs in a threadpool."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return 503, b'{"error":"ANTHROPIC_API_KEY is not set on the server"}'
    req = urllib.request.Request(
        _ANTHROPIC_URL, data=payload, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001 — network/timeout surfaces as 502
        return 502, json.dumps({"error": f"anthropic proxy failed: {e}"}).encode()


@app.post("/api/ai/anthropic", dependencies=[Depends(auth.require_write_token)])
async def proxy_anthropic(request: Request) -> Response:
    """Forward an Anthropic /v1/messages request using the server-side key. The
    body is the same {model, max_tokens, system, messages} the UI already builds;
    the upstream response is passed straight back so the UI's data.content parse
    is unchanged."""
    body = await request.body()
    status, out = await run_in_threadpool(_forward_anthropic, body)
    return Response(content=out, status_code=status, media_type="application/json")


@app.get("/api/now")
def get_now() -> dict:
    brief = command_brief.build_brief()
    nb = brief.get("next_best")
    if not nb:
        return {"job": None, "after": None}
    dag = storage.load_dag(nb["dag"])
    if dag is None:
        return {"job": None, "after": None}
    src = _packets_by_drop().get(dag.get("source_drop"), {})
    steps = [{"text": n["title"], "done": n.get("status") == "done"} for n in dag["nodes"]]
    next_move = next((n["title"] for n in dag["nodes"] if n.get("status") == "ready"), "")
    done_means = "; ".join(n["done_condition"] for n in dag["nodes"] if n.get("done_condition"))
    ready = brief.get("ready") or []
    after = ready[1]["title"] if len(ready) > 1 else None
    return {
        "job": {
            "id": dag["dag_id"],
            "title": dag.get("goal", ""),
            "why": src.get("raw_input", ""),
            "doneMeans": done_means,
            "nextMove": next_move,
            "steps": steps,
            "status": dag.get("status", "running"),
        },
        "after": after,
    }


@app.get("/api/dag/sample")
def get_dag_sample(dag_id: Optional[str] = None) -> dict:
    """Alias the chain view expects (chain.html:323): a specific ?dag_id=, else
    the most-recently-modified DAG. Declared before /api/dag/{dag_id} so the
    literal 'sample' path wins over the path param."""
    if dag_id:
        d = storage.load_dag(dag_id)
        if d is None:
            raise HTTPException(status_code=404, detail=f"dag {dag_id} not found")
        return d
    files = sorted(_dag_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files:
        d = storage.load_dag(p.stem)
        if d:
            return d
    return {"dag_id": None, "nodes": []}


@app.get("/api/dag/{dag_id}")
def get_dag(dag_id: str) -> dict:
    d = storage.load_dag(dag_id)
    if d is None:
        raise HTTPException(status_code=404, detail=f"dag {dag_id} not found")
    return d


@app.get("/api/dags")
def list_dags(
    limit: int = 50, domain: Optional[str] = None, status: Optional[str] = None
) -> dict:
    pkts = _packets_by_drop()
    out = []
    for p in sorted(_dag_dir().glob("*.json")):
        d = storage.load_dag(p.stem)
        if not d:
            continue
        if domain and d.get("domain") != domain:
            continue
        if status and d.get("status") != status:
            continue
        out.append({
            "dag_id": d["dag_id"],
            "goal": d.get("goal", ""),
            "domain": d.get("domain", ""),
            "type": d.get("type", ""),
            "status": d.get("status", ""),
            "node_count": len(d.get("nodes", [])),
            "source_drop": d.get("source_drop", ""),
            "created_at": pkts.get(d.get("source_drop"), {}).get(
                "created_at", d.get("created_at", "")
            ),
        })
    return {"dags": out[:limit]}


@app.get("/api/packets")
def list_packets(
    limit: int = 200, offset: int = 0,
    domain: Optional[str] = None, status: Optional[str] = None,
) -> dict:
    ps = storage.read_all(storage.PACKETS)
    if domain:
        ps = [p for p in ps if p.get("domain") == domain]
    if status:
        ps = [p for p in ps if p.get("status") == status]
    total = len(ps)
    return {"packets": ps[offset:offset + limit], "total": total}


@app.get("/api/state")
def get_state() -> dict:
    return {
        "recurring": state.list_recurring(),
        "due_today": state.due_recurring(),
        "locked_refs": state.locked_refs(),
    }


@app.get("/api/brief")
def get_brief() -> dict:
    return command_brief.build_brief()


@app.get("/api/entities")
def get_entities(type: Optional[str] = None) -> dict:
    ents = entities.list_all()
    if type:
        ents = [e for e in ents if e.get("type") == type]
    return {"entities": ents}


@app.post("/api/drop", dependencies=[Depends(auth.require_write_token)])
async def post_drop(request: Request) -> dict:
    """Intake valve: catch raw input, run the bouncer + chainer, secure or drop.

    Body: a JSON object carrying the raw text under any of ``raw`` /
    ``rawInput`` / ``text`` (rawInput matches the webhook-snippet field name).
    Optional ``ship: true`` also emits a Mini Ship.

    Always returns HTTP 200 with ``{"status": "secured" | "dropped", ...}`` so
    an upstream webhook does not retry a deliberately-dropped (noise/duplicate)
    payload. Malformed requests get 4xx; a genuine storage fault gets 500.
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — bad/empty JSON body
        raise HTTPException(status_code=400, detail="request body must be JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")

    raw = body.get("raw") or body.get("rawInput") or body.get("text") or ""
    if not isinstance(raw, str):
        raise HTTPException(status_code=400, detail="'raw' must be a string")

    return intake.chain_intake(raw, make_ship=bool(body.get("ship", False)))


# ---------------------------------------------------------------------------
# Mark-off + Checklist (PKT-011 / Brick 1 of the project-lifecycle spine).
#
# The write side of "plan -> advance by hand": a human can check a task off and
# the graph wakes its dependents. The graph logic is NOT reimplemented here —
# completion reuses dag_update.apply_review (dag_update.py:20), which already
# sets status->done, attaches the result, wakes waiting nodes whose deps are
# satisfied, and flips dag.status to complete when nothing runnable remains.
#
# Auth mirrors POST /api/drop: all three writes now require the X-Atlas-Token
# shared secret (Task B, 2026-06-25) via dependencies=[Depends(require_write_token)]
# on the decorators below. See auth.py and PACKETS/011_markoff_and_checklist.md.
# ---------------------------------------------------------------------------


def _find_node(dag: dict, node_id: str) -> Optional[dict]:
    return next((n for n in dag["nodes"] if n["id"] == node_id), None)


# ---------------------------------------------------------------------------
# Per-DAG write serialization (TOCTOU fix).
#
# complete_node load-check-mutate-saves a DAG that each request reads off disk
# independently. The not-done check and the save are not atomic, so two
# concurrent completes on the same node could both pass the check, both call
# apply_review, both save, and both append a `node_completed` audit row —
# violating the spec's "one wins" contract (duplicate audit events; both
# requests return `updates` instead of one getting `already_done`). The on-disk
# DAG stays correct because the transitions are idempotent, but the audit log
# double-counts.
#
# Fix: serialize the whole load->check->mutate->save->append for a given dag_id
# behind a per-DAG lock. A real threading.Lock (not asyncio.Lock) so it also
# holds against the optional daemon thread (server.py:51) that mutates DAGs on a
# separate OS thread. The locked section is await-free, so it never yields the
# event loop while held — no deadlock, no starvation.
# See ~/.claude/rules/common/code-as-furniture.md — bug fixed inline, not documented.
# ---------------------------------------------------------------------------
_dag_locks_guard = threading.Lock()
_dag_locks: dict[str, threading.Lock] = {}


def _dag_lock(dag_id: str) -> threading.Lock:
    """Return the process-wide lock for one dag_id, creating it on first use.

    The guard lock makes the get-or-create itself atomic so two threads racing
    on a never-seen dag_id can't end up with two different locks.
    """
    with _dag_locks_guard:
        lock = _dag_locks.get(dag_id)
        if lock is None:
            lock = threading.Lock()
            _dag_locks[dag_id] = lock
        return lock


def _complete_node_core(dag_id: str, node_id: str, body: dict) -> dict:
    """The serialized load->check->mutate->save->append for one node completion.

    Synchronous and await-free so the whole critical section runs atomically
    under the per-DAG lock. Raises HTTPException for the 404/409 cases exactly
    as the endpoint did before the refactor. Returns the response dict.
    """
    with _dag_lock(dag_id):
        # load the dag the same way GET /api/dag/{dag_id} does (server.py:75-80)
        dag = storage.load_dag(dag_id)
        if dag is None:
            raise HTTPException(status_code=404, detail=f"dag {dag_id} not found")
        node = _find_node(dag, node_id)
        if node is None:
            raise HTTPException(
                status_code=404, detail=f"node {node_id} not found in dag {dag_id}"
            )

        # idempotent: a done node is a no-op, no double-mutation. Inside the lock
        # this is the compare half of an atomic compare-and-set on node status:
        # the loser of a concurrent race re-reads `done` here and stops.
        if node["status"] == "done":
            return {
                "dag_id": dag_id,
                "node": node_id,
                "already_done": True,
                "dag_status": dag["status"],
                "updates": [],
                "ready_now": [n["id"] for n in dispatcher.get_ready_nodes(dag)],
            }

        # you can't check off step 3 while step 1 is still open
        done = {n["id"] for n in dag["nodes"] if n["status"] == "done"}
        unmet = [d for d in node.get("depends_on", []) if d not in done]
        if unmet:
            raise HTTPException(
                status_code=409, detail=f"{node_id} blocked by {unmet}"
            )

        note = body.get("note")
        evidence = body.get("evidence") or []
        if not isinstance(evidence, list):
            raise HTTPException(status_code=400, detail="'evidence' must be a list")
        result: dict[str, Any] = {
            "by": "human",
            "note": note,
            "evidence": evidence,
            "result": body.get("result"),
            "at": clock.now_iso(),
        }
        review = {"mark_node_as": "done", "approved_new_nodes": []}
        # apply_review does the whole advance step: done + wake deps + flip dag.status
        updates = dag_update.apply_review(dag, node, result, review)

        storage.save_dag(dag)  # same persistence graph_engine.py uses (graph_engine.py:235)
        storage.append(storage.DAG_EVENTS, {
            "event": "node_completed", "dag_id": dag_id, "node_id": node_id,
            "by": "human", "at": clock.now_iso(), "updates": updates,
        })
        return {
            "dag_id": dag_id,
            "node": node_id,
            "dag_status": dag["status"],
            "updates": updates,
            "ready_now": [n["id"] for n in dispatcher.get_ready_nodes(dag)],
        }


@app.post("/api/dag/{dag_id}/node/{node_id}/complete",
          dependencies=[Depends(auth.require_write_token)])
async def complete_node(dag_id: str, node_id: str, request: Request) -> dict:
    """Mark a node done, unblock its dependents, and flip the DAG to complete
    when the last node lands. Idempotent on an already-done node; 409 if the
    node's dependencies are not all done yet.

    Body parsing (the handler's only await) happens up front; the actual
    load->check->mutate->save->append is delegated to _complete_node_core, which
    runs under a per-DAG lock so concurrent completes can't double-fire.
    """
    # optional body: {"result": <any>, "evidence": [<str>...], "note": <str>}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — empty/no body is fine for a bare check-off
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")

    return _complete_node_core(dag_id, node_id, body)


@app.get("/api/dag/{dag_id}/checklist")
def get_checklist(dag_id: str) -> dict:
    """Return the DAG as a flat, ordered checklist."""
    dag = storage.load_dag(dag_id)
    if dag is None:
        raise HTTPException(status_code=404, detail=f"dag {dag_id} not found")
    done = {n["id"] for n in dag["nodes"] if n["status"] == "done"}
    return {
        "dag_id": dag_id,
        "goal": dag.get("goal"),
        "status": dag["status"],
        "tasks": [
            {
                "id": n["id"],
                "title": n.get("title", ""),
                "status": n["status"],
                "done_condition": n.get("done_condition", ""),
                "depends_on": n.get("depends_on", []),
                "blocked_by": [d for d in n.get("depends_on", []) if d not in done],
            }
            for n in dag["nodes"]
        ],
    }


@app.post("/api/dag/{dag_id}/node/{node_id}/reopen",
          dependencies=[Depends(auth.require_write_token)])
async def reopen_node(dag_id: str, node_id: str) -> dict:
    """Set a done node back to ready, then re-derive the waiting/ready state of
    every node and the DAG status from scratch. Refused (409) if the node is
    under a do-not-reopen lock (node['do_not_reopen_refs'] intersecting the
    state lock), honoring the same guard graph_engine._enrich respects."""
    dag = storage.load_dag(dag_id)
    if dag is None:
        raise HTTPException(status_code=404, detail=f"dag {dag_id} not found")
    node = _find_node(dag, node_id)
    if node is None:
        raise HTTPException(
            status_code=404, detail=f"node {node_id} not found in dag {dag_id}"
        )
    if node["status"] != "done":
        return {"dag_id": dag_id, "node": node_id, "reopened": False,
                "reason": f"node is {node['status']}, not done", "dag_status": dag["status"]}

    locked = set(state.locked_refs().keys())
    blocked_by_lock = [r for r in node.get("do_not_reopen_refs", []) if r in locked]
    if blocked_by_lock:
        raise HTTPException(
            status_code=409,
            detail=f"{node_id} under do-not-reopen lock {blocked_by_lock}",
        )

    node["status"] = "ready"
    node["result"] = None
    # re-derive ready/waiting + dag status via the shared updater — one source of
    # truth with apply_review. Was hand-rolled here (drift risk); §D fix 2026-06-25.
    dag_update.recompute_states(dag)

    storage.save_dag(dag)
    storage.append(storage.DAG_EVENTS, {
        "event": "node_reopened", "dag_id": dag_id, "node_id": node_id,
        "by": "human", "at": clock.now_iso(),
    })
    return {
        "dag_id": dag_id,
        "node": node_id,
        "reopened": True,
        "dag_status": dag["status"],
        "ready_now": [n["id"] for n in dispatcher.get_ready_nodes(dag)],
    }


def run() -> None:
    import uvicorn
    # Port 3073: 3071 is owned by memory-hub (.claude/launch.json). Two FastAPI
    # services cannot bind the same port; droplist moved off the collision so the
    # atlas-map action layer resolves droplist→3073 (not memory-hub's 3071).
    # See ~/.claude/rules/common/code-as-furniture.md — no broken code left in place.
    uvicorn.run(app, host="127.0.0.1", port=3073)


if __name__ == "__main__":
    run()
