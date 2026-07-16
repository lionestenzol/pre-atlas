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
  GET  /route?q=<q>&limit=N           dispatch: which capability answers this intent?

The data comes from <repo>/audit/system-index.json + <repo>/atlas-map.json,
loaded on startup. Use POST /admin/reload to re-read from disk after the builder
runs. All POST endpoints require an X-Atlas-Token header (see auth.py); GET reads
are open. Bind 127.0.0.1 only — do not expose this port externally.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from rapidfuzz import fuzz

from . import auth
from . import call_counter
from . import describe as describe_mod
from . import gateway as gateway_mod
from . import items as items_backbone
from . import launcher
from . import receipt_store
from . import route as route_mod
from . import seam as seam_mod
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
# The same list gates the token handout (origin defense-in-depth), so it's a
# module constant both the middleware and /admin/write-token consult.
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3011", "http://127.0.0.1:3011",   # lattice
    "http://localhost:8897", "http://127.0.0.1:8897",   # audit-map
    "http://localhost:8888", "http://127.0.0.1:8888",   # atlas-shell
    "http://localhost:3006", "http://127.0.0.1:3006",   # inpact
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
            "/map/launchables?probe=true",
            "POST /map/start/{name}",
            "POST /map/stop/{name}",
            "POST /map/restart/{name}",
            "POST /map/launch/{name}",
            "POST /map/halt/{name}",
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
async def write_token(
    request: Request,
    scope: str | None = Query(None, description="Capability scope: boot | items"),
) -> dict[str, str]:
    """Hand a SCOPED, least-privilege write token to a CORS-trusted viewer origin.

    A static viewer can't read the gitignored .atlas-write-token off disk, so it
    bootstraps a secret here. Two guards, layered:

    1. Scope (least privilege): this returns a per-capability token, NEVER the
       root token. `scope=boot` => may POST /map/* only (start/stop/restart/
       launch/halt); `scope=items` => may POST /items/* only. Neither can touch
       /admin/*. So a leaked handout token can't do everything root can.
    2. Origin (defense-in-depth, NOT authentication): the request's Origin header
       must be a known viewer origin. This blocks the no-Origin `curl` that
       previously walked off with the root token. It is SPOOFABLE by a determined
       non-browser caller (Origin is a client-set header), so it is a hardening
       layer on top of scope, not a real authenticator.

    Unknown/missing scope => 400. Disallowed/absent Origin => 403. The root token
    is never exposed here; processes with filesystem access still read the file
    directly (unchanged), and the CLI uses that file, not this endpoint.
    """
    origin = request.headers.get("origin")
    if not origin or origin not in ALLOWED_ORIGINS:
        raise HTTPException(403, "origin not allowed")
    try:
        token = auth.scoped_token(scope or "")
    except KeyError:
        raise HTTPException(400, "unknown or missing scope (expected: boot | items)")
    return {"token": token, "scope": scope or ""}


@app.post("/admin/reload", dependencies=[Depends(auth.require_write_token)])
async def reload_snapshot() -> dict[str, Any]:
    """Re-read system-index.json + atlas-map.json from disk."""
    global _snapshot, _graph, _loaded_at
    _snapshot = None
    _graph = None
    auth.reload_role_tokens()  # pick up rotated/revoked role tokens without a restart
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


def _as_int(p: Any) -> int | None:
    """Coerce a launch.json port to int, or None if it isn't numeric. Keeps the
    listing fail-soft (matches launcher.port_alive) — one malformed entry degrades
    to a port-less row instead of 500-ing the whole list."""
    try:
        return int(p)
    except (ValueError, TypeError):
        return None


