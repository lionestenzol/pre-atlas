"""Tests for openclaw.channels — base abstraction and channel implementations."""
import pytest
from openclaw.channels.base import Channel, ChannelType, Message, Command


class TestMessage:
    def test_defaults(self):
        msg = Message(text="hello")
        assert msg.text == "hello"
        assert msg.channel_type is None
        assert msg.chat_id == ""
        assert msg.timestamp is not None


class TestCommand:
    def test_create(self):
        cmd = Command(name="status", description="Get status")
        assert cmd.name == "status"
        assert cmd.handler is None


class TestChannelHandleCommand:
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """A concrete channel should return error for unknown commands."""
        from openclaw.channels.telegram import TelegramChannel
        ch = TelegramChannel(token="fake", chat_id="123")
        result = await ch.handle_command("nonexistent", Message(text=""))
        assert "Unknown command" in result

    @pytest.mark.asyncio
    async def test_registered_command(self):
        from openclaw.channels.telegram import TelegramChannel
        ch = TelegramChannel(token="fake", chat_id="123")

        async def handler(msg):
            return "handled!"

        ch.register_command(Command(name="test", description="test cmd", handler=handler))
        result = await ch.handle_command("test", Message(text=""))
        assert result == "handled!"


class TestTelegramChannel:
    @pytest.mark.asyncio
    async def test_send_without_token_returns_false(self):
        from openclaw.channels.telegram import TelegramChannel
        ch = TelegramChannel(token="", chat_id="")
        result = await ch.send_message("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_without_token_skips(self):
        from openclaw.channels.telegram import TelegramChannel
        ch = TelegramChannel(token="", chat_id="")
        await ch.start()
        assert ch.connected is False


class TestSlackChannel:
    @pytest.mark.asyncio
    async def test_send_without_token_returns_false(self):
        from openclaw.channels.slack import SlackChannel
        ch = SlackChannel(token="", channel="")
        result = await ch.send_message("test")
        assert result is False


class TestDiscordChannel:
    @pytest.mark.asyncio
    async def test_send_without_token_returns_false(self):
        from openclaw.channels.discord import DiscordChannel
        ch = DiscordChannel(token="", channel_id="")
        result = await ch.send_message("test")
        assert result is False
