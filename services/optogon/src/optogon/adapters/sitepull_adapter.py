"""Sitepull -> ContextPackage v1 adapter.

Reads a sitepull audit output directory (produced by `npx sitepull <url>`)
and emits a ContextPackage v1 payload that Optogon can ingest as
`initial_context.system` on session creation.

Sitepull's structured output (`.sitepull-manifest.json`) lists every vendored
file with sha256 + bytes, but does not enumerate live endpoints in JSON form
(those live in the human-readable AUDIT.md). This adapter therefore emits a
*partial* ContextPackage by default, with `coverage_score` reflecting how
much of the schema we could fill in from the manifest alone.

Usage:
    from pathlib import Path
    from optogon.adapters.sitepull_adapter import build_context_package

    pkg = build_context_package(
        audit_dir=Path("./audits/example.com"),
        target_url="https://example.com",
    )
    # pkg is a dict that validates against ContextPackage.v1
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..contract_validator import validate

CONTRACT_NAME = "ContextPackage"
SCHEMA_VERSION = "1.0"
MANIFEST_NAME = ".sitepull-manifest.json"
AUDIT_NAME = "AUDIT.md"


@dataclass(frozen=True)
class SitepullManifest:
    """Subset of sitepull's manifest we care about."""

    target: str
    mode: str
    run_date: str
    files: tuple[dict, ...]


def load_manifest(audit_dir: Path) -> SitepullManifest | None:
    manifest_path = audit_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return SitepullManifest(
        target=raw.get("target", ""),
        mode=raw.get("mode", "unknown"),
        run_date=raw.get("runDate", datetime.now(timezone.utc).isoformat()),
        files=tuple(raw.get("files", [])),
    )


def _classify_file(rel_path: str) -> str | None:
    """Map a vendored file path to a ContextPackage component type."""
    lower = rel_path.lower()
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "page"
    if lower.endswith(".js") or lower.endswith(".mjs"):
        return "service"
    if "api/" in lower or lower.endswith(".json"):
        return "api"
    return None


def _components_from_files(files: tuple[dict, ...]) -> list[dict]:
    components: list[dict] = []
    for entry in files:
        rel = entry.get("path", "")
        kind = _classify_file(rel)
        if kind is None:
            continue
        components.append(
            {
                "name": rel,
                "type": kind,
                "dependencies": [],
                "inferred_purpose": f"vendored {kind} from sitepull",
            }
        )
    return components


_AUDIT_ROUTE_RE = re.compile(r"^\s*(GET|POST|PUT|DELETE|WS)\s+(\S+)", re.MULTILINE)


def _routes_from_audit(audit_dir: Path) -> list[dict]:
    audit_path = audit_dir / AUDIT_NAME
    if not audit_path.exists():
        return []
    text = audit_path.read_text(encoding="utf-8", errors="replace")
    routes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for method, path in _AUDIT_ROUTE_RE.findall(text):
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        routes.append({"path": path, "method": method, "params": [], "inferred_purpose": ""})
    return routes


def _coverage_score(components: list[dict], routes: list[dict]) -> float:
    """Crude score: rewards presence of components, routes, audit doc."""
    score = 0.0
    if components:
        score += 0.5
    if routes:
        score += 0.3
    score += 0.2  # always have manifest if we got this far
    return round(min(score, 1.0), 2)


def _stable_id(target: str, run_date: str) -> str:
    digest = hashlib.sha256(f"{target}|{run_date}".encode("utf-8")).hexdigest()[:12]
    return f"sitepull-{digest}"


def build_context_package(
    audit_dir: Path,
    target_url: str | None = None,
    source: str = "url",
) -> dict:
    """Translate a sitepull audit dir into a ContextPackage v1 dict.

    Raises FileNotFoundError if the manifest is missing.
    Raises ContractError if the produced package fails schema validation.
    """
    manifest = load_manifest(audit_dir)
    if manifest is None:
        raise FileNotFoundError(f"{MANIFEST_NAME} not found in {audit_dir}")

    target = target_url or manifest.target
    components = _components_from_files(manifest.files)
    routes = _routes_from_audit(audit_dir)
    if not routes:
        # Schema requires routes (can be empty array); ensure at least entry.
        routes = []
    entry_points = [target] if target else []

    package: dict = {
        "schema_version": SCHEMA_VERSION,
        "id": _stable_id(target, manifest.run_date),
        "source": source,
        "captured_at": manifest.run_date,
        "partial": True,
        "coverage_score": _coverage_score(components, routes),
        "structure_map": {
            "entry_points": entry_points,
            "routes": routes,
            "components": components,
        },
        "action_inventory": [],
        "inferred_state": {
            "tech_stack": [manifest.mode] if manifest.mode else [],
        },
        "token_count": sum(int(f.get("bytes", 0)) for f in manifest.files) // 4,
    }

    validate(package, CONTRACT_NAME)
    return package
