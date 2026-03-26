"""Tests for mirofish.reports.builder."""
import pytest
from unittest.mock import AsyncMock

from mirofish.reports.builder import ReportBuilder
from mirofish.swarm.simulator import SimulationResult, AgentMessage
from mirofish.swarm.personality import AgentProfile


def _make_result():
    """Create a minimal SimulationResult for testing."""
    agents = [
        AgentProfile(agent_id="a0", name="Expert 1", archetype="Expert"),
        AgentProfile(agent_id="a1", name="Skeptic 1", archetype="Skeptic"),
    ]
    ticks = [
        [
            AgentMessage(agent_id="a0", agent_name="Expert 1", content="AI is transformative."),
            AgentMessage(agent_id="a1", agent_name="Skeptic 1", content="But at what cost?"),
        ],
        [
            AgentMessage(agent_id="a0", agent_name="Expert 1", content="The benefits outweigh risks."),
        ],
    ]
    return SimulationResult(
        simulation_id="sim-builder-test",
        topic="AI impact",
        agents=agents,
        ticks=ticks,
        duration_seconds=5.0,
        status="completed",
    )


class TestReportBuilder:
    @pytest.mark.asyncio
    async def test_build_without_ollama(self):
        """When Ollama is unreachable, build still returns a valid report structure."""
        builder = ReportBuilder(ollama_url="http://localhost:99999")
        result = _make_result()
        report = await builder.build(result)

        assert report["simulation_id"] == "sim-builder-test"
        assert report["schema_version"] == "1.0.0"
        assert report["topic"] == "AI impact"
        assert report["agent_count"] == 2
        assert report["tick_count"] == 2
        assert report["duration_seconds"] == 5.0
        assert "created_at" in report
        # Fallback summary when Ollama fails
        assert "AI impact" in report["summary"]

    @pytest.mark.asyncio
    async def test_agent_contributions_calculated(self):
        """Agent contributions should count messages and compute influence."""
        builder = ReportBuilder(ollama_url="http://localhost:99999")
        result = _make_result()
        report = await builder.build(result)

        contributions = report["agent_contributions"]
        assert len(contributions) == 2

        # a0 has 2 messages, a1 has 1
        a0 = next(c for c in contributions if c["agent_id"] == "a0")
        a1 = next(c for c in contributions if c["agent_id"] == "a1")
        assert a0["message_count"] == 2
        assert a1["message_count"] == 1
        assert a0["influence_score"] > a1["influence_score"]
        assert a0["archetype"] == "Expert"

    @pytest.mark.asyncio
    async def test_build_with_empty_ticks(self):
        """Report builds even when simulation has no messages."""
        builder = ReportBuilder(ollama_url="http://localhost:99999")
        result = SimulationResult(
            simulation_id="sim-empty",
            topic="empty test",
            agents=[],
            ticks=[],
            duration_seconds=0.1,
            status="completed",
        )
        report = await builder.build(result)

        assert report["agent_count"] == 0
        assert report["tick_count"] == 0
        assert report["agent_contributions"] == []
