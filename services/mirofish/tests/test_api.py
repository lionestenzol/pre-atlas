"""Tests for mirofish.api — REST endpoints using FastAPI TestClient."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from mirofish.api import app, store


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "mirofish"
        assert "timestamp" in data


class TestSimulationEndpoints:
    def setup_method(self):
        self.client = TestClient(app)

    def test_list_simulations(self):
        resp = self.client.get("/api/v1/simulations")
        assert resp.status_code == 200
        assert "simulations" in resp.json()

    def test_get_nonexistent_simulation(self):
        resp = self.client.get("/api/v1/simulations/does-not-exist")
        assert resp.status_code == 404

    def test_delete_nonexistent_simulation(self):
        resp = self.client.delete("/api/v1/simulations/does-not-exist")
        assert resp.status_code == 404

    def test_get_report_nonexistent(self):
        resp = self.client.get("/api/v1/simulations/does-not-exist/report")
        assert resp.status_code == 404

    def test_start_simulation_returns_id(self):
        resp = self.client.post("/api/v1/simulations", json={
            "topic": "test topic",
            "agent_count": 2,
            "tick_count": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "simulation_id" in data
        assert data["status"] == "started"
        assert data["topic"] == "test topic"

        # Clean up
        sim_id = data["simulation_id"]
        store.delete_simulation(sim_id)
