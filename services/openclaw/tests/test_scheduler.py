"""Tests for openclaw.scheduler."""
import pytest
from unittest.mock import AsyncMock

from openclaw.scheduler import DailyScheduler
from openclaw.channels.base import ChannelType


class TestDailyScheduler:
    @pytest.mark.asyncio
    async def test_post_to_all_skips_disconnected(self):
        ch1 = AsyncMock()
        ch1.connected = True
        ch1.send_message = AsyncMock(return_value=True)

        ch2 = AsyncMock()
        ch2.connected = False

        scheduler = DailyScheduler(channels=[ch1, ch2])
        sent = await scheduler._post_to_all("test message")
        assert sent == 1
        ch1.send_message.assert_awaited_once_with("test message")
        ch2.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_post_daily_brief_without_service(self):
        scheduler = DailyScheduler(channels=[])
        brief = await scheduler.post_daily_brief()
        assert "Daily Brief" in brief
        assert "Could not fetch" in brief  # cognitive service not running

    @pytest.mark.asyncio
    async def test_stall_check_non_closure_returns_none(self):
        scheduler = DailyScheduler(channels=[])
        # orchestrator not running, check returns None
        result = await scheduler.check_closure_stall()
        assert result is None

    def test_cron_config(self):
        scheduler = DailyScheduler()
        cron = scheduler.get_cron_config()
        assert cron["hour"] == 9
        assert cron["minute"] == 30
