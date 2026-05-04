"""Optogon FastAPI server on :3010.

Endpoints per doctrine/04_BUILD_PLAN.md Phase 2:
- POST /session/start          -> create session, return first response
- POST /session/from_sitepull  -> create session pre-loaded from anatomy.json
- POST /session/{id}/turn      -> process user turn
- GET  /session/{id}           -> full session state
- GET  /paths                  -> list available paths
- GET  /health                 -> service health
- GET  /signals                -> emitted signals (debug)
"""
from __future__ import annotations
import json
import os
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pathlib import Path

from . import signals as signal_module
from .adapters.sitepull_adapter import build_context_package, load_context_package
from .config import PATHS_DIR, SCHEMAS_DIR
from .contract_validator import ContractError, validate
from .node_processor import process_turn
from .session_store import get_store

app = FastAPI(title="Optogon", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3006", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_BOOT_TS = time.time()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class StartRequest(BaseModel):
    path_id: str
    initial_context: Optional[dict[str, Any]] = None
    context_package: Optional[dict[str, Any]] = None
    sitepull_audit_dir: Optional[str] = None


class SitepullSessionRequest(BaseModel):
    host: Optional[str] = None
    anatomy_path: Optional[str] = None


_SITEPULL_KEYS = (
    "structure_map",
    "action_inventory",
    "inferred_state",
    "coverage_score",
    "partial",
    "source",
    "captured_at",
    "id",
)


def _flatten_context_package(pkg: dict[str, Any]) -> dict[str, Any]:
    """Flatten a ContextPackage into namespaced system-tier keys."""
    flat: dict[str, Any] = {}
    for key in _SITEPULL_KEYS:
        if key in pkg:
            flat[f"sitepull.{key}"] = pkg[key]
    entry_points = (pkg.get("structure_map") or {}).get("entry_points")
    if entry_points:
        flat["sitepull.entry_points"] = entry_points
    return flat


def _resolve_context_package(req: StartRequest) -> Optional[dict[str, Any]]:
    """Build a ContextPackage from whichever input the caller supplied."""
    if req.context_package is not None:
        validate(req.context_package, "ContextPackage")
        return req.context_package
    if req.sitepull_audit_dir:
        audit_dir = Path(req.sitepull_audit_dir)
        if not audit_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"sitepull_audit_dir does not exist: {audit_dir}",
            )
        return build_context_package(audit_dir)
    return None


class TurnRequest(BaseModel):
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Path loading
# ---------------------------------------------------------------------------
def _load_path(path_id: str) -> dict[str, Any]:
    path_file = PATHS_DIR / f"{path_id}.json"
    if not path_file.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path_id}")
    with path_file.open("r", encoding="utf-8") as f:
        path = json.load(f)
    # Validate against OptogonPath schema
    try:
        validate(path, "OptogonPath")
    except ContractError as e:
        raise HTTPException(status_code=500, detail=f"Path {path_id} invalid: {e}")
    return path


def _list_paths() -> list[dict[str, str]]:
    PATHS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(PATHS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            with f.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            out.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
            })
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, Any]:
    schemas_loaded = 0
    try:
        schemas_loaded = len(list(SCHEMAS_DIR.glob("*.v1.json")))
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime_seconds": round(time.time() - _BOOT_TS, 2),
        "schemas_loaded": schemas_loaded,
    }


@app.get("/paths")
def paths() -> list[dict[str, str]]:
    return _list_paths()


@app.post("/session/start")
def session_start(req: StartRequest) -> dict[str, Any]:
    path = _load_path(req.path_id)
    entry_node_id = (path.get("entry") or {}).get("node_id") or "entry"
    pkg = _resolve_context_package(req)
    system_context = _flatten_context_package(pkg) if pkg else None
    store = get_store()
    state = store.create(
        req.path_id,
        req.initial_context,
        entry_node_id=entry_node_id,
        nodes_total=len(path.get("nodes") or {}),
        system_context=system_context,
    )

    # Kick off: process an initial turn with no message so execute/gate/qualify-with-inference can advance
    state, text, emitted = process_turn(state, path, None)
    state = store.update(state)

    return {
        "session_id": state["session_id"],
        "state": state,
        "response": text,
        "signals": emitted,
    }


@app.post("/session/from_sitepull")
def session_from_sitepull(req: SitepullSessionRequest) -> dict[str, Any]:
    """Create an Optogon session pre-loaded from an anatomy.json capture.

    Body: {"host": "example.com"} resolves via WEB_AUDIT_ROOT.
    Body: {"anatomy_path": "/abs/path/anatomy.json"} uses the path directly.
    """
    if req.anatomy_path:
        anatomy_path = Path(req.anatomy_path)
    elif req.host:
        if "/" in req.host or "\\" in req.host or ".." in req.host or req.host.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid host")
        web_audit_root = os.environ.get("WEB_AUDIT_ROOT", str(Path.home() / "web-audit"))
        anatomy_path = Path(web_audit_root) / ".canvas" / req.host / "anatomy.json"
    else:
        raise HTTPException(status_code=400, detail="Provide 'host' or 'anatomy_path'.")

    if not anatomy_path.exists():
        target = req.host or str(anatomy_path)
        raise HTTPException(
            status_code=404,
            detail=f"anatomy.json not found: {anatomy_path}. Run sitepull capture for {target} first.",
        )

    try:
        pkg = load_context_package(anatomy_path)
    except ContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    system_context = _flatten_context_package(pkg)
    store = get_store()
    state = store.create(
        "__sitepull__",
        entry_node_id="entry",
        nodes_total=0,
        system_context=system_context,
    )
    state = store.update(state)

    return {"session_id": state["session_id"]}