@app.get("/map/launchables")
async def launchables(
    probe: bool = Query(True, description="Live TCP-probe each port for running state"),
) -> dict[str, Any]:
    """Everything that can be booted, straight from .claude/launch.json — the
    authoritative allowlist the setup UI boots from.

    Unlike /map/viewer (which only covers ported subsystems present in the
    snapshot) this includes the UI-only servers — lattice, cycleboard, hydra,
    droplist-ui, … — that the setup page must be able to start. Each item is
    keyed by its launch.json NAME, the exact key POST /map/launch/{name} and
    POST /map/halt/{name} take. `running` is a live loopback probe when
    probe=true, else null. `shared_with` lists OTHER launch names bound to the
    same port (a TCP probe can't tell them apart, and halting one halts both —
    the UI surfaces this). Read-only; no auth.
    """
    snap, _ = _ensure_loaded()
    cfgs = launcher.load_launch_configs(snap.repo_root)
    ports = sorted({p for c in cfgs if (p := _as_int(c.get("port"))) is not None})
    names_by_port: dict[int, list[str]] = {}
    for c in cfgs:
        p = _as_int(c.get("port"))
        if p is not None:
            names_by_port.setdefault(p, []).append(str(c.get("name")))
    running_by_port: dict[int, bool] = {}
    if probe and ports:
        results = await asyncio.gather(*[_probe_port(p) for p in ports])
        running_by_port = dict(zip(ports, results))
    items = []
    for c in cfgs:
        p = _as_int(c.get("port"))
        name = c.get("name")
        running = running_by_port.get(p, False) if (probe and p is not None) else None
        shared = [n for n in names_by_port.get(p, []) if n != name] if p is not None else []
        items.append(
            {
                "name": name,
                "port": c.get("port"),  # raw value preserved (degraded row keeps its label)
                "running": running,
                "self": p is not None and p == launcher.SELF_PORT,
                "shared_with": shared,
            }
        )
    # Running first, then alphabetical — so the UI shows what's live up top.
    items.sort(key=lambda x: (x["running"] is not True, str(x["name"] or "")))
    return {"count": len(items), "items": items, "probed": probe}


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


@app.post("/map/halt/{name}", dependencies=[Depends(auth.require_write_token)])
async def halt_launch(name: str) -> dict[str, Any]:
    """Stop a launch.json entry BY NAME — the symmetric partner to /map/launch.

    /map/stop/{name} is keyed by snapshot *subsystem*, so it can't stop the
    UI-only servers (lattice, hydra, droplist-ui, …) that aren't in the snapshot.
    This resolves name -> port via launch.json and stops whatever holds that
    port. SELF_PORT is refused inside stop_on_port. Allowlist = launch.json
    (404 for unknown names)."""
    snap, _ = _ensure_loaded()
    cfgs = launcher.load_launch_configs(snap.repo_root)
    cfg = next((c for c in cfgs if c.get("name") == name), None)
    if cfg is None:
        raise HTTPException(404, f"no launch.json entry named '{name}'")
    port = cfg.get("port")
    pi = _as_int(port)
    # stop_on_port kills every PID on the port; if another launch entry shares it
    # (e.g. droplist-ui & triangulation both on 3074) that one dies too. Surface
    # it rather than silently collateral-killing. NOTE: a name-scoped kill (match
    # by cwd/cmdline) is the deeper fix — deferred until the launch.json port
    # collision itself is resolved (owner: Bruke). See code-as-furniture.md.
    shared = [c.get("name") for c in cfgs if c.get("name") != name and pi is not None and _as_int(c.get("port")) == pi]
    result = launcher.stop_on_port(port)
    if shared:
        result["shared_with"] = shared
        result["warning"] = f"port {port} is shared — also stopped: {', '.join(shared)}"
    return {"action": "halt", "name": name, **result}


@app.get("/map/surfaces")
async def map_surfaces() -> dict[str, Any]:
    """Every visual surface (HTML UI) in the repo, mapped to its served URL +
    mtime + group. The monitor wall reads this so it shows ALL screens."""
    snap, _ = _ensure_loaded()
    return surfaces_mod.all_surfaces(snap.repo_root)


@app.get("/items")
async def items(source: str | None = Query(None, description="Filter to one source: droplist|cycleboard|inpact|festival")) -> dict[str, Any]:
    """The item backbone (brick 1): one unified feed of every surface's items.

    Aggregates droplist packets/entities, cycleboard cards, inpact projects, and
    fest festivals into a single {id, source, kind, title, status, updated} shape
    — so all your stuff is visible in one place for the first time. Read-only,
    fail-soft.
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
    live: bool = Query(False, description="Probe the surface's public health read to fill `state`"),
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
    if live:
        form["state"] = await gateway_mod.fetch_state(snap, surface)
    if format == "text":
        return PlainTextResponse(describe_mod.render_text(form))
    return form


@app.get("/route")
async def route_endpoint(
    q: str = Query(..., min_length=1, description="Free-text intent, e.g. 'where am I' or 'run autopilot'"),
    limit: int = Query(5, ge=1, le=20),
    role: str | None = Query(None, description="Request a NARROWER preview role (cannot escalate past your token)"),
    x_atlas_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Layer-4: pick which declared capability best answers a free-text intent —
    the dispatch layer in front of /describe and /call (the "librarian").

    Ranks over exactly what /describe would show THIS caller — same token-derived
    role, same redaction ladder — so it can never surface a capability outside the
    caller's clearance. Read-only selection only: it never invokes anything, it
    only names a (surface, capability) pair for the caller to pass to /call. Below
    a confidence threshold `confident` is false and `matches` is a shortlist to
    choose from rather than a single dispatch.
    """
    snap, _ = _ensure_loaded()
    token_role = describe_mod.resolve_role(auth.resolve_caller_role(x_atlas_token, snap.repo_root))
    effective = describe_mod.narrow_role(token_role, role)
    return route_mod.route(snap.repo_root, effective, q, limit, secret=auth.current_token())


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
    # Gateway-level refusals (enforcement / resolution) surface as HTTP errors; a
    # reached invocation returns its normalized envelope verbatim, even when the
    # upstream itself failed (the envelope's own `ok`/`status` carry that).
    if result.get("refusal"):
        raise HTTPException(result.get("code", 400), result["error"])
    return result


