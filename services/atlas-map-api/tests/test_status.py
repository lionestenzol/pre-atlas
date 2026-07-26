"""Tests for the Wave 1.3 unified status surface (GET /status)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import atlas_map_api.status as status_mod
from atlas_map_api.server import app

client = TestClient(app)


def test_unified_status_shape(monkeypatch):
    # Stub the machine-touching collectors so the test is hermetic.
    monkeypatch.setattr(
        status_mod,
        "collect_scheduled_tasks",
        lambda: {
            "error": None,
            "tasks": [{"name": "Atlas-Autostart", "state": "Ready", "triggers": ["LogonTrigger"]}],
        },
    )

    async def fake_daemon():
        return {"reachable": True, "running": True, "last_heartbeat": 1234567890123, "current_job": None}

    monkeypatch.setattr(status_mod, "collect_daemon", fake_daemon)
    monkeypatch.setattr(status_mod, "collect_orphans", lambda root: {"error": None, "count": 0, "candidates": []})

    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    for key in ("services", "services_up", "scheduled_tasks", "daemon", "orphans"):
        assert key in body
    assert body["daemon"]["running"] is True
    assert body["orphans"]["count"] == 0
