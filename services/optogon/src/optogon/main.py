"""Optogon FastAPI server on :3010.

Endpoints per doctrine/04_BUILD_PLAN.md Phase 2:
- POST /session/start       -> create session, return first response
- POST /session/{id}/turn   -> process user turn
- GET  /session/{id}        -> full session state
- GET  /paths               -> list available paths
- GET  /health              -> service health
- GET  /signals             -> emitted signals (debug)
"""
from __future__ import annotations
import json
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import signals as signal_module
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
    store = get_store()
    state = store.create(req.path_id, req.initial_context, entry_node_id=entry_node_id)

    # Kick off: process an initial turn with no message so execute/gate/qualify-with-inference can advance
    state, text, emitted = process_turn(state, path, None)
    state = store.update(state)

    return {
        "session_id": state["session_id"],
        "state": state,
        "response": text,
        "signals": emitted,
    }


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