@app.post("/session/{session_id}/turn")
def session_turn(session_id: str, req: TurnRequest) -> dict[str, Any]:
    store = get_store()
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    path = _load_path(state["path_id"])
    state, text, emitted = process_turn(state, path, req.message)
    state = store.update(state)
    return {
        "session_id": session_id,
        "state": state,
        "response": text,
        "signals": emitted,
    }


@app.post("/session/run")
def session_run(req: StartRequest) -> dict[str, Any]:
    """One-shot drive: create + walk turns until closed or stuck on user-input.

    For autonomous callers (Claude Code via codex-delegate skill, scripts,
    automation) that can't sit in a turn-by-turn loop. Caps at 30 internal
    turns to prevent infinite advancement.
    """
    path = _load_path(req.path_id)
    entry_node_id = (path.get("entry") or {}).get("node_id") or "entry"
    pkg = _resolve_context_package(req)
    system_context = _flatten_context_package(pkg) if pkg else None
    store = get_store()
    state = store.create(
        req.path_id,
        req.initial_context,
        entry_node_id=entry_node_id,
        nodes_total=len(path.get("nodes") or {}),
        system_context=system_context,
    )

    # Initial turn (kicks off entry/qualify/execute)
    state, text, emitted_all = process_turn(state, path, None)
    state = store.update(state)

    # Walk forward until closed, asking for user-input, awaiting approval, or hit max turns
    # NOTE: _handle_close sets state["_close_signal"] but does NOT set state["closed_at"]
    # (latent core bug). We detect close via the signal instead.
    def _is_closed(s: dict[str, Any]) -> bool:
        if s.get("_close_signal") or s.get("closed_at"):
            return True
        cur = s.get("current_node")
        ns = (s.get("node_states") or {}).get(cur, {}) if cur else {}
        node_def = (path.get("nodes") or {}).get(cur, {}) if cur else {}
        return node_def.get("type") == "close" and ns.get("status") == "closed"

    MAX_TURNS = 30
    BLOCKING_STATUSES = ("blocked", "unqualified", "awaiting_approval")
    turns = 1
    while turns < MAX_TURNS and not _is_closed(state):
        prev_node = state.get("current_node")
        prev_status = (state.get("node_states") or {}).get(prev_node, {}).get("status")

        # Stop if a qualify node is asking for user input or an approval node
        # is awaiting a human decision - autonomous caller can't answer.
        if prev_status == "awaiting_approval":
            break
        if prev_status == "unqualified" and text:
            break

        state, text, emitted = process_turn(state, path, None)
        state = store.update(state)
        emitted_all = emitted_all + emitted

        new_node = state.get("current_node")
        new_status = (state.get("node_states") or {}).get(new_node, {}).get("status")
        # If we didn't advance and the node is blocked / waiting for input, bail
        if new_node == prev_node and new_status in BLOCKING_STATUSES:
            break
        turns += 1

    # Pull deliverables from action_results so they survive the close-state
    # trim. Last-write-wins by node iteration order: node_states is dict-ordered
    # by insertion (Python 3.7+), and nodes are inserted as they're entered, so
    # later nodes (e.g. retries, multi-execute paths) overwrite earlier values.
    # This is intentional: if the run node fires twice, the terminal result
    # should reflect the latest run, not the first.
    final_outputs: dict[str, Any] = {}
    for node_id, ns in (state.get("node_states") or {}).items():
        for action_id, result in (ns.get("action_results") or {}).items():
            if isinstance(result, dict):
                for key in ("codex_output", "parsed_output", "schema_valid",
                            "schema_errors", "exit_code", "codex_success",
                            "skill", "sandbox", "codex_stderr"):
                    if key in result:
                        final_outputs[key] = result[key]

    return {
        "session_id": state["session_id"],
        "state": state,
        "response": text,
        "signals": emitted_all,
        "outputs": final_outputs,
        "turns_walked": turns,
        "closed": _is_closed(state),
    }


@app.get("/session/{session_id}")
def session_get(session_id: str) -> dict[str, Any]:
    store = get_store()
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return state


@app.get("/signals")
def signals_list(since: Optional[str] = None) -> list[dict[str, Any]]:
    return signal_module.all_signals(since=since)


@app.exception_handler(ContractError)
def contract_error_handler(request: Request, exc: ContractError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=400,
        content={"error": "contract_violation", "contract": exc.contract_name, "details": exc.errors},
    )
