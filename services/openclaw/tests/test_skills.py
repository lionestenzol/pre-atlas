"""Tests for openclaw.skills — each skill handles errors gracefully."""
import pytest
from openclaw.channels.base import Message


class TestStatusSkill:
    @pytest.mark.asyncio
    async def test_status_fails_gracefully(self, monkeypatch):
        # Unroutable port: delta-kernel is often live on the dev machine, and a
        # running service made this "fails gracefully" test fail with a success.
        from openclaw import config as config_module
        monkeypatch.setattr(config_module.config, "delta_url", "http://127.0.0.1:1")
        from openclaw.skills.status import handle_status
        result = await handle_status(Message(text=""))
        assert "Could not fetch status" in result


class TestBriefSkill:
    @pytest.mark.asyncio
    async def test_brief_fails_gracefully(self):
        from openclaw.skills.brief import handle_brief
        result = await handle_brief(Message(text=""))
        assert "Could not fetch brief" in result


class TestFestSkill:
    @pytest.mark.asyncio
    async def test_fest_fails_gracefully(self):
        from openclaw.skills.fest import handle_fest
        result = await handle_fest(Message(text=""))
        # FA0001 retired the live festival API; the skill now degrades to a
        # pointer at the terminal CLI instead of a fetch error.
        assert "isn't available over chat" in result


class TestSimulateSkill:
    @pytest.mark.asyncio
    async def test_simulate_no_topic(self):
        from openclaw.skills.simulate import handle_simulate
        result = await handle_simulate(Message(text=""))
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_simulate_fails_gracefully(self):
        from openclaw.skills.simulate import handle_simulate
        result = await handle_simulate(Message(text="AI impact on testing"))
        # FA0001 retired mirofish with no successor endpoint; the skill now
        # reports unavailability rather than a connection failure.
        assert "aren't available right now" in result


class TestApproveSkill:
    @pytest.mark.asyncio
    async def test_approve_no_id(self):
        from openclaw.skills.approve import handle_approve
        result = await handle_approve(Message(text=""))
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_approve_fails_gracefully(self, monkeypatch):
        # Unroutable port makes the transport failure deterministic — the
        # other "fails gracefully" tests rely on the service being down,
        # but delta-kernel (:3001) is often running on the dev machine.
        from openclaw import config as config_module
        monkeypatch.setattr(config_module.config, "delta_url", "http://127.0.0.1:1")
        from openclaw.skills.approve import handle_approve
        result = await handle_approve(Message(text="pa-123"))
        assert "Could not reach delta-kernel" in result

    @pytest.mark.asyncio
    async def test_approve_maps_gate_outcomes(self, monkeypatch):
        from openclaw.skills import approve as approve_module

        outcomes = [
            (200, {"id": "pa-1", "status": "CONFIRMED",
                   "execution": {"run_id": "r-9", "status": "ok"}}, "Approved"),
            (404, {"error": "Pending action not found"}, "No pending action"),
            (409, {"error": "Action already CONFIRMED"}, "already resolved"),
            (410, {"error": "Action expired"}, "expired"),
            (403, {"error": "not allowed in mode RECOVER"}, "mode gate"),
        ]
        for status, body, expected in outcomes:
            async def fake_confirm(action_id, _s=status, _b=body):
                return _s, _b
            monkeypatch.setattr(approve_module, "confirm_pending_action", fake_confirm)
            result = await approve_module.handle_approve(Message(text="pa-1"))
            assert expected in result, f"status {status}: {result}"


class TestPendingSkill:
    @pytest.mark.asyncio
    async def test_pending_fails_gracefully(self, monkeypatch):
        # Unroutable port makes the transport failure deterministic — same
        # rationale as TestStatusSkill/TestApproveSkill's isolation fix.
        from openclaw import config as config_module
        monkeypatch.setattr(config_module.config, "delta_url", "http://127.0.0.1:1")
        from openclaw.skills.pending import handle_pending
        result = await handle_pending(Message(text=""))
        assert "Could not fetch pending actions" in result

    @pytest.mark.asyncio
    async def test_pending_empty(self, monkeypatch):
        from openclaw.skills import pending as pending_module

        async def fake_fetch():
            return []
        monkeypatch.setattr(pending_module, "fetch_pending_actions", fake_fetch)
        result = await pending_module.handle_pending(Message(text=""))
        assert result == "No pending actions."

    @pytest.mark.asyncio
    async def test_pending_lists_actions(self, monkeypatch):
        from openclaw.skills import pending as pending_module

        async def fake_fetch():
            return [
                {
                    "id": "pa-1",
                    "action_type": "reply_message",
                    "target_entity_id": "draft-1",
                    "label": "Reply to Jane",
                    "status": "PENDING",
                    "expires_at": 1720000000000,
                },
                {
                    "id": "pa-2",
                    "action_type": "rest_action",
                    "target_entity_id": "t-2",
                    "label": None,
                    "status": "PENDING",
                    "expires_at": 1720000100000,
                },
            ]
        monkeypatch.setattr(pending_module, "fetch_pending_actions", fake_fetch)
        result = await pending_module.handle_pending(Message(text=""))
        assert "(2)" in result
        assert "pa-1" in result and "Reply to Jane" in result
        # Falls back to action_type when label is missing/None.
        assert "pa-2" in result and "rest_action" in result
        assert "/approve <id>" in result
