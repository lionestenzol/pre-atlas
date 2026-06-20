"""FastAPI surface for atlas-map-api — port 3072.

Endpoints:
  GET  /                              service info
  GET  /healthz                       up-check
  GET  /map/systems                   list all subsystems
  GET  /map/systems/{name}            one subsystem + neighbors
  GET  /map/locate?file=<path>        which subsystem owns this file?
  GET  /map/neighbors/{name}?hops=N   N-hop neighborhood
  GET  /map/path?from=X&to=Y          directed shortest path
  GET  /map/search?q=<q>&limit=N      fuzzy search across name + purpose
  GET  /map/signals                   live: ports + autostart + retired

The data comes from <repo>/audit/system-index.json + <repo>/atlas-map.json,
loaded on startup. Use POST /admin/reload to re-read from disk after the
builder runs (no auth — local dev only; do not expose this port externally).
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz

from .graph import ServiceGraph
from .loader import MapSnapshot, load_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_loaded()
    yield


app = FastAPI(title="atlas-map-api", version="0.1.0", lifespan=lifespan)

# CORS — the viewer (system-map.html served on :8897, lattice on :3011, etc.)
# needs to query this API from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------- in-memory snapshot, reload-able ----------
_snapshot: MapSnapshot | None = None
_graph: ServiceGraph | None = None
_loaded_at: float = 0.0


def _ensure_loaded() -> tuple[MapSnapshot, ServiceGraph]:
    global _snapshot, _graph, _loaded_at
    if _snapshot is None or _graph is None:
        _snapshot = load_snapshot()
        _graph = ServiceGraph(_snapshot.service_edges, _snapshot.subsystems.keys())
        _loaded_at = time.time()
    return _snapshot, _graph


@app.get("/")
async def root() -> dict[str, Any]:
    snap, g = _ensure_loaded()
    return {
        "name": "atlas-map-api",
        "version": "0.1.0",
        "repo_root": str(snap.repo_root),
        "generated_at": snap.generated_at,
        "loaded_at": _loaded_at,
        "subsystem_count": len(snap.subsystems),
        "edge_count": len(snap.service_edges),
        "endpoints": [
            "/map/systems",
            "/map/systems/{name}",
            "/map/locate?file=<path>",
            "/map/neighbors/{name}?hops=N",
            "/map/path?from=X&to=Y",
            "/map/search?q=<q>&limit=N",
            "/map/signals",
            "/map/viewer?probe=true",
            "/admin/reload",
        ],
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    _ensure_loaded()
    return {"status": "ok"}


@app.post("/admin/reload")
async def reload_snapshot() -> dict[str, Any]:
    """Re-read system-index.json + atlas-map.json from disk."""
    global _snapshot, _graph, _loaded_at
    _snapshot = None
    _graph = None
    snap, _ = _ensure_loaded()
    return {"status": "ok", "loaded_at": _loaded_at, "subsystem_count": len(snap.subsystems)}


@app.get("/map/systems")
async def list_systems(
    group: str | None = Query(None, description="Filter by group (services/apps/tools)"),
    running: bool | None = Query(None, description="Filter by autostart membership"),
) -> dict[str, Any]:
    snap, _ = _ensure_loaded()
    items = [s.to_dict() for s in snap.subsystems.values()]
    if group:
        items = [s for s in items if s["group"] == group]
    if running is not None:
        items = [s for s in items if bool(s["in_autostart"]) == running]
    items.sort(key=lambda s: (s["group"], s["name"]))
    return {"count": len(items), "items": items}


@app.get("/map/systems/{name}")
async def get_system(name: str) -> dict[str, Any]:
    snap, g = _ensure_loaded()
    sub = snap.subsystems.get(name)
    if not sub:
        raise HTTPException(404, f"subsystem '{name}' not found")
    return {
        **sub.to_dict(),
        "retired": name in snap.retired,
        "depends_on": g.neighbors_out(name),
        "depended_on_by": g.neighbors_in(name),
    }


@app.get("/map/locate")
async def locate(file: str = Query(..., description="Repo-relative file path")) -> dict[str, Any]:
    snap, _ = _ensure_loaded()
    norm = file.replace("\\", "/").lstrip("./")
    # Match the longest subsystem path that is a prefix of the file path.
    best: tuple[int, str] | None = None
    for sub in snap.subsystems.values():
        sp = sub.path.replace("\\", "/").rstrip("/") + "/"
        if norm.startswith(sp):
            if best is None or len(sp) > best[0]:
                best = (len(sp), sub.name)
    if not best:
        return {"file": file, "system": None, "match": "none"}
    return {"file": file, "system": best[1], "match": "prefix"}


@app.get("/map/neighbors/{name}")
async def neighbors(name: str, hops: int = Query(1, ge=1, le=5)) -> dict[str, Any]:
    snap, g = _ensure_loaded()
    if name not in snap.subsystems:
        raise HTTPException(404, f"subsystem '{name}' not found")
    return {
        "root": name,
        "hops": hops,
        "by_distance": g.neighborhood(name, hops),
        "out": g.neighbors_out(name),
        "in": g.neighbors_in(name),
    }


@app.get("/map/path")
async def path(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
) -> dict[str, Any]:
    snap, g = _ensure_loaded()
    if from_ not in snap.subsystems:
        raise HTTPException(404, f"'from' subsystem '{from_}' not found")
    if to not in snap.subsystems:
        raise HTTPException(404, f"'to' subsystem '{to}' not found")
    forward = g.shortest_path(from_, to)
    reverse = g.shortest_path(to, from_)
    return {
        "from": from_,
        "to": to,
        "forward": forward,
        "reverse": reverse,
        "reachable": forward is not None or reverse is not None,
    }


@app.get("/map/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
    snap, _ = _ensure_loaded()
    # Build a haystack of "name | purpose | language | group" so fuzz matches
    # broadly. We index per subsystem and rank by combined score.
    rows = []
    for sub in snap.subsystems.values():
        hay = " | ".join(filter(None, [sub.name, sub.purpose, sub.language, sub.framework, sub.group]))
        score = fuzz.WRatio(q, hay)
        rows.append((score, sub))
    rows.sort(key=lambda r: -r[0])
    items = [
        {"score": int(score), **sub.to_dict()}
        for score, sub in rows[:limit] if score > 30
    ]
    return {"query": q, "count": len(items), "items": items}


async def _probe_port(port: int, timeout: float = 0.2) -> bool:
    """Return True if something accepts a TCP connection on 127.0.0.1:port."""
    writer = None
    try:
        fut = asyncio.open_connection("127.0.0.1", port)
        _, writer = await asyncio.wait_for(fut, timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


@app.get("/map/viewer")
async def viewer(
    probe: bool = Query(True, description="Live TCP-probe each port for running state"),
) -> dict[str, Any]:
    """Return the map in the exact shape the system-map.html viewer consumes
    (window.SERVICES + edges), field-adapted from the snapshot. `running` is
    computed live by concurrently probing every ported subsystem; `state` is
    reserved for Wire 2 (dormant/gated/void facts) and is null for now.

    This is the single surface both the visual viewer and the live-refresh
    path compose on — the viewer keeps its baked file previews and overlays
    this live structure+state on top.
    """
    snap, _ = _ensure_loaded()
    subs = list(snap.subsystems.values())

    running_by_name: dict[str, bool] = {}
    if probe:
        ported = [s for s in subs if s.port]
        results = await asyncio.gather(*[_probe_port(int(s.port)) for s in ported])
        running_by_name = {s.name: r for s, r in zip(ported, results)}

    services = []
    for s in subs:
        running = running_by_name.get(s.name, False) if probe else bool(s.in_autostart)
        # Derived health: autostart service that isn't answering is a real problem;
        # a non-autostart service being down is expected (idle).
        if running:
            health = "ok"
        elif s.in_autostart:
            health = "down"  # should be up, isn't
        else:
            health = "idle"
        services.append(
            {
                "name": s.name,
                "group": s.group,
                "port": s.port,
                "running": running,
                "health": health,
                "state": None,  # lifecycle slot (retired/new) — left to the snapshot
                "gov": s.gov,  # Wire 2: {automation, note} governance facts from the trace
                "lang": s.language,
                "framework": s.framework,
                "files": s.file_count,
                "loc": s.total_loc,
                "deps_count": len(s.deps),
                "in_autostart": s.in_autostart,
                "purpose": s.purpose,
                "entry_points": list(s.entry_points),
            }
        )
    services.sort(key=lambda x: (x["group"], x["name"]))
    edges = [{"from": a, "to": b} for (a, b) in snap.service_edges]
    return {
        "generated_at": snap.generated_at,
        "loaded_at": _loaded_at,
        "probed": probe,
        "services": services,
        "edges": edges,
    }


@app.get("/map/signals")
async def signals() -> dict[str, Any]:
    snap, _ = _ensure_loaded()
    autostart = sorted([s.name for s in snap.subsystems.values() if s.in_autostart])
    ported = sorted(
        [{"name": s.name, "port": s.port} for s in snap.subsystems.values() if s.port],
        key=lambda x: x["port"],
    )
    return {
        "subsystem_count": len(snap.subsystems),
        "autostart": autostart,
        "ported": ported,
        "retired": sorted(snap.retired),
        "generated_at": snap.generated_at,
        "loaded_at": _loaded_at,
    }


def run() -> None:
    """Console-script entry point."""
    uvicorn.run("atlas_map_api.server:app", host="127.0.0.1", port=3072, reload=False)


if __name__ == "__main__":
    run()
