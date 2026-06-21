"""DropList HTTP read-only API surface. See BIBLE.md §17 for the protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import (  # noqa: F401 — atlas_signal/dag_builder kept for v2 mutation surface
    atlas_signal,
    command_brief,
    dag_builder,
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

app = FastAPI(title="DropList API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _packets_by_drop() -> dict:
    return {p.get("drop_id", ""): p for p in storage.read_all(storage.PACKETS)}


def _dag_dir() -> Path:
    return Path(storage.DATA_DIR) / "dags"


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


@app.post("/api/drop")
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


def run() -> None:
    import uvicorn
    # Port 3073: 3071 is owned by memory-hub (.claude/launch.json). Two FastAPI
    # services cannot bind the same port; droplist moved off the collision so the
    # atlas-map action layer resolves droplist→3073 (not memory-hub's 3071).
    # See ~/.claude/rules/common/code-as-furniture.md — no broken code left in place.
    uvicorn.run(app, host="127.0.0.1", port=3073)


if __name__ == "__main__":
    run()
