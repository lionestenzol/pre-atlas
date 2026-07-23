"""The item backbone — brick 1: one unified READ across every surface's store.

The point of this module is connection, not another island. Today each surface
keeps its own items in its own shape:

    droplist   -> services/droplist/data/dags/*.json + entities/*.json
    cycleboard -> services/cognitive-sensor/thread_cards.json
    inpact     -> apps/inpact/projects.json
    festival   -> ~/festival-project/festivals/**/fest.yaml (ATLAS_FESTIVAL_DIR)

This normalizes all of them to ONE item shape so a single feed can show
everything at once:

    { "id", "source", "kind", "title", "status", "updated", "ref" }

Read-only and fail-soft: a missing or malformed store yields [] for that
source, never an exception. The write side (act in one surface, reflect in all)
is brick 2 and lives elsewhere — this is the seam everything will read from.
"""

from __future__ import annotations

import ast
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

# Write-through (brick 3) is deliberately tiny: only these sources accept writes,
# and only the `status` field. Everything else is read-only.
WRITABLE_SOURCES = {"droplist"}
_MAX_STATUS_LEN = 64


_MAX_STORE_FILE_BYTES = 5 * 1024 * 1024  # packets/cards are tiny; cap to avoid a huge-file read


def _read_json(path: Path) -> Any:
    try:
        if path.stat().st_size > _MAX_STORE_FILE_BYTES:
            return None
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


def _read_yaml(path: Path) -> Any:
    try:
        if path.stat().st_size > _MAX_STORE_FILE_BYTES:
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None


def _festival_workspace() -> Path:
    """Festivals live OUTSIDE repo_root, unlike every other source. Resolve the
    fest workspace via ATLAS_FESTIVAL_DIR (mirrors loader.py's ATLAS_REPO_ROOT
    pattern), defaulting to ~/festival-project."""
    env = os.environ.get("ATLAS_FESTIVAL_DIR")
    return Path(env) if env else Path.home() / "festival-project"


def festival_items(repo_root: Path) -> list[dict[str, Any]]:
    """fest festivals as backbone items. `repo_root` is unused on purpose —
    festivals live in their own workspace (ATLAS_FESTIVAL_DIR), not under the
    repo. Read-only and fail-soft: a missing/malformed workspace yields []."""
    fests = _festival_workspace() / "festivals"
    if not fests.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(fests.rglob("fest.yaml"))[:500]:
        d = _read_yaml(f)
        if not isinstance(d, dict):
            continue
        md = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
        history = md.get("status_history")
        last = history[-1] if isinstance(history, list) and history and isinstance(history[-1], dict) else {}
        # state dir = first path segment under festivals/ (active|planning|ready|dungeon|…)
        try:
            state_dir = f.relative_to(fests).parts[0]
        except (ValueError, IndexError):
            state_dir = ""
        try:
            ref = str(f.relative_to(_festival_workspace())).replace("\\", "/")
        except ValueError:
            ref = str(f).replace("\\", "/")
        # PyYAML auto-parses ISO timestamps to datetime; coerce to the string
        # contract every other source emits.
        updated = last.get("timestamp") or md.get("created_at") or ""
        if not isinstance(updated, str):
            updated = updated.isoformat() if hasattr(updated, "isoformat") else str(updated)
        out.append({
            "id": str(md.get("id") or f.parent.name),
            "source": "festival",
            "kind": "festival",
            "title": str(md.get("goal") or md.get("name") or f.parent.name),
            "status": _as_status(last.get("status")) or state_dir,
            "updated": updated,
            "ref": ref,
        })
    return out


_SOURCES: dict[str, Callable[[Path], list[dict[str, Any]]]] = {
    "droplist": droplist_items,
    "cycleboard": cycleboard_items,
    "inpact": inpact_items,
    "festival": festival_items,
}


