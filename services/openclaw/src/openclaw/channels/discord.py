"""Discord channel implementation."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Channel, ChannelType

log = structlog.get_logger()

DISCORD_API = "https://discord.com/api/v10"


class DiscordChannel(Channel):
    """Discord messaging via REST API (no gateway/websocket)."""

    channel_type = ChannelType.DISCORD

    def __init__(self, token: str = "", channel_id: str = ""):
        self.token = token or config.discord_token
        self.channel_id = channel_id or config.discord_channel_id
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Authorization": f"Bot {self.token}"},
            )
        return self._client

    async def send_message(self, text: str, chat_id: str = "") -> bool:
        target = chat_id or self.channel_id
        if not self.token or not target:
            log.warning("discord.not_configured")
            return False
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{DISCORD_API}/channels/{target}/messages",
                json={"content": text},
            )
            resp.raise_for_status()
            self.connected = True
            return True
        except Exception as e:
            log.error("discord.send_failed", error=str(e))
            return False

    async def start(self) -> None:
        if not self.token:
            log.info("discord.skipped", reason="no token")
            return
        try:
            client = await self._get_client()
            resp = await client.get(f"{DISCORD_API}/users/@me")
            resp.raise_for_status()
            bot = resp.json()
            self.connected = True
            log.info("discord.connected", bot_name=bot.get("username", "unknown"))
        except Exception as e:
            log.warning("discord.connect_failed", error=str(e))

    async def stop(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self.connected = False
