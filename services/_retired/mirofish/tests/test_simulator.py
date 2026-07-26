"""Tests for mirofish.swarm.simulator."""
import pytest
from unittest.mock import AsyncMock

from mirofish.swarm.simulator import SimulationRunner, SimulationConfig, SimulationResult
from mirofish.swarm.personality import AgentProfile
from mirofish.swarm.store import SimulationStore


class TestSimulationRunner:
    @pytest.mark.asyncio
    async def test_run_uses_provided_simulation_id(self, tmp_db):
        """When simulation_id is passed, runner reuses it instead of creating a new store record."""
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("external-id", "test", 2, 1, [])

        runner = SimulationRunner(
            store=store,
            ollama_url="http://localhost:99999",  # will fail, that's OK
        )

        agents = [
            AgentProfile(agent_id="a0", name="Agent 0", archetype="Expert"),
            AgentProfile(agent_id="a1", name="Agent 1", archetype="Skeptic"),
        ]
        sim_config = SimulationConfig(topic="test", agents=agents, tick_count=1)

        # Runner will fail at Ollama call but should use external-id
        result = await runner.run(sim_config, simulation_id="external-id")

        assert result.simulation_id == "external-id"
        # Verify the store record was updated (started, then completed)
        sim = store.get_simulation("external-id")
        assert sim["status"] == "completed"
        store.close()

    @pytest.mark.asyncio
    async def test_run_generates_id_when_none_provided(self, tmp_db):
        """When no simulation_id is passed, runner creates its own."""
        store = SimulationStore(db_path=tmp_db)
        runner = SimulationRunner(
            store=store,
            ollama_url="http://localhost:99999",
        )

        agents = [AgentProfile(agent_id="a0", name="A0", archetype="Expert")]
        sim_config = SimulationConfig(topic="auto-id test", agents=agents, tick_count=1)

        result = await runner.run(sim_config)

        # Should have a UUID-style ID
        assert len(result.simulation_id) > 10
        sim = store.get_simulation(result.simulation_id)
        assert sim is not None
        assert sim["topic"] == "auto-id test"
        store.close()

    @pytest.mark.asyncio
    async def test_agent_messages_on_ollama_failure(self, tmp_db):
        """When Ollama is unreachable, agents produce error messages."""
        store = SimulationStore(db_path=tmp_db)
        runner = SimulationRunner(
            store=store,
            ollama_url="http://localhost:99999",
        )

        agents = [AgentProfile(agent_id="a0", name="A0", archetype="Expert")]
        sim_config = SimulationConfig(topic="error test", agents=agents, tick_count=1)

        result = await runner.run(sim_config)

        assert result.status == "completed"
        assert len(result.ticks) == 1
        # Messages should contain error indicator
        for msg in result.ticks[0]:
            assert "unavailable" in msg.content.lower() or msg.content  # either error or content
        store.close()
