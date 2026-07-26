"""Load the system map snapshot from disk.

Sources of truth:
- <repo>/audit/system-index.json — 33 subsystems with metadata, file_count, loc, port, autostart
- <repo>/atlas-map.json          — hand-curated service_edges + retired set + purpose strings

Both are emitted by audit/imports/_build_map.py. We read them, never write.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Subsystem:
    name: str
    path: str
    group: str  # services | apps | tools
    language: str
    framework: str
    file_count: int
    total_loc: int
    deps: tuple[str, ...] = field(default_factory=tuple)
    entry_points: tuple[str, ...] = field(default_factory=tuple)
    port: int | None = None
    in_autostart: bool = False
    purpose: str = ""
    gov: dict[str, Any] | None = None  # {automation, note} from atlas-map.json governance block

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "group": self.group,
            "language": self.language,
            "framework": self.framework,
            "file_count": self.file_count,
            "total_loc": self.total_loc,
            "deps": list(self.deps),
            "entry_points": list(self.entry_points),
            "port": self.port,
            "in_autostart": self.in_autostart,
            "purpose": self.purpose,
            "gov": self.gov,
        }


@dataclass(frozen=True)
class MapSnapshot:
    repo_root: Path
    generated_at: str
    subsystems: dict[str, Subsystem]
    service_edges: tuple[tuple[str, str], ...]
    retired: frozenset[str]

    @property
    def names(self) -> list[str]:
        return sorted(self.subsystems.keys())


def _resolve_repo_root() -> Path:
    """Walk up from this file until we find atlas-map.json or audit/system-index.json."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "audit" / "system-index.json").is_file():
            return parent
        if (parent / "atlas-map.json").is_file() and (parent / "audit").is_dir():
            return parent
    # Fallback: env override
    env_root = os.environ.get("ATLAS_REPO_ROOT")
    if env_root:
        p = Path(env_root)
        if p.is_dir():
            return p
    raise RuntimeError(
        "atlas-map-api: could not locate Pre Atlas repo root "
        "(looked for audit/system-index.json or atlas-map.json). "
        "Set ATLAS_REPO_ROOT env var to override."
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_gov(raw: Any) -> dict[str, Any] | None:
    """Coerce a governance entry to a stable {automation, note} shape, or None.

    Guards the viewer against rendering literal "undefined" when a hand-edited
    atlas-map.json governance entry omits a key.
    """
    if not isinstance(raw, dict):
        return None
    return {"automation": str(raw.get("automation", "unknown")), "note": str(raw.get("note", ""))}


def load_snapshot(repo_root: Path | None = None) -> MapSnapshot:
    """Read system-index.json + atlas-map.json and build the in-memory snapshot."""
    root = repo_root or _resolve_repo_root()
    idx_path = root / "audit" / "system-index.json"
    if not idx_path.is_file():
        raise RuntimeError(f"system-index.json not found at {idx_path}")

    idx = _read_json(idx_path)
    generated_at = str(idx.get("generated_at", ""))
    purpose_by_name: dict[str, str] = {}
    gov_by_name: dict[str, dict[str, Any]] = {}
    retired_set: set[str] = set()
    edges: list[tuple[str, str]] = []

    cfg_path = root / "atlas-map.json"
    if cfg_path.is_file():
        cfg = _read_json(cfg_path)
        purpose_by_name.update(cfg.get("purposes", {}) or {})
        gov_by_name.update(cfg.get("governance", {}) or {})
        retired_set.update(cfg.get("retired", []) or [])
        for pair in cfg.get("service_edges", []) or []:
            if isinstance(pair, list) and len(pair) == 2:
                edges.append((str(pair[0]), str(pair[1])))

    subsystems: dict[str, Subsystem] = {}
    for entry in idx.get("entries", []) or []:
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        subsystems[name] = Subsystem(
            name=name,
            path=str(entry.get("path", "")),
            group=str(entry.get("path", "")).split("/", 1)[0] if "/" in str(entry.get("path", "")) else "",
            language=str(entry.get("language", "") or ""),
            framework=str(entry.get("framework", "") or ""),
            file_count=int(entry.get("file_count", 0) or 0),
            total_loc=int(entry.get("total_loc", 0) or 0),
            deps=tuple(str(d) for d in (entry.get("deps", []) or [])),
            entry_points=tuple(str(e) for e in (entry.get("entry_points", []) or [])),
            port=int(entry["port"]) if entry.get("port") not in (None, "") else None,
            in_autostart=bool(entry.get("in_autostart", False)),
            purpose=purpose_by_name.get(name, ""),
            gov=_normalize_gov(gov_by_name.get(name)),
        )

    return MapSnapshot(
        repo_root=root,
        generated_at=generated_at,
        subsystems=subsystems,
        service_edges=tuple(edges),
        retired=frozenset(retired_set),
    )
