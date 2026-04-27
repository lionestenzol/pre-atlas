"""Tests for the sitepull -> ContextPackage adapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from optogon.adapters.sitepull_adapter import (
    MANIFEST_NAME,
    build_context_package,
)
from optogon.contract_validator import validate


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
