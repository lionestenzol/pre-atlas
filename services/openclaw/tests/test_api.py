"""Tests for openclaw.api — REST endpoints."""
import pytest
from fastapi.testclient import TestClient

from openclaw.api import app


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "openclaw"


class TestChannelsEndpoint:
    def test_list_channels(self):
        client = TestClient(app)
        resp = client.get("/api/v1/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["channels"]) == 3
        names = {ch["name"] for ch in data["channels"]}
        assert names == {"telegram", "slack", "discord"}


class TestSkillsEndpoint:
    def test_list_skills(self):
        client = TestClient(app)
        resp = client.get("/api/v1/skills")
        assert resp.status_code == 200
        skills = resp.json()["skills"]
        skill_names = {s["name"] for s in skills}
        assert {"status", "brief", "fest", "simulate", "approve"} == skill_names

    def test_execute_unknown_skill(self):
        client = TestClient(app)
        resp = client.post("/api/v1/skills/nonexistent")
        assert resp.status_code == 404


class TestNotifyEndpoint:
    def test_notify_unknown_channel(self):
        client = TestClient(app)
        resp = client.post("/api/v1/notify", json={"text": "hi", "channel": "fax"})
        assert resp.status_code == 404

    def test_notify_all_disconnected(self):
        client = TestClient(app)
        resp = client.post("/api/v1/notify", json={"text": "test"})
        assert resp.status_code == 200
        # No channels connected, so sent should be empty
        assert resp.json()["sent"] == {}