def parse_backbone_id(bb_id: str) -> tuple[str | None, str | None]:
    """'bb:droplist:DAG-xxx' -> ('droplist', 'DAG-xxx'). None on malformed."""
    parts = str(bb_id).split(":", 2)
    if len(parts) != 3 or parts[0] != "bb" or not parts[1] or not parts[2]:
        return None, None
    return parts[1], parts[2]


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON via temp-file + os.replace so a crash can't leave a partial file."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def set_item_status(repo_root: Path, bb_id: str, new_status: str) -> dict[str, Any]:
    """Write-through: change a backbone item's status in its SOURCE store.

    Conservative by construction: only WRITABLE_SOURCES, only the status field,
    a .bak is written before the mutation, the write is atomic, and every other
    field in the source record is preserved untouched.
    """
    source, native_id = parse_backbone_id(bb_id)
    if source is None:
        return {"ok": False, "error": f"malformed backbone id: {bb_id!r}"}
    if source not in WRITABLE_SOURCES:
        return {"ok": False, "error": f"write-through not supported for source '{source}' (read-only)"}
    if not isinstance(new_status, str) or not new_status.strip() or len(new_status) > _MAX_STATUS_LEN:
        return {"ok": False, "error": "status must be a non-empty string <= 64 chars"}
    new_status = new_status.strip()
    # Path-traversal guard: native id must be a bare token (droplist ids look
    # like 'DAG-4bbd2113'). This is what stops '../../etc/x' from escaping the
    # dags/ dir when we build the file path below.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", native_id or ""):
        return {"ok": False, "error": "invalid item id"}

    # droplist: status lives on the DAG packet json (entities have no status)
    f = repo_root / "services" / "droplist" / "data" / "dags" / f"{native_id}.json"
    if not f.is_file():
        return {"ok": False, "error": f"droplist packet '{native_id}' not found (only packets have status)"}
    d = _read_json(f)
    if not isinstance(d, dict):
        return {"ok": False, "error": "packet unreadable"}

    old_status = d.get("status")
    bak = f.parent / (f.name + ".bak")
    try:
        bak.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # backup is best-effort; atomic write still protects the original

    d["status"] = new_status
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(f, d)
    return {
        "ok": True, "source": source, "id": native_id,
        "old_status": old_status, "new_status": new_status,
        "ref": str(f.relative_to(repo_root)).replace("\\", "/"),
    }


def _parse_deps(raw: Any) -> list[str]:
    """depends_on is stored as a python-repr string ("['N1', 'N3']") or a list."""
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            v = ast.literal_eval(raw)
            return [str(x) for x in v] if isinstance(v, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


def get_workflow(repo_root: Path, bb_id: str) -> dict[str, Any]:
    """Return a droplist packet's DAG as nodes + edges (steps + depends_on flow).

    This is what turns the flat item 'Check Goat · needs_human' into the actual
    workflow underneath it: 6 steps, their states, and the dependency edges.
    """
    source, native = parse_backbone_id(bb_id)
    if source != "droplist":
        return {"ok": False, "error": f"workflow view is droplist-only (got '{source}')"}
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", native or ""):
        return {"ok": False, "error": "invalid packet id"}
    f = repo_root / "services" / "droplist" / "data" / "dags" / f"{native}.json"
    if not f.is_file():
        return {"ok": False, "error": f"packet '{native}' not found"}
    d = _read_json(f)
    if not isinstance(d, dict):
        return {"ok": False, "error": "packet unreadable"}

    nodes_out: list[dict[str, Any]] = []
    edges_out: list[dict[str, str]] = []
    known: set[str] = set()
    for n in (d.get("nodes") or []):
        if isinstance(n, dict) and (n.get("id") or n.get("node_id")):
            known.add(str(n.get("id") or n.get("node_id")))
    for n in (d.get("nodes") or []):
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or n.get("node_id") or "")
        if not nid:
            continue
        nodes_out.append({
            "id": nid,
            "title": n.get("title") or nid,
            "type": n.get("type") or "",
            "status": n.get("status") or "open",
            "done_condition": n.get("done_condition") or "",
        })
        for dep in _parse_deps(n.get("depends_on")):
            if dep in known:
                edges_out.append({"from": dep, "to": nid})
    return {
        "ok": True, "id": native, "goal": d.get("goal") or "",
        "status": d.get("status"), "domain": d.get("domain"),
        "nodes": nodes_out, "edges": edges_out,
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
