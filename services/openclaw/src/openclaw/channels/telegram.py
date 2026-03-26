"""Telegram channel implementation."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Channel, ChannelType, Message

log = structlog.get_logger()

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramChannel(Channel):
    """Telegram messaging via Bot API (HTTP, no polling dependency)."""

    channel_type = ChannelType.TELEGRAM

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or config.telegram_token
        self.chat_id = chat_id or config.telegram_chat_id
        self.base_url = TELEGRAM_API.format(token=self.token)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def send_message(self, text: str, chat_id: str = "") -> bool:
        target = chat_id or self.chat_id
        if not self.token or not target:
            log.warning("telegram.not_configured")
            return False
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": target, "text": text, "parse_mode": "Markdown"},
            )
            resp.raise_for_status()
            self.connected = True
            return True
        except Exception as e:
            log.error("telegram.send_failed", error=str(e))
            return False

    async def start(self) -> None:
        if not self.token:
            log.info("telegram.skipped", reason="no token")
            return
        # Verify token with getMe
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/getMe")
            resp.raise_for_status()
            bot = resp.json().get("result", {})
            self.connected = True
            log.info("telegram.connected", bot_name=bot.get("username", "unknown"))
        except Exception as e:
            log.warning("telegram.connect_failed", error=str(e))

    async def stop(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self.connected = False
