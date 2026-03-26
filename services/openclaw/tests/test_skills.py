"""Tests for openclaw.skills — each skill handles errors gracefully."""
import pytest
from openclaw.channels.base import Message


class TestStatusSkill:
    @pytest.mark.asyncio
    async def test_status_fails_gracefully(self):
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
        assert "Could not fetch festival" in result


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
        assert "Could not start simulation" in result


class TestApproveSkill:
    @pytest.mark.asyncio
    async def test_approve_no_id(self):
        from openclaw.skills.approve import handle_approve
        result = await handle_approve(Message(text=""))
        assert "Usage" in result
