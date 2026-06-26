"""DropList HTTP read-only API surface. See BIBLE.md §17 for the protocol."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

# slowapi is optional (Task F): the daily AI cost-ceiling below is pure-stdlib and
# always on; per-IP rate limiting layers on only when slowapi is installed, so the
# zero-extra-deps `[ui]` install still runs. See assemble-first.md.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _limiter: "Limiter | None" = Limiter(key_func=get_remote_address)
except ImportError:  # pragma: no cover - exercised only without the extra
    _limiter = None
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

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
    keys,
    llm,
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
    keys.load_into_env()  # apply any UI-saved provider keys (real env vars still win)
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

# ---------------------------------------------------------------------------
# AI spend guards (Task F). Two layers on /api/ai/*:
#   1. Daily cost ceiling (pure stdlib, always on): sum today's estimated_cost
#      from llm_calls.jsonl; reject once it crosses DROPLIST_DAILY_AI_BUDGET. The
#      real SaaS guard — caps dollars, not just request rate. 0 disables.
#   2. Per-IP rate limit (slowapi, when installed): blunts bursts/abuse.
# Without these a leaked token = unbounded provider spend. See security.md.
# ---------------------------------------------------------------------------
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# Guarded parse: a malformed env value must not crash the server at import.
DAILY_AI_BUDGET = _env_float("DROPLIST_DAILY_AI_BUDGET", 5.0)
# Hard per-request ceiling so one oversized call can't outrun the daily budget.
MAX_AI_TOKENS = _env_int("DROPLIST_MAX_AI_TOKENS", 4096)
_AI_RATE = os.environ.get("DROPLIST_AI_RATE", "30/minute")

if _limiter is not None:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _today_ai_cost() -> float:
    """Sum of today's (UTC) logged AI cost. Matches llm.log_call's timestamp format."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    total = 0.0
    for rec in storage.iter_records(storage.LLM_CALLS):
        if str(rec.get("timestamp", "")).startswith(today):
            try:
                total += float(rec.get("estimated_cost") or 0.0)
            except (TypeError, ValueError):
                continue
    return total


def require_ai_budget() -> None:
    """FastAPI dependency: 429 once today's AI spend hits the ceiling."""
    if DAILY_AI_BUDGET > 0 and _today_ai_cost() >= DAILY_AI_BUDGET:
        raise HTTPException(
            status_code=429,
            detail=f"daily AI budget ${DAILY_AI_BUDGET:.2f} reached; raise DROPLIST_DAILY_AI_BUDGET to continue",
        )


def ai_rate_limit(func):
    """Apply the slowapi per-IP limit when available; a no-op passthrough otherwise."""
    return _limiter.limit(_AI_RATE)(func) if _limiter is not None else func


