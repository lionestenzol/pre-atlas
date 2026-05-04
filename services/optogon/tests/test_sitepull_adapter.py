"""Tests for the sitepull -> ContextPackage adapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from optogon.adapters.sitepull_adapter import (
    MANIFEST_NAME,
    build_context_package,
    load_context_package,
)
from optogon.contract_validator import validate

FIXTURES = Path(__file__).parent / "fixtures"


def _write_manifest(audit_dir: Path, files: list[dict]) -> None:
    manifest = {
        "version": 1,
        "target": "https://example.com",
        "mode": "MPA",
        "runDate": "2026-04-22T12:00:00.000Z",
        "fileCount": len(files),
        "totalBytes": sum(f["bytes"] for f in files),
        "files": files,
    }
    (audit_dir / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_context_package(tmp_path)


def test_minimal_manifest_produces_valid_package(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [
            {"path": "index.html", "bytes": 528, "sha256": "deadbeef"},
            {"path": "static/app.js", "bytes": 2048, "sha256": "cafebabe"},
        ],
    )
    pkg = build_context_package(tmp_path)
    validate(pkg, "ContextPackage")
    assert pkg["partial"] is True
    assert pkg["source"] == "url"
    assert pkg["structure_map"]["entry_points"] == ["https://example.com"]
    component_types = {c["type"] for c in pkg["structure_map"]["components"]}
    assert component_types == {"page", "service"}
    assert pkg["token_count"] > 0


def test_audit_md_routes_lifted(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [{"path": "index.html", "bytes": 100, "sha256": "x"}])
    (tmp_path / "AUDIT.md").write_text(
        "## Endpoints\n\nGET /api/users\nPOST /api/login\nGET /api/users\n",
        encoding="utf-8",
    )
    pkg = build_context_package(tmp_path)
    routes = pkg["structure_map"]["routes"]
    paths = {(r["method"], r["path"]) for r in routes}
    assert ("GET", "/api/users") in paths
    assert ("POST", "/api/login") in paths
    # de-duplicated
    assert len(routes) == 2


def test_target_override(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [{"path": "index.html", "bytes": 100, "sha256": "x"}])
    pkg = build_context_package(tmp_path, target_url="http://localhost:3000", source="localhost")
    assert pkg["source"] == "localhost"
    assert pkg["structure_map"]["entry_points"] == ["http://localhost:3000"]


def test_coverage_score_bounded(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [{"path": "index.html", "bytes": 100, "sha256": "x"}])
    (tmp_path / "AUDIT.md").write_text("GET /api/x\n", encoding="utf-8")
    pkg = build_context_package(tmp_path)
    assert 0.0 <= pkg["coverage_score"] <= 1.0


# ---------------------------------------------------------------------------
# load_context_package: anatomy-v1 -> ContextPackage
# ---------------------------------------------------------------------------

def _write_anatomy(path: Path, anatomy: dict) -> None:
    path.write_text(json.dumps(anatomy), encoding="utf-8")


def _base_anatomy(**overrides) -> dict:
    base = {
        "version": "anatomy-v1",
        "metadata": {
            "target": "https://example.com/",
            "mode": "spa",
            "timestamp": "2026-04-22T19:10:00Z",
            "tools": ["anatomy-extension@0.2.0"],
        },
        "regions": [],
        "chains": [],
        "layers": {
            "ui": {"color": "#c084fc"},
            "api": {"color": "#f59e0b"},
            "ext": {"color": "#818cf8"},
            "lib": {"color": "#22c55e"},
            "state": {"color": "#a855f7"},
        },
    }
    base.update(overrides)
    return base


def test_load_anatomy_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_context_package(tmp_path / "anatomy.json")


def test_load_anatomy_minimal_valid_package(tmp_path: Path) -> None:
    """Minimal anatomy with one region produces a schema-valid ContextPackage."""
    anatomy = _base_anatomy(
        regions=[{"id": "header", "n": 1, "name": "Header", "layer": "ui", "kind": "sem"}]
    )
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    validate(pkg, "ContextPackage")
    assert pkg["token_count"] > 0
    assert 0.0 <= pkg["coverage_score"] <= 1.0


def test_regions_map_to_components(tmp_path: Path) -> None:
    """anatomy regions map to structure_map.components with layer-based type."""
    anatomy = _base_anatomy(regions=[
        {"id": "nav", "n": 1, "name": "Nav", "layer": "ui", "desc": "Top nav"},
        {"id": "api-layer", "n": 2, "name": "API endpoint", "layer": "api"},
        {"id": "cart-state", "n": 3, "name": "Cart store", "layer": "state"},
        {"id": "ext-svc", "n": 4, "name": "External svc", "layer": "ext"},
    ])
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    components = {c["name"]: c["type"] for c in pkg["structure_map"]["components"]}
    assert components["Nav"] == "page"           # ui -> page
    assert components["API endpoint"] == "api"   # api -> api
    assert components["Cart store"] == "store"   # state -> store
    assert components["External svc"] == "service"  # ext -> service


def test_fetches_map_to_action_inventory(tmp_path: Path) -> None:
    """Fetches from regions map to action_inventory with correct risk tiers."""
    anatomy = _base_anatomy(regions=[
        {
            "id": "main",
            "n": 1,
            "name": "Main",
            "layer": "ui",
            "fetches": [
                {"method": "GET", "url": "/api/me"},
                {"method": "POST", "url": "/api/cart"},
                {"method": "DELETE", "url": "/api/item/1"},
            ],
        }
    ])
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    actions = {a["label"]: a for a in pkg["action_inventory"]}
    assert actions["GET /api/me"]["risk_tier"] == "low"
    assert actions["GET /api/me"]["reversible"] is True
    assert actions["POST /api/cart"]["risk_tier"] == "medium"
    assert actions["POST /api/cart"]["reversible"] is False
    assert actions["DELETE /api/item/1"]["risk_tier"] == "high"
    assert actions["DELETE /api/item/1"]["reversible"] is False
    # Fetches deduplicated across regions
    assert len(pkg["action_inventory"]) == 3


def test_unknown_fetch_method_defaults_to_high_risk(tmp_path: Path) -> None:
    """Contract 1 Rule 3: unknown HTTP methods get risk_tier: high."""
    anatomy = _base_anatomy(regions=[
        {
            "id": "main",
            "n": 1,
            "name": "Main",
            "layer": "ui",
            "fetches": [{"method": "PATCH", "url": "/api/item/1"}],
        }
    ])
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    assert len(pkg["action_inventory"]) == 1
    assert pkg["action_inventory"][0]["risk_tier"] == "high"


def test_chains_map_to_dependency_graph(tmp_path: Path) -> None:
    """chains[] produces dependency_graph nodes and edges."""
    anatomy = _base_anatomy(
        regions=[{"id": "hdr", "n": 1, "name": "Header", "layer": "ui"}],
        chains=[
            {
                "id": "chain-login",
                "nodes": [
                    {"n": 2, "layer": "ui", "label": "LoginForm"},
                    {"n": 3, "layer": "api", "label": "POST /api/login"},
                    {"n": 4, "layer": "ext", "label": "auth.example.com"},
                ],
            }
        ],
    )
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    graph = pkg.get("dependency_graph")
    assert graph is not None
    node_names = {n["name"] for n in graph["nodes"]}
    assert "LoginForm" in node_names
    assert "POST /api/login" in node_names
    assert "auth.example.com" in node_names
    # ext layer -> external type
    ext_node = next(n for n in graph["nodes"] if n["name"] == "auth.example.com")
    assert ext_node["type"] == "external"
    # Edges: 2->3, 3->4
    assert len(graph["edges"]) == 2
    assert all(e["relationship"] == "calls" for e in graph["edges"])


def test_partial_anatomy_degrades_gracefully(tmp_path: Path) -> None:
    """Missing chains and fetches yields partial package, not a failure."""
    anatomy = _base_anatomy(
        regions=[{"id": "hero", "n": 1, "name": "Hero", "layer": "ui"}]
        # no chains, no fetches
    )
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    validate(pkg, "ContextPackage")
    assert pkg.get("partial") is True
    assert pkg["coverage_score"] < 1.0
    assert pkg["action_inventory"] == []


def test_token_count_populated(tmp_path: Path) -> None:
    """Contract 1 Rule 4: token_count must be present and > 0."""
    p = FIXTURES / "anatomy-realistic.json"
    pkg = load_context_package(p)
    assert isinstance(pkg["token_count"], int)
    assert pkg["token_count"] > 0


def test_realistic_anatomy_produces_valid_package() -> None:
    """Smoke: the realistic fixture validates clean against ContextPackage.v1."""
    pkg = load_context_package(FIXTURES / "anatomy-realistic.json")
    validate(pkg, "ContextPackage")
    assert pkg["structure_map"]["entry_points"] == ["https://shop.example.com/products"]
    assert len(pkg["action_inventory"]) > 0
    assert pkg["dependency_graph"]["nodes"]


def test_fetch_deduplication_across_regions(tmp_path: Path) -> None:
    """Same (method, url) appearing in two regions produces one action."""
    anatomy = _base_anatomy(regions=[
        {"id": "r1", "n": 1, "name": "R1", "layer": "ui",
         "fetches": [{"method": "GET", "url": "/api/shared"}]},
        {"id": "r2", "n": 2, "name": "R2", "layer": "ui",
         "fetches": [{"method": "GET", "url": "/api/shared"}]},
    ])
    p = tmp_path / "anatomy.json"
    _write_anatomy(p, anatomy)
    pkg = load_context_package(p)
    assert len(pkg["action_inventory"]) == 1
