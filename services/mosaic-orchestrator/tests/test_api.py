"""Tests for the Mosaic Orchestrator API endpoints."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from mosaic.api import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_metering_usage(client):
    resp = await client.get("/api/v1/metering/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_seconds_used" in data
    assert "paused" in data


@pytest.mark.asyncio
async def test_metering_pause_toggle(client):
    # First call: pause
    resp = await client.post("/api/v1/metering/pause")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paused"] is True

    # Second call: resume
    resp = await client.post("/api/v1/metering/pause")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paused"] is False


@pytest.mark.asyncio
async def test_daily_workflow_endpoint(client):
    with patch("mosaic.api.run_daily_loop", new_callable=AsyncMock) as mock_loop:
        mock_loop.return_value = {"started": "2026-01-01", "steps": [], "completed": "2026-01-01", "skipped": False}
        resp = await client.post("/api/v1/workflows/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data


@pytest.mark.asyncio
async def test_stall_check_endpoint(client):
    with patch("mosaic.api.detect_stalls", new_callable=AsyncMock) as mock_stall:
        mock_stall.return_value = {"stall_detected": False, "cut_list": [], "notified": False}
        resp = await client.post("/api/v1/workflows/stall-check")
        assert resp.status_code == 200
        assert resp.json()["stall_detected"] is False


@pytest.mark.asyncio
async def test_idea_simulation_endpoint(client):
    with patch("mosaic.api.run_idea_to_simulation", new_callable=AsyncMock) as mock_sim:
        mock_sim.return_value = {"ideas_scanned": 0, "simulations_started": 0, "routing_decisions": []}
        resp = await client.post("/api/v1/workflows/idea-simulation")
        assert resp.status_code == 200
        assert resp.json()["simulations_started"] == 0