def _clamp_tokens(v) -> int:
    """Bound user-supplied max_tokens to [1, MAX_AI_TOKENS] so a single oversized
    (or negative) request can't outrun the daily budget guard."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 1024
    return max(1, min(n, MAX_AI_TOKENS))


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
    # Task B: inject the write token. Task C: inject PWA head tags + SW registration
    # here (same mechanism) so both line.html and chain.html become installable with
    # zero edits to the static files.
    inject = (
        f"<script>window.__DL_TOKEN__={json.dumps(auth.current_token())};</script>"
        '<link rel="manifest" href="/manifest.webmanifest">'
        '<meta name="theme-color" content="#0c0e0d">'
        '<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">'
        '<link rel="icon" type="image/png" href="/icons/icon-192.png">'
        "<script>if('serviceWorker' in navigator){window.addEventListener('load',"
        "function(){navigator.serviceWorker.register('/sw.js').catch(function(){});});}</script>"
    )
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    return HTMLResponse(html)


# Task C — PWA install assets. Manifest + service worker are served from the app
# root (SW scope must cover "/"); icons are a static mount. MIME types matter:
# browsers reject a manifest/SW served as text/plain.
@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest() -> FileResponse:
    return FileResponse(_UI_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def pwa_service_worker() -> FileResponse:
    # Service-Worker-Allowed lets a root-scope SW be served from anywhere; here it's
    # already at root, but the header is harmless and future-proofs a /static move.
    return FileResponse(
        _UI_DIR / "sw.js",
        media_type="text/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


_ICONS_DIR = _UI_DIR / "icons"
if _ICONS_DIR.is_dir():
    app.mount("/icons", StaticFiles(directory=str(_ICONS_DIR)), name="icons")


@app.get("/", response_class=HTMLResponse)
def ui_now() -> HTMLResponse:
    """Serve the NOW screen (ui/line.html) — self-wires to GET /api/now."""
    return _serve_ui("line.html")


@app.get("/chain", response_class=HTMLResponse)
def ui_chain() -> HTMLResponse:
    """Serve the DAG/chain view (ui/chain.html) — self-wires to GET /api/dag/sample."""
    return _serve_ui("chain.html")


# ---------------------------------------------------------------------------
# Swappable LLM proxy (Task B, litellm). The UIs used to POST straight to
# api.anthropic.com from the browser — CORS-broken AND a client-side key path.
# These routes hold every provider key server-side (litellm reads them from env)
# and run one provider-agnostic `completion(model=...)`, so the user can pick
# GPT-4o / Gemini / local Llama from a dropdown and NO key ships to the client.
# The response is normalized to the Anthropic shape the UI already parses, so
# nothing in line.html's data.content handling changes. Guarded by the write
# token because it spends money; runs in a threadpool so the blocking SDK call
# never stalls the event loop.
# See assemble-first.md (litellm, not a 2nd HTTP path) + code-as-furniture.md.
# ---------------------------------------------------------------------------


@app.get("/api/ai/models")
def ai_models() -> dict:
    """Models the server can actually run right now (key present, or local Ollama).

    Public read — it leaks no secret, only which providers are configured — so the
    picker can populate before the user authenticates a write."""
    models = llm.available_models()
    return {"models": models, "default": llm.default_model()}


@app.get("/api/ai/keys")
def ai_keys() -> dict:
    """Which providers have a key configured. Booleans only — NEVER the key values."""
    return {"configured": keys.configured()}


@app.post("/api/ai/keys", dependencies=[Depends(auth.require_write_token)])
async def ai_set_key(request: Request) -> Response:
    """BYO-key from the UI. Body {provider, key} — empty key clears it. The key is
    stored server-side (gitignored data dir) + applied to the process env so litellm
    uses it; the response returns only the configured-booleans, never the value.
    Write-token guarded: setting a key is a privileged, money-spending action."""
    body = await request.json()
    provider = (body.get("provider") or "").strip()
    if not keys.set_key(provider, body.get("key") or ""):
        return Response(
            content=json.dumps({"error": f"unknown provider '{provider}'"}).encode(),
            status_code=400, media_type="application/json",
        )
    return {"ok": True, "configured": keys.configured(), "models": llm.available_models()}


def _ai_complete(model: str, system: str | None, messages: list, max_tokens: int) -> tuple[int, bytes]:
    """Blocking litellm completion → (status, Anthropic-shaped JSON bytes). Threadpool."""
    try:
        payload = llm.complete(model=model, messages=messages, system=system, max_tokens=max_tokens, purpose="ui")
        return 200, json.dumps(payload).encode()
    except Exception as e:  # noqa: BLE001 — provider/network error surfaces as 502
        return 502, json.dumps({"error": f"completion failed: {e}"}).encode()


@app.post(
    "/api/ai/complete",
    dependencies=[Depends(auth.require_write_token), Depends(require_ai_budget)],
)
@ai_rate_limit
async def proxy_complete(request: Request) -> Response:
    """Provider-agnostic completion. Body: {model, max_tokens, system, messages}
    where `model` is a litellm id (e.g. ``openai/gpt-4o``, ``ollama/llama3``).
    Returns Anthropic-shaped ``{content:[{type,text}], model, estimated_cost}``."""
    body = await request.json()
    model = (body.get("model") or "").strip()
    if not model:
        return Response(
            content=json.dumps({"error": "model is required"}).encode(),
            status_code=400, media_type="application/json",
        )
    status, out = await run_in_threadpool(
        _ai_complete, model, body.get("system"), body.get("messages") or [], _clamp_tokens(body.get("max_tokens")),
    )
    return Response(content=out, status_code=status, media_type="application/json")


@app.post(
    "/api/ai/anthropic",
    dependencies=[Depends(auth.require_write_token), Depends(require_ai_budget)],
)
@ai_rate_limit
async def proxy_anthropic(request: Request) -> Response:
    """Back-compat alias for any caller still posting the old Anthropic shape —
    routes through the same litellm path, forcing the anthropic/ provider."""
    body = await request.json()
    model = (body.get("model") or "claude-sonnet-4-20250514").strip()
    if "/" not in model:
        model = f"anthropic/{model}"
    status, out = await run_in_threadpool(
        _ai_complete, model, body.get("system"), body.get("messages") or [], _clamp_tokens(body.get("max_tokens")),
    )
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


def run(port: int | None = None, host: str = "127.0.0.1") -> None:
    import uvicorn
    # Port 3073: 3071 is owned by memory-hub (.claude/launch.json). Two FastAPI
    # services cannot bind the same port; droplist moved off the collision so the
    # atlas-map action layer resolves droplist→3073 (not memory-hub's 3071).
    # The desktop wrapper (desktop.py) passes a dynamic free port so two instances
    # don't collide — hence the param + DROPLIST_PORT override, default 3073.
    # See ~/.claude/rules/common/code-as-furniture.md — no broken code left in place.
    if port is None:
        port = int(os.environ.get("DROPLIST_PORT", "3073"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
