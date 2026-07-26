"""Tests for mirofish.swarm.store."""
import pytest

from mirofish.swarm.store import SimulationStore


class TestSimulationStore:
    def test_create_and_get(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        agents = [{"agent_id": "a0", "name": "Test Agent"}]
        store.create_simulation("sim-1", "test topic", 1, 5, agents)

        sim = store.get_simulation("sim-1")
        assert sim is not None
        assert sim["topic"] == "test topic"
        assert sim["agent_count"] == 1
        assert sim["tick_count"] == 5
        assert sim["status"] == "pending"
        assert sim["agents"] == agents
        store.close()

    def test_lifecycle_transitions(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-2", "lifecycle", 3, 10, [])

        store.start_simulation("sim-2")
        sim = store.get_simulation("sim-2")
        assert sim["status"] == "running"
        assert sim["started_at"] is not None

        store.complete_simulation("sim-2", 42.5)
        sim = store.get_simulation("sim-2")
        assert sim["status"] == "completed"
        assert sim["duration_seconds"] == 42.5
        store.close()

    def test_fail_simulation(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-3", "fail test", 2, 5, [])
        store.fail_simulation("sim-3", "timeout error occurred")
        sim = store.get_simulation("sim-3")
        assert sim["status"] == "failed"
        assert sim["error_message"] == "timeout error occurred"
        store.close()

    def test_save_and_get_ticks(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-4", "ticks", 2, 3, [])

        msgs_0 = [{"agent_id": "a0", "content": "hello"}]
        msgs_1 = [{"agent_id": "a1", "content": "world"}]
        msgs_2 = [{"agent_id": "a0", "content": "done"}]
        store.save_tick("sim-4", 0, msgs_0)
        store.save_tick("sim-4", 1, msgs_1)
        store.save_tick("sim-4", 2, msgs_2)

        all_ticks = store.get_ticks("sim-4")
        assert len(all_ticks) == 3
        assert all_ticks[0]["messages"] == msgs_0

        # from_tick filtering
        later = store.get_ticks("sim-4", from_tick=2)
        assert len(later) == 1
        assert later[0]["tick_number"] == 2
        store.close()

    def test_save_and_get_report(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-5", "report", 5, 10, [])
        report = {"summary": "test report", "key_insights": ["a", "b"]}
        store.save_report("sim-5", report)

        sim = store.get_simulation("sim-5")
        assert sim["report"] == report
        store.close()

    def test_list_simulations(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-a", "first", 1, 1, [])
        store.create_simulation("sim-b", "second", 2, 2, [])

        sims = store.list_simulations()
        assert len(sims) == 2
        # Most recent first
        assert sims[0]["simulation_id"] == "sim-b"
        store.close()

    def test_delete_cascades(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        store.create_simulation("sim-del", "delete me", 1, 2, [])
        store.save_tick("sim-del", 0, [{"msg": "hi"}])
        store.save_tick("sim-del", 1, [{"msg": "bye"}])

        store.delete_simulation("sim-del")
        assert store.get_simulation("sim-del") is None
        assert store.get_ticks("sim-del") == []
        store.close()

    def test_get_nonexistent_returns_none(self, tmp_db):
        store = SimulationStore(db_path=tmp_db)
        assert store.get_simulation("does-not-exist") is None
        store.close()
