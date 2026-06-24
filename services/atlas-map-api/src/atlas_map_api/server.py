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
loaded on startup. Use POST /admin/reload to re-read from disk after the builder
runs. All POST endpoints require an X-Atlas-Token header (see auth.py); GET reads
are open. Bind 127.0.0.1 only — do not expose this port externally.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from rapidfuzz import fuzz

from . import auth
from . import describe as describe_mod
from . import gateway as gateway_mod
from . import items as items_backbone
from . import launcher
from . import surfaces as surfaces_mod
from .graph import ServiceGraph
from .loader import MapSnapshot, load_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    snap, _ = _ensure_loaded()
    # Resolve (and, if absent, generate + persist) the write token at startup so
    # the .atlas-write-token file exists for consumers (CLI, viewer) to read.
    auth.load_or_create_token(snap.repo_root)
    yield


app = FastAPI(title="atlas-map-api", version="0.1.0", lifespan=lifespan)

# CORS — the viewer queries this API from a different origin. Now that the API
# has process start/stop/restart endpoints, allow_origins is restricted to the
# known local viewer origins (was "*") so a malicious page can't drive services.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3011", "http://127.0.0.1:3011",   # lattice
        "http://localhost:8897", "http://127.0.0.1:8897",   # audit-map
        "http://localhost:8888", "http://127.0.0.1:8888",   # atlas-shell
        "http://localhost:3006", "http://127.0.0.1:3006",   # inpact
    ],
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
            "/describe",
            "/describe/{surface}?role=R&format=json|text",
            "/map/viewer?probe=true",
            "POST /map/start/{name}",
            "POST /map/stop/{name}",
            "POST /map/restart/{name}",
            "POST /map/launch/{name}",
            "POST /items/{item_id}/status",
            "GET /admin/write-token",
            "POST /admin/reload",
        ],
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    _ensure_loaded()
    return {"status": "ok"}


@app.get("/admin/write-token")
async def write_token() -> dict[str, str]:
    """Hand the write token to a CORS-trusted viewer origin.

    The static lattice viewer can't read the gitignored .atlas-write-token off
    disk, so it bootstraps the secret here. CORS (allow_origins) restricts which
    browser origins can read this response — a DNS-rebind tab at a foreign origin
    cannot. Local processes with filesystem access can read the file directly, so
    this endpoint exposes nothing they couldn't already obtain.
    """
    return {"token": auth.current_token()}


@app.post("/admin/reload", dependencies=[Depends(auth.require_write_token)])
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


def _require_subsystem(name: str) -> Any:
    snap, _ = _ensure_loaded()
    sub = snap.subsystems.get(name)
    if not sub:
        raise HTTPException(404, f"subsystem '{name}' not found")
    return snap, sub


@app.post("/map/start/{name}", dependencies=[Depends(auth.require_write_token)])
async def start_service(name: str) -> dict[str, Any]:
    """Start a stopped service by spawning its launch.json-defined command.

    The request only names a known subsystem; the actual command is resolved
    subsystem -> port -> launch.json config and spawned verbatim (see launcher).
    """
    snap, sub = _require_subsystem(name)
    cfg = launcher.config_for_port(snap.repo_root, sub.port)
    if cfg is None:
        raise HTTPException(
            422,
            f"no launch.json config for '{name}'"
            + (f" (port {sub.port})" if sub.port else " (no port — cannot be started)"),
        )
    return {"action": "start", "subsystem": name, **launcher.start_from_config(cfg, snap.repo_root)}


@app.post("/map/stop/{name}", dependencies=[Depends(auth.require_write_token)])
async def stop_service(name: str) -> dict[str, Any]:
    """Stop a running service by terminating the process on its port.

    Mirrors start's allowlist guard: only stop services that have a launch.json
    config, so we never kill a process atlas-map-api has no business managing.
    """
    snap, sub = _require_subsystem(name)
    if launcher.config_for_port(snap.repo_root, sub.port) is None:
        raise HTTPException(422, f"no launch.json config for '{name}' — refusing to stop an unmanaged process")
    return {"action": "stop", "subsystem": name, **launcher.stop_on_port(sub.port)}


@app.post("/map/restart/{name}", dependencies=[Depends(auth.require_write_token)])
async def restart_service(name: str) -> dict[str, Any]:
    """Stop then start a service (best-effort stop, then spawn)."""
    snap, sub = _require_subsystem(name)
    cfg = launcher.config_for_port(snap.repo_root, sub.port)
    if cfg is None:
        raise HTTPException(422, f"no launch.json config for '{name}'")
    stop_result = launcher.stop_on_port(sub.port)
    # terminate() is graceful — wait (bounded) for the port to actually free so
    # start_from_config's idempotency check doesn't see it "already running".
    for _ in range(20):
        if not launcher.port_alive(sub.port):
            break
        await asyncio.sleep(0.15)
    start_result = launcher.start_from_config(cfg, snap.repo_root)
    return {"action": "restart", "subsystem": name, "stop": stop_result, "start": start_result}


@app.get("/map/surfaces")
async def map_surfaces() -> dict[str, Any]:
    """Every visual surface (HTML UI) in the repo, mapped to its served URL +
    mtime + group. The monitor wall reads this so it shows ALL screens."""
    snap, _ = _ensure_loaded()
    return surfaces_mod.all_surfaces(snap.repo_root)