@app.get("/map/calls")
async def call_traffic(
    dark: bool = Query(False, description="Only list DECLARED capabilities with zero recorded calls"),
) -> dict[str, Any]:
    """Live-traffic report over the capability registry: for every (surface,
    capability), how many times has /call, /seam/call, or the MCP atlas_call
    actually reached it. Answers "which capabilities are dark" — a static
    /describe form can't tell you that, since declaring a capability says
    nothing about whether anyone has ever invoked it.

    dark=true flips this to a punch list: every capability declared in a
    surface's overlay with NO recorded row at all (never even attempted).
    """
    snap, _ = _ensure_loaded()
    called = call_counter.get_counts(snap.repo_root)
    if not dark:
        return {"calls": called}
    called_keys = {(r["surface"], r["capability"]) for r in called}
    dark_caps: list[dict[str, str]] = []
    for surface in describe_mod.described_surfaces(snap.repo_root):
        overlay = describe_mod.load_overlay(snap.repo_root, surface)
        if overlay is None:
            continue
        for cap in overlay.capabilities:
            if (surface, cap.id) not in called_keys:
                dark_caps.append({"surface": surface, "capability": cap.id, "lifecycle": overlay.lifecycle})
    return {"dark_count": len(dark_caps), "dark": dark_caps}


@app.post("/seam/call")
async def seam_call_endpoint(
    surface: str = Body(...),
    capability: str = Body(...),
    args: dict[str, Any] | None = Body(default=None),
    sha256: str | None = Body(default=None),
    run_id: str | None = Body(default=None),
    x_atlas_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """The perceive -> compile -> carry seam's front door: invoke any tool capability
    and ALWAYS get back ONE normalized Receipt (seam.v1), keyed on a content-address.

    Unlike /call (which raises an HTTP error on a gateway refusal), this folds
    refusal, reached-but-failed, and success into a single Receipt shape — so a
    downstream stage reads `status` only: 'error' carries the reason in `error`,
    'ok' carries the tool's parsed payload in `data` plus the `sha256` join key. A
    caller-supplied `sha256` (the known join key for this artifact) is authoritative;
    otherwise it is lifted from the tool's own receipt when present.

    Every Receipt is persisted to the durable store (receipt_store.py), tagged with
    `run_id` — the eventual LangGraph `thread_id` (docs/LANGGRAPH_SKILL_LATTICE_PLAN.md,
    Seq 1). Omit `run_id` on the first call of a chain; the response echoes back the
    one used (generated if you didn't supply it) so later calls can pass it forward
    and land in the same group. Read a chain back via GET /seam/receipts?run_id=...
    """
    snap, _ = _ensure_loaded()
    env = await gateway_mod.call_capability(snap, surface, capability, args, x_atlas_token)
    if "surface" not in env:  # gateway refusals carry no surface — stamp the requested one
        env = {**env, "surface": surface}
    receipt = seam_mod.Receipt.from_envelope(env, sha256=sha256)
    resolved_run_id = run_id or uuid.uuid4().hex
    receipt_store.append(snap.repo_root, resolved_run_id, receipt.model_dump())
    return {"run_id": resolved_run_id, **receipt.model_dump()}


@app.get("/seam/receipts")
async def seam_receipts_endpoint(
    run_id: str = Query(..., description="The run_id from a prior /seam/call response"),
) -> dict[str, Any]:
    """Read back every Receipt persisted under one run_id — the durable trace a
    crashed chain resumes from (docs/LANGGRAPH_SKILL_LATTICE_PLAN.md, Seq 1)."""
    snap, _ = _ensure_loaded()
    return {"run_id": run_id, "receipts": receipt_store.read(snap.repo_root, run_id)}


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
