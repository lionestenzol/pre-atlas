"""Base channel abstraction for multi-platform messaging."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Awaitable


class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"


@dataclass
class Message:
    """A message to send or received from a channel."""
    text: str
    channel_type: ChannelType | None = None
    chat_id: str = ""
    sender: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Command:
    """A slash command registered with a channel."""
    name: str  # e.g. "status", "brief"
    description: str
    handler: Callable[[Message], Awaitable[str]] | None = None


class Channel(ABC):
    """Abstract base for messaging channel implementations."""

    channel_type: ChannelType
    connected: bool = False

    @abstractmethod
    async def send_message(self, text: str, chat_id: str = "") -> bool:
        """Send a message to the channel. Returns True on success."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect, authenticate, begin polling)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        ...

    def register_command(self, command: Command) -> None:
        """Register a slash command handler."""
        if not hasattr(self, "_commands"):
            self._commands: dict[str, Command] = {}
        self._commands[command.name] = command

    async def handle_command(self, name: str, message: Message) -> str:
        """Dispatch a command by name. Returns response text."""
        if not hasattr(self, "_commands"):
            self._commands = {}
        cmd = self._commands.get(name)
        if cmd and cmd.handler:
            return await cmd.handler(message)
        return f"Unknown command: /{name}"