@app.get("/items")
async def items(source: str | None = Query(None, description="Filter to one source: droplist|cycleboard|inpact")) -> dict[str, Any]:
    """The item backbone (brick 1): one unified feed of every surface's items.

    Aggregates droplist packets/entities, cycleboard cards, and inpact projects
    into a single {id, source, kind, title, status, updated} shape — so all your
    stuff is visible in one place for the first time. Read-only, fail-soft.
    """
    snap, _ = _ensure_loaded()
    return items_backbone.all_items(snap.repo_root, source)


@app.post("/items/{item_id}/status", dependencies=[Depends(auth.require_write_token)])
async def set_item_status_endpoint(item_id: str, status: str = Body(..., embed=True)) -> dict[str, Any]:
    """Write-through (brick 3): set a backbone item's status in its SOURCE store.

    Only droplist packets are writable; every other source returns 422. The
    write is atomic + backed up + field-preserving (see items.set_item_status).
    """
    snap, _ = _ensure_loaded()
    result = items_backbone.set_item_status(snap.repo_root, item_id, status)
    if not result.get("ok"):
        raise HTTPException(422, result.get("error", "write-through failed"))
    return {"action": "set_status", "item": item_id, **result}


@app.post("/map/launch/{name}", dependencies=[Depends(auth.require_write_token)])
async def launch_config(name: str) -> dict[str, Any]:
    """Start a launch.json entry by its NAME — covers UI servers (lattice,
    cycleboard, droplist-ui, …) that aren't ported subsystems and so can't be
    reached by /map/start. Idempotent (won't double-spawn). Allowlist = launch.json."""
    snap, _ = _ensure_loaded()
    cfg = next((c for c in launcher.load_launch_configs(snap.repo_root) if c.get("name") == name), None)
    if cfg is None:
        raise HTTPException(404, f"no launch.json entry named '{name}'")
    return {"action": "launch", "name": name, **launcher.start_from_config(cfg, snap.repo_root)}


@app.get("/items/{item_id}/workflow")
async def item_workflow(item_id: str) -> dict[str, Any]:
    """A droplist packet's DAG (steps + depends_on edges + states) — the flow
    behind a flat item, for the workflow viewer. Read-only, droplist-only."""
    snap, _ = _ensure_loaded()
    result = items_backbone.get_workflow(snap.repo_root, item_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "workflow not found"))
    return result


@app.get("/describe")
async def describe_index() -> dict[str, Any]:
    """Discovery: which roles exist, and which surfaces have declared themselves.

    The roles are the 'test-takers'; each surface listed here will hand a
    different form to each role via /describe/{surface}.
    """
    snap, _ = _ensure_loaded()
    return {
        "roles": [r.to_dict() for r in describe_mod.ROLES.values()],
        "default_role": describe_mod.DEFAULT_ROLE,
        "surfaces": describe_mod.described_surfaces(snap.repo_root),
    }


@app.get("/describe/{surface}")
async def describe_surface_endpoint(
    surface: str,
    role: str | None = Query(None, description="Request a NARROWER preview role (cannot escalate past your token)"),
    format: str = Query("json", description="json | text"),
    x_atlas_token: str | None = Header(default=None),
) -> Any:
    """The headless, caller-scoped self-description of one surface — its 'form'.

    The caller's role is DERIVED from their X-Atlas-Token (no token => anon). The
    `role` query param may only *narrow* that role (preview a lower form), never
    escalate it — so `?role=root` from an unauthenticated caller still yields the
    anon form. Higher-criticality capabilities are progressively redacted unless
    cleared; criticality>=2 redactions carry an existence proof. Pass format=text
    for the screen-reader / CLI / TTS narration of the same descriptor.
    """
    snap, _ = _ensure_loaded()
    overlay = describe_mod.load_overlay(snap.repo_root, surface)
    if overlay is None:
        raise HTTPException(404, f"surface '{surface}' has not declared a self-description overlay")
    token_role = describe_mod.resolve_role(auth.resolve_caller_role(x_atlas_token, snap.repo_root))
    effective = describe_mod.narrow_role(token_role, role)
    form = describe_mod.describe_surface(overlay, effective, secret=auth.current_token())
    if format == "text":
        return PlainTextResponse(describe_mod.render_text(form))
    return form


@app.post("/call")
async def call_endpoint(
    surface: str = Body(...),
    capability: str = Body(...),
    args: dict[str, Any] | None = Body(default=None),
    x_atlas_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Layer-3 gateway: invoke a service capability BY NAME through one front door.

    Access is enforced by the registry — you can only call a capability your own
    /describe form shows (not locked, not redacted). Resolves surface->port and
    proxies the declared route to the live service. Read-only http surfaces only
    in this brick; writes gated (DESCRIBE_GATEWAY_WRITES=1), cli/ui not proxyable.
    """
    snap, _ = _ensure_loaded()
    result = await gateway_mod.call_capability(snap, surface, capability, args, x_atlas_token)
    # Gateway-level failures (enforcement / resolution) carry `error` and no
    # `response`; a proxied upstream reply always carries `response` and is
    # returned verbatim even if the upstream status was non-2xx.
    if "error" in result and "response" not in result:
        raise HTTPException(result.get("code", 400), result["error"])
    return result


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
