"""Wiring tests: POST /session/start ingests a ContextPackage into system tier."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from optogon.context import resolve
from optogon.main import app


PATH_ID = "ship_inpact_lesson"


def _valid_package() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "id": "ctx-test-001",
        "source": "url",
        "captured_at": "2026-04-22T12:00:00Z",
        "structure_map": {
            "entry_points": ["https://example.com"],
            "routes": [
                {"path": "/api/x", "method": "GET", "params": [], "inferred_purpose": ""}
            ],
            "components": [],
        },
        "action_inventory": [
            {
                "id": "act1",
                "label": "List users",
                "type": "api_call",
                "inputs": [],
                "outputs": [],
                "risk_tier": "low",
                "reversible": True,
            }
        ],
        "inferred_state": {"tech_stack": ["MPA"]},
        "token_count": 42,
    }


def _write_sitepull_dir(audit_dir: Path) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "target": "https://example.com",
        "mode": "MPA",
        "runDate": "2026-04-22T12:00:00.000Z",
        "fileCount": 1,
        "totalBytes": 100,
        "files": [{"path": "index.html", "bytes": 100, "sha256": "abc"}],
    }
    (audit_dir / ".sitepull-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (audit_dir / "AUDIT.md").write_text("GET /api/users\n", encoding="utf-8")


@pytest.fixture
def client(tmp_db):
    return TestClient(app)


def test_inline_context_package_lands_in_system_tier(client: TestClient) -> None:
    resp = client.post(
        "/session/start",
        json={"path_id": PATH_ID, "context_package": _valid_package()},
    )
    assert resp.status_code == 200, resp.text
    state = resp.json()["state"]
    sys_tier = state["context"]["system"]
    assert "sitepull.structure_map" in sys_tier
    assert "sitepull.action_inventory" in sys_tier
    assert "sitepull.inferred_state" in sys_tier
    assert sys_tier["sitepull.entry_points"] == ["https://example.com"]


def test_sitepull_audit_dir_lands_in_system_tier(
    client: TestClient, tmp_path: Path
) -> None:
    audit_dir = tmp_path / "example-audit"
    _write_sitepull_dir(audit_dir)
    resp = client.post(
        "/session/start",
        json={"path_id": PATH_ID, "sitepull_audit_dir": str(audit_dir)},
    )
    assert resp.status_code == 200, resp.text
    state = resp.json()["state"]
    sys_tier = state["context"]["system"]
    assert "sitepull.structure_map" in sys_tier
    assert sys_tier["sitepull.partial"] is True


def test_invalid_context_package_returns_400(client: TestClient) -> None:
    bad = _valid_package()
    del bad["structure_map"]
    resp = client.post(
        "/session/start",
        json={"path_id": PATH_ID, "context_package": bad},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "contract_violation"
    assert body["contract"] == "ContextPackage"


def test_user_tier_overrides_system_tier(client: TestClient) -> None:
    resp = client.post(
        "/session/start",
        json={
            "path_id": PATH_ID,
            "context_package": _valid_package(),
            "initial_context": {"sitepull.structure_map": "USER_OVERRIDE"},
        },
    )
    assert resp.status_code == 200, resp.text
    ctx = resp.json()["state"]["context"]
    value, tier = resolve("sitepull.structure_map", ctx)
    assert value == "USER_OVERRIDE"
    assert tier == "user"


def test_missing_audit_dir_returns_400(client: TestClient, tmp_path: Path) -> None:
    resp = client.post(
        "/session/start",
        json={
            "path_id": PATH_ID,
            "sitepull_audit_dir": str(tmp_path / "does-not-exist"),
        },
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]
