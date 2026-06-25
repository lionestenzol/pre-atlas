"""Wiring tests: POST /session/start and POST /session/from_sitepull."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from optogon.context import resolve
from optogon.main import app


PATH_ID = "ship_inpact_lesson"
FIXTURES = Path(__file__).parent / "fixtures"


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


# ---------------------------------------------------------------------------
# POST /session/from_sitepull
# ---------------------------------------------------------------------------

def _write_anatomy_dir(base: Path, host: str) -> Path:
    """Write a minimal anatomy.json at base/.canvas/<host>/anatomy.json."""
    anatomy_dir = base / ".canvas" / host
    anatomy_dir.mkdir(parents=True)
    anatomy = {
        "version": "anatomy-v1",
        "metadata": {
            "target": f"https://{host}/",
            "mode": "spa",
            "timestamp": "2026-04-22T19:10:00Z",
            "tools": ["anatomy-extension@0.2.0"],
        },
        "regions": [
            {
                "id": "header",
                "n": 1,
                "name": "Header",
                "layer": "ui",
                "fetches": [{"method": "GET", "url": "/api/me"}],
            }
        ],
        "chains": [],
        "layers": {
            "ui": {"color": "#c084fc"},
            "api": {"color": "#f59e0b"},
            "ext": {"color": "#818cf8"},
            "lib": {"color": "#22c55e"},
            "state": {"color": "#a855f7"},
        },
    }
    (anatomy_dir / "anatomy.json").write_text(json.dumps(anatomy), encoding="utf-8")
    return anatomy_dir / "anatomy.json"


@pytest.fixture
def sitepull_client(tmp_db):
    return TestClient(app)


def test_from_sitepull_with_anatomy_path(
    sitepull_client: TestClient, tmp_path: Path
) -> None:
    """POST /session/from_sitepull with anatomy_path creates a session."""
    _write_anatomy_dir(tmp_path, "example.com")
    anatomy_path = tmp_path / ".canvas" / "example.com" / "anatomy.json"
    resp = sitepull_client.post(
        "/session/from_sitepull",
        json={"anatomy_path": str(anatomy_path)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session_id" in body
    assert body["session_id"].startswith("sess_")


def test_from_sitepull_with_host_via_web_audit_root(
    sitepull_client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    """POST /session/from_sitepull with host uses WEB_AUDIT_ROOT to resolve anatomy.json."""
    web_audit_root = tmp_path / "web-audit"
    _write_anatomy_dir(web_audit_root, "news.ycombinator.com")
    monkeypatch.setenv("WEB_AUDIT_ROOT", str(web_audit_root))
    resp = sitepull_client.post(
        "/session/from_sitepull",
        json={"host": "news.ycombinator.com"},
    )
    assert resp.status_code == 200, resp.text
    assert "session_id" in resp.json()


def test_from_sitepull_context_lands_in_system_tier(
    sitepull_client: TestClient, tmp_path: Path
) -> None:
    """Created session has sitepull context keys in system tier."""
    _write_anatomy_dir(tmp_path, "example.com")
    anatomy_path = tmp_path / ".canvas" / "example.com" / "anatomy.json"
    resp = sitepull_client.post(
        "/session/from_sitepull",
        json={"anatomy_path": str(anatomy_path)},
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["session_id"]

    # Fetch the session state
    state_resp = sitepull_client.get(f"/session/{session_id}")
    assert state_resp.status_code == 200, state_resp.text
    sys_ctx = state_resp.json()["context"]["system"]
    assert "sitepull.structure_map" in sys_ctx
    assert "sitepull.action_inventory" in sys_ctx
    assert sys_ctx["sitepull.entry_points"] == ["https://example.com/"]


def test_from_sitepull_missing_anatomy_returns_404(
    sitepull_client: TestClient, tmp_path: Path
) -> None:
    """Missing anatomy.json returns 404."""
    resp = sitepull_client.post(
        "/session/from_sitepull",
        json={"anatomy_path": str(tmp_path / "does-not-exist" / "anatomy.json")},
    )
    assert resp.status_code == 404
    assert "anatomy.json not found" in resp.json()["detail"]


def test_from_sitepull_no_body_returns_400(sitepull_client: TestClient) -> None:
    """Neither host nor anatomy_path returns 400."""
    resp = sitepull_client.post("/session/from_sitepull", json={})
    assert resp.status_code == 400


def test_from_sitepull_realistic_fixture(sitepull_client: TestClient) -> None:
    """Realistic anatomy fixture produces a valid session with action_inventory."""
    resp = sitepull_client.post(
        "/session/from_sitepull",
        json={"anatomy_path": str(FIXTURES / "anatomy-realistic.json")},
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["session_id"]

    state_resp = sitepull_client.get(f"/session/{session_id}")
    sys_ctx = state_resp.json()["context"]["system"]
    action_inv = sys_ctx["sitepull.action_inventory"]
    assert len(action_inv) > 0
    risk_tiers = {a["risk_tier"] for a in action_inv}
    assert "low" in risk_tiers   # GET requests
    assert "high" in risk_tiers  # DELETE requests
