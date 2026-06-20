"""FastMCP wrapper — exposes the system-map graph as Claude tools.

Mirrors the search-stack MCP pattern. Direct-imports the loader + graph so the
HTTP server (`atlas-map-api`) does NOT need to be running for these tools to
work. The snapshot is cached in-process; call `atlas_reload` after a builder
re-run to pick up changes.

Tools (one per /map/* endpoint, plus reload):
  atlas_where     — which subsystem owns the current working directory?
  atlas_locate    — which subsystem owns a given file path?
  atlas_neighbors — N-hop dependency neighborhood
  atlas_path      — shortest directed dependency path (both ways)
  atlas_search    — fuzzy match across name + purpose + language + framework
  atlas_list      — list subsystems (filter by group or autostart)
  atlas_show      — detail for one subsystem (+ depends_on / depended_on_by)
  atlas_status    — live signals: ports + autostart + retired
  atlas_reload    — re-read snapshot files from disk
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from rapidfuzz import fuzz

from .graph import ServiceGraph
from .loader import MapSnapshot, load_snapshot

mcp = FastMCP("atlas-map")

# In-process snapshot cache. Reload via the atlas_reload tool.
_snapshot: Optional[MapSnapshot] = None
_graph: Optional[ServiceGraph] = None
_loaded_at: float = 0.0


def _ensure() -> tuple[MapSnapshot, ServiceGraph]:
    global _snapshot, _graph, _loaded_at
    if _snapshot is None or _graph is None:
        _snapshot = load_snapshot()
        _graph = ServiceGraph(_snapshot.service_edges, _snapshot.subsystems.keys())
        _loaded_at = time.time()
    return _snapshot, _graph


def _to_repo_relative(path: str, repo_root: Path) -> str:
    """Mirror of atlas_cli.client.to_repo_relative — accepts absolute, repo-rel,
    or cwd-rel forms; returns a POSIX repo-relative string."""
    p = Path(path)
    if p.is_absolute():
        p = p.resolve()
        try:
            return str(p.relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")
    norm = str(p).replace("\\", "/")
    if (repo_root / p).exists() or not (Path.cwd() / p).exists():
        return norm
    resolved = (Path.cwd() / p).resolve()
    try:
        return str(resolved.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def _locate_internal(file: str, snap: MapSnapshot) -> dict:
    """Same logic as the HTTP /map/locate endpoint — longest-prefix match."""
    norm = file.replace("\\", "/").lstrip("./")
    best: Optional[tuple[int, str]] = None
    for sub in snap.subsystems.values():
        sp = sub.path.replace("\\", "/").rstrip("/") + "/"
        if norm.startswith(sp):
            if best is None or len(sp) > best[0]:
                best = (len(sp), sub.name)
    if not best:
        return {"file": file, "system": None, "match": "none"}
    return {"file": file, "system": best[1], "match": "prefix"}


# ---------------- TOOLS ----------------


@mcp.tool()
async def atlas_where() -> dict:
    """Which Pre Atlas subsystem owns the current working directory?

    Returns:
        {cwd, repo_root, system, match} — system is None if cwd is outside any subsystem.
    """
    snap, _ = _ensure()
    cwd = Path.cwd().resolve()
    repo_root = snap.repo_root
    try:
        rel = str(cwd.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return {"cwd": str(cwd), "repo_root": str(repo_root), "system": None, "match": "outside_repo"}
    probe = (rel.rstrip("/") + "/.") if rel and rel != "." else "."
    result = _locate_internal(probe, snap)
    return {"cwd": str(cwd), "repo_root": str(repo_root), "rel": rel, **result}


@mcp.tool()
async def atlas_locate(file: str) -> dict:
    """Which subsystem owns this file? Accepts absolute, repo-relative, or cwd-relative paths.

    Args:
        file: Any file path (e.g. "services/delta-kernel/src/api/server.ts" or "C:/abs/path.py").

    Returns:
        {file, system, match} — system is None if no subsystem prefix matches.
    """
    snap, _ = _ensure()
    rel = _to_repo_relative(file, snap.repo_root)
    return _locate_internal(rel, snap)


@mcp.tool()
async def atlas_neighbors(name: str, hops: int = 1) -> dict:
    """N-hop dependency neighborhood for a subsystem.

    Args:
        name: Subsystem name (e.g. "delta-kernel").
        hops: 1-5. 1 = direct deps + dependents; 2 includes deps-of-deps; etc.

    Returns:
        {root, hops, out: [...], in: [...], by_distance: {"0": [...], "1": [...], ...}}
    """
    snap, g = _ensure()
    if name not in snap.subsystems:
        return {"error": f"subsystem '{name}' not found", "root": name}
    hops = max(1, min(5, hops))
    return {
        "root": name,
        "hops": hops,
        "by_distance": g.neighborhood(name, hops),
        "out": g.neighbors_out(name),
        "in": g.neighbors_in(name),
    }


@mcp.tool()
async def atlas_path(from_system: str, to_system: str) -> dict:
    """Shortest directed dependency path between two subsystems, in both directions.

    Args:
        from_system: Source subsystem name.
        to_system: Target subsystem name.

    Returns:
        {from, to, forward: [...] | None, reverse: [...] | None, reachable: bool}
    """
    snap, g = _ensure()
    if from_system not in snap.subsystems:
        return {"error": f"'from' subsystem '{from_system}' not found"}
    if to_system not in snap.subsystems:
        return {"error": f"'to' subsystem '{to_system}' not found"}
    fwd = g.shortest_path(from_system, to_system)
    rev = g.shortest_path(to_system, from_system)
    return {
        "from": from_system,
        "to": to_system,
        "forward": fwd,
        "reverse": rev,
        "reachable": fwd is not None or rev is not None,
    }


@mcp.tool()
async def atlas_search(query: str, limit: int = 10) -> dict:
    """Fuzzy match across subsystem name + purpose + language + framework + group.

    Args:
        query: Free-text query (e.g. "preview", "auth", "ingestion").
        limit: 1-50 results.

    Returns:
        {query, count, items: [{score, name, purpose, group, language, port, ...}]}
    """
    snap, _ = _ensure()
    limit = max(1, min(50, limit))
    rows = []
    for sub in snap.subsystems.values():
        hay = " | ".join(filter(None, [sub.name, sub.purpose, sub.language, sub.framework, sub.group]))
        score = fuzz.WRatio(query, hay)
        rows.append((score, sub))
    rows.sort(key=lambda r: -r[0])
    items = [{"score": int(score), **sub.to_dict()} for score, sub in rows[:limit] if score > 30]
    return {"query": query, "count": len(items), "items": items}


@mcp.tool()
async def atlas_list(group: Optional[str] = None, running: Optional[bool] = None) -> dict:
    """List subsystems with optional filters.

    Args:
        group: Filter by "services", "apps", "tools", etc.
        running: If true, only autostart subsystems; if false, only non-autostart.

    Returns:
        {count, items: [{name, group, language, port, loc, in_autostart, ...}]}
    """
    snap, _ = _ensure()
    items = [s.to_dict() for s in snap.subsystems.values()]
    if group:
        items = [s for s in items if s.get("group") == group]
    if running is not None:
        items = [s for s in items if bool(s.get("in_autostart")) == running]
    items.sort(key=lambda s: (s.get("group") or "", s.get("name") or ""))
    return {"count": len(items), "items": items}


@mcp.tool()
async def atlas_show(name: str) -> dict:
    """Detail for one subsystem, including dependency neighbors.

    Args:
        name: Subsystem name.

    Returns:
        Full subsystem record + retired flag + depends_on + depended_on_by.
    """
    snap, g = _ensure()
    sub = snap.subsystems.get(name)
    if not sub:
        return {"error": f"subsystem '{name}' not found"}
    return {
        **sub.to_dict(),
        "retired": name in snap.retired,
        "depends_on": g.neighbors_out(name),
        "depended_on_by": g.neighbors_in(name),
    }


@mcp.tool()
async def atlas_status() -> dict:
    """Live signals snapshot: subsystem count, ported services, autostart membership, retired set.

    Returns:
        {subsystem_count, autostart: [...], ported: [{name, port}, ...], retired: [...], generated_at, loaded_at}
    """
    snap, _ = _ensure()
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


@mcp.tool()
async def atlas_reload() -> dict:
    """Re-read system-index.json + atlas-map.json from disk. Call after the
    builder script (_build_map.py) runs so the cached snapshot picks up changes."""
    global _snapshot, _graph, _loaded_at
    _snapshot = None
    _graph = None
    snap, _ = _ensure()
    return {"status": "ok", "loaded_at": _loaded_at, "subsystem_count": len(snap.subsystems)}


def run() -> None:
    """Console-script entry point."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    run()
