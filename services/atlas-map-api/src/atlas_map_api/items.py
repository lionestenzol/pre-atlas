"""The item backbone — brick 1: one unified READ across every surface's store.

The point of this module is connection, not another island. Today each surface
keeps its own items in its own shape:

    droplist   -> services/droplist/data/dags/*.json + entities/*.json
    cycleboard -> services/cognitive-sensor/thread_cards.json
    inpact     -> apps/inpact/projects.json

This normalizes all of them to ONE item shape so a single feed can show
everything at once:

    { "id", "source", "kind", "title", "status", "updated", "ref" }

Read-only and fail-soft: a missing or malformed store yields [] for that
source, never an exception. The write side (act in one surface, reflect in all)
is brick 2 and lives elsewhere — this is the seam everything will read from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _as_status(value: Any) -> str:
    """Coerce a heterogeneous status field to a short string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("label", "status", "verdict", "value"):
            if isinstance(value.get(k), str):
                return value[k]
        return "classified"
    if value is None:
        return ""
    return str(value)


def droplist_items(repo_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base = repo_root / "services" / "droplist" / "data"
    for f in sorted((base / "dags").glob("*.json"))[:500]:
        d = _read_json(f)
        if not isinstance(d, dict):
            continue
        out.append({
            "id": d.get("dag_id") or f.stem,
            "source": "droplist",
            "kind": "packet",
            "title": d.get("goal") or d.get("raw_input") or f.stem,
            "status": _as_status(d.get("status")),
            "updated": d.get("updated_at") or d.get("created_at") or "",
            "ref": str(f.relative_to(repo_root)).replace("\\", "/"),
        })
    for f in sorted((base / "entities").glob("*.json"))[:500]:
        d = _read_json(f)
        if not isinstance(d, dict):
            continue
        open_nodes = d.get("open_nodes") or []
        out.append({
            "id": d.get("entity_id") or f.stem,
            "source": "droplist",
            "kind": "entity",
            "title": d.get("name") or f.stem,
            "status": f"{len(open_nodes)} open" if open_nodes else "tracked",
            "updated": d.get("updated_at") or d.get("last_observation") or "",
            "ref": str(f.relative_to(repo_root)).replace("\\", "/"),
        })
    return out


def cycleboard_items(repo_root: Path) -> list[dict[str, Any]]:
    f = repo_root / "services" / "cognitive-sensor" / "thread_cards.json"
    data = _read_json(f)
    cards = data if isinstance(data, list) else (data.get("cards") if isinstance(data, dict) else None)
    if not isinstance(cards, list):
        return []
    out: list[dict[str, Any]] = []
    for c in cards:
        if not isinstance(c, dict):
            continue
        out.append({
            "id": c.get("convo_id") or c.get("id") or "",
            "source": "cycleboard",
            "kind": "card",
            "title": c.get("title") or c.get("convo_id") or "",
            "status": _as_status(c.get("classification")),
            "updated": c.get("date") or "",
            "ref": "services/cognitive-sensor/thread_cards.json",
        })
    return out


def inpact_items(repo_root: Path) -> list[dict[str, Any]]:
    f = repo_root / "apps" / "inpact" / "projects.json"
    data = _read_json(f)
    projects = data if isinstance(data, list) else (data.get("projects") if isinstance(data, dict) else None)
    if not isinstance(projects, list):
        return []
    out: list[dict[str, Any]] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        out.append({
            "id": p.get("name") or p.get("path") or "",
            "source": "inpact",
            "kind": "project",
            "title": p.get("name") or p.get("path") or "",
            "status": _as_status(p.get("band")),
            "updated": p.get("updated") or "",
            "ref": "apps/inpact/projects.json",
        })
    return out


_SOURCES: dict[str, Callable[[Path], list[dict[str, Any]]]] = {
    "droplist": droplist_items,
    "cycleboard": cycleboard_items,
    "inpact": inpact_items,
}


def all_items(repo_root: Path, source: str | None = None) -> dict[str, Any]:
    """Aggregate every surface's items into one feed. fail-soft per source."""
    chosen = {source: _SOURCES[source]} if source in _SOURCES else _SOURCES
    items: list[dict[str, Any]] = []
    by_source: dict[str, int] = {}
    for name, fn in chosen.items():
        try:
            got = fn(repo_root)
        except Exception:
            got = []
        by_source[name] = len(got)
        items.extend(got)
    return {"count": len(items), "by_source": by_source, "items": items}
