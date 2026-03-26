"""Shared test fixtures for mosaic-orchestrator."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mosaic.clients.cognitive_client import CognitiveClient
from mosaic.clients.delta_client import DeltaClient
from mosaic.clients.mirofish_client import MirofishClient
from mosaic.clients.openclaw_client import OpenClawClient


@pytest.fixture
def tmp_sensor_dir(tmp_path):
    """Create a temp cognitive-sensor directory with fixture data."""
    sensor = tmp_path / "cognitive-sensor"
    sensor.mkdir()

    # completion_stats.json
    (sensor / "completion_stats.json").write_text(
        '{"closed_week": 0, "archived_week": 0, "closed_life": 3, "archived_life": 15, "closure_ratio": 16.7}'
    )

    # daily_payload.json
    (sensor / "daily_payload.json").write_text(
        '{"mode": "BUILD", "schema_version": "1.0.0", "mode_source": "atlas_config"}'
    )

    # governance_state.json
    (sensor / "governance_state.json").write_text(
        '{"open_loops": [{"id": "loop_1", "title": "Fix auth", "age_days": 20}, {"id": "loop_2", "title": "Refactor DB", "age_days": 7}]}'
    )

    # daily_brief.md
    (sensor / "daily_brief.md").write_text("# Daily Brief\nAll systems normal.")

    # governance_config.json
    (sensor / "governance_config.json").write_text('{"mode": "BUILD"}')

    # idea_registry.json
    (sensor / "idea_registry.json").write_text("""{
        "metadata": {"total_ideas": 3},
        "tiers": {
            "execute_now": [
                {"canonical_id": "canon_001", "canonical_title": "High Alignment Idea", "alignment_score": 0.85, "category": "ai_automation", "complexity": "medium"},
                {"canonical_id": "canon_002", "canonical_title": "Low Alignment Idea", "alignment_score": 0.3, "category": "workflow", "complexity": "simple"}
            ],
            "next_up": [
                {"canonical_id": "canon_003", "canonical_title": "Moderate Idea", "alignment_score": 0.75, "category": "systems", "complexity": "large"}
            ],
            "backlog": [],
            "archive": []
        }
    }""")

    return sensor


@pytest.fixture
def mock_cognitive(tmp_sensor_dir):
    """CognitiveClient pointed at fixture data."""
    return CognitiveClient(tmp_sensor_dir)


@pytest.fixture
def mock_delta():
    """DeltaClient with mocked HTTP calls."""
    client = MagicMock(spec=DeltaClient)
    client.get_daemon_status = AsyncMock(return_value={"refreshing": False})
    client.get_unified_state = AsyncMock(return_value={"mode": "BUILD", "risk": "LOW"})
    client.ingest_cognitive = AsyncMock(return_value={"status": "ok"})
    return client


@pytest.fixture
def mock_mirofish():
    """MirofishClient with mocked HTTP calls."""
    client = MagicMock(spec=MirofishClient)
    client.start_simulation = AsyncMock(return_value={"simulation_id": "sim_001"})
    client.get_report = AsyncMock(return_value={"confidence": 0.85, "consensus_score": 0.85})
    return client


@pytest.fixture
def mock_openclaw():
    """OpenClawClient with mocked HTTP calls."""
    client = MagicMock(spec=OpenClawClient)
    client.notify = AsyncMock(return_value={"status": "sent"})
    return client
