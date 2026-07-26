"""Shared fixtures for MiroFish tests."""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test_simulations.db"


@pytest.fixture
def sample_report():
    """A valid SimulationReport matching SimulationReport.v1.json."""
    return {
        "simulation_id": "sim-test-001",
        "schema_version": "1.0.0",
        "topic": "Impact of AI on software testing",
        "agent_count": 5,
        "tick_count": 3,
        "duration_seconds": 12.5,
        "summary": "Agents reached consensus that AI accelerates testing.",
        "key_insights": [
            "AI reduces manual test writing by 60%",
            "Human review remains essential for edge cases",
        ],
        "consensus_points": [
            {"claim": "AI improves test coverage", "confidence": 0.85, "supporting_agents": 4},
        ],
        "dissent_points": [
            {"claim": "AI can replace QA teams", "agents_for": 1, "agents_against": 4},
        ],
        "recommendations": [
            {"action": "Adopt AI-assisted test generation", "priority": "high", "rationale": "Proven ROI"},
        ],
        "agent_contributions": [
            {"agent_id": "agent_000", "archetype": "Expert", "message_count": 5, "influence_score": 0.35},
            {"agent_id": "agent_001", "archetype": "Skeptic", "message_count": 3, "influence_score": 0.20},
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
