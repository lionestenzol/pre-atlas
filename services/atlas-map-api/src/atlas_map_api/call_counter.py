"""Per-(surface, capability) call counter for the /call gateway.

Answers "which of the registered capabilities actually see live traffic" — a
question the static self-description registry (describe.py) can't answer on
its own, since a declared capability says nothing about whether anyone has
ever invoked it. One counter, incremented at the single choke point every
call path (`/call`, `/seam/call`, MCP `atlas_call`) already funnels through:
`gateway.call_capability`.

Outcome buckets:
  ok      - reached the surface and it reported success
  error   - reached the surface but it failed (bad upstream status / cli exit)
  refused - never reached the surface (enforcement/resolution refusal: 403/404/501/etc)

`refused` is tracked separately from `ok`/`error` so a capability that gets
called constantly but always denied (wrong role, writes gated off) doesn't
read as "live" the same way a capability that's actually being reached does.

Persisted as one JSON file so counts survive a process restart. Single-process
personal-scale tool — a module-level lock around read-modify-write is enough;
no external counter store is warranted here.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Outcome = Literal["ok", "error", "refused"]

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None
_CACHE_PATH: Path | None = None


def _store_path(repo_root: Path) -> Path:
    return repo_root / "services" / "atlas-map-api" / "var" / "call_counts.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}  # fail-soft: a corrupt counter file never blocks a live call


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)  # atomic on both POSIX and Windows


def _key(surface: str, capability_id: str) -> str:
    return f"{surface}:{capability_id}"


def record(repo_root: Path, surface: str, capability_id: str, outcome: Outcome) -> None:
    """Increment the counter for one (surface, capability) call. Fire-and-forget:
    never raises — a counter bug must not be able to break a live call."""
    global _CACHE, _CACHE_PATH
    path = _store_path(repo_root)
    try:
        with _LOCK:
            if _CACHE is None or _CACHE_PATH != path:
                _CACHE = _load(path)
                _CACHE_PATH = path
            row = _CACHE.setdefault(
                _key(surface, capability_id),
                {"surface": surface, "capability": capability_id, "ok": 0, "error": 0, "refused": 0,
                 "first_called": None, "last_called": None},
            )
            row[outcome] = row.get(outcome, 0) + 1
            now = datetime.now(timezone.utc).isoformat()
            row["last_called"] = now
            if row["first_called"] is None:
                row["first_called"] = now
            _save(path, _CACHE)
    except OSError:
        pass  # disk hiccup — traffic counting is best-effort, not load-bearing


def get_counts(repo_root: Path) -> list[dict[str, Any]]:
    """All recorded rows, most total calls first. Does not include capabilities
    that have never been called — cross-reference against describe.py's
    declared capabilities to find those (zero rows = zero live traffic)."""
    with _LOCK:
        data = _load(_store_path(repo_root))
    rows = list(data.values())
    rows.sort(key=lambda r: r["ok"] + r["error"] + r["refused"], reverse=True)
    return rows


def reset(repo_root: Path) -> None:
    """Wipe the counter file. Test/ops use only."""
    global _CACHE, _CACHE_PATH
    path = _store_path(repo_root)
    with _LOCK:
        _CACHE = {}
        _CACHE_PATH = path
        _save(path, _CACHE)
