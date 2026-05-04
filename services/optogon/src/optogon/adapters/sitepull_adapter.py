"""Sitepull -> ContextPackage v1 adapter.

Two entry points:

1. build_context_package(audit_dir, ...) - reads a sitepull audit directory
   (.sitepull-manifest.json + AUDIT.md) and emits a partial ContextPackage.

2. load_context_package(anatomy_path) - reads an anatomy-v1 JSON file and
   emits a ContextPackage. Anatomy is richer: regions, chains, fetches all
   map directly to the contract's structure_map, dependency_graph, and
   action_inventory fields.

Usage:
    from pathlib import Path
    from optogon.adapters.sitepull_adapter import load_context_package

    pkg = load_context_package(Path("/web-audit/.canvas/example.com/anatomy.json"))
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


# ---------------------------------------------------------------------------
# Anatomy-v1 -> ContextPackage adapter
# ---------------------------------------------------------------------------

_LAYER_TO_COMPONENT_TYPE: dict[str, str] = {
    "ui": "page",
    "api": "api",
    "ext": "service",
    "lib": "service",
    "state": "store",
}

_LAYER_TO_NODE_TYPE: dict[str, str] = {
    "ui": "internal",
    "api": "internal",
    "ext": "external",
    "lib": "package",
    "state": "internal",
}

# Risk by HTTP method. Anything not listed defaults to high (Contract 1 Rule 3).
_METHOD_RISK: dict[str, str] = {
    "GET": "low",
    "POST": "medium",
    "PUT": "high",
    "DELETE": "high",
    "WS": "medium",
}


def _infer_source(target: str) -> str:
    if "localhost" in target or "127.0.0.1" in target:
        return "localhost"
    if target.startswith("http"):
        return "url"
    return "filesystem"


def _anatomy_id(target: str, timestamp: str) -> str:
    digest = hashlib.sha256(f"anatomy|{target}|{timestamp}".encode("utf-8")).hexdigest()[:12]
    return f"anatomy-{digest}"


def _components_from_regions(regions: list[dict]) -> list[dict]:
    components: list[dict] = []
    for r in regions:
        layer = r.get("layer", "ui")
        comp_type = _LAYER_TO_COMPONENT_TYPE.get(layer, "service")
        components.append({
            "name": r.get("name") or r.get("id", "unknown"),
            "type": comp_type,
            "dependencies": [],
            "inferred_purpose": r.get("desc") or r.get("name", ""),
        })
    return components


def _dependency_graph_from_chains(chains: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    for chain in chains:
        prev_id: str | None = None
        for node in chain.get("nodes", []):
            n_id = str(node.get("n", ""))
            if not n_id:
                prev_id = None
                continue
            if n_id not in seen:
                seen.add(n_id)
                layer = node.get("layer", "ui")
                nodes.append({
                    "id": n_id,
                    "type": _LAYER_TO_NODE_TYPE.get(layer, "internal"),
                    "name": node.get("label", n_id),
                })
            if prev_id is not None:
                edges.append({"from": prev_id, "to": n_id, "relationship": "calls"})
            prev_id = n_id

    return {"nodes": nodes, "edges": edges}


def _actions_from_regions(regions: list[dict]) -> list[dict]:
    """Extract deduplicated action_inventory entries from region fetches."""
    actions: list[dict] = []
    seen: set[str] = set()

    for region in regions:
        for fetch in region.get("fetches", []):
            method = (fetch.get("method") or "").upper()
            url = fetch.get("url", "")
            dedup_key = f"{method}|{url}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            action_id = "fetch-" + hashlib.sha256(dedup_key.encode()).hexdigest()[:10]
            # Contract 1 Rule 3: unknown methods default to high
            risk_tier = _METHOD_RISK.get(method, "high")

            actions.append({
                "id": action_id,
                "label": f"{method} {url}",
                "type": "api_call",
                "inputs": [],
                "outputs": [],
                "risk_tier": risk_tier,
                "reversible": method == "GET",
            })
    return actions


def _routes_from_regions(regions: list[dict]) -> list[dict]:
    _valid_methods = {"GET", "POST", "PUT", "DELETE", "WS"}
    seen: set[tuple[str, str]] = set()
    routes: list[dict] = []
    for region in regions:
        for fetch in region.get("fetches", []):
            method = (fetch.get("method") or "").upper()
            url = fetch.get("url", "")
            if method not in _valid_methods:
                method = "GET"
            key = (method, url)
            if key in seen:
                continue
            seen.add(key)
            routes.append({"path": url, "method": method, "params": [], "inferred_purpose": ""})
    return routes


def _tech_stack_from_metadata(mode: str, tools: list) -> list[str]:
    stack: list[str] = []
    if mode:
        stack.append(mode)
    stack.extend(t for t in tools if isinstance(t, str))
    return stack


def _anatomy_coverage(regions: list, chains: list, has_fetches: bool, metadata: dict) -> float:
    """Coverage: 0.25 per quadrant (regions, chains, fetches, complete metadata)."""
    score = 0.0
    if regions:
        score += 0.25
    if chains:
        score += 0.25
    if has_fetches:
        score += 0.25
    if metadata.get("target") and metadata.get("timestamp"):
        score += 0.25
    return round(min(score, 1.0), 2)


def load_context_package(anatomy_path: Path) -> dict:
    """Read an anatomy-v1 JSON file and produce a ContextPackage v1 dict.

    Raises FileNotFoundError if anatomy.json is missing.
    Raises ContractError if the produced package fails schema validation.
    Degrades gracefully on partial anatomy (missing chains or fetches).
    """
    if not anatomy_path.exists():
        raise FileNotFoundError(f"anatomy.json not found: {anatomy_path}")

    raw_text = anatomy_path.read_text(encoding="utf-8")
    raw = json.loads(raw_text)

    metadata = raw.get("metadata", {})
    regions: list[dict] = raw.get("regions", [])
    chains: list[dict] = raw.get("chains", [])

    target = metadata.get("target", "")
    mode = metadata.get("mode", "")
    timestamp = metadata.get("timestamp", datetime.now(timezone.utc).isoformat())
    tools: list = metadata.get("tools", [])

    all_fetches = [f for r in regions for f in r.get("fetches", [])]
    has_fetches = bool(all_fetches)

    components = _components_from_regions(regions)
    routes = _routes_from_regions(regions)
    dep_graph = _dependency_graph_from_chains(chains)
    action_inventory = _actions_from_regions(regions)

    data_stores = [
        r.get("name") or r.get("id", "")
        for r in regions
        if r.get("layer") == "state"
    ]
    inferred_state: dict = {
        "auth_required": False,
        "data_stores": data_stores,
        "environment": "dev",
        "tech_stack": _tech_stack_from_metadata(mode, tools),
    }

    coverage = _anatomy_coverage(regions, chains, has_fetches, metadata)

    package: dict = {
        "schema_version": SCHEMA_VERSION,
        "id": _anatomy_id(target, timestamp),
        "source": _infer_source(target),
        "captured_at": timestamp,
        "structure_map": {
            "entry_points": [target] if target else [],
            "routes": routes,
            "components": components,
        },
        "action_inventory": action_inventory,
        "inferred_state": inferred_state,
        # Contract 1 Rule 4: token_count required
        "token_count": len(raw_text) // 4,
        "coverage_score": coverage,
    }

    if coverage < 1.0:
        package["partial"] = True

    if dep_graph["nodes"]:
        package["dependency_graph"] = dep_graph

    validate(package, CONTRACT_NAME)
    return package
