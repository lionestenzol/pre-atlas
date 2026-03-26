"""Slack channel implementation."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Channel, ChannelType

log = structlog.get_logger()

SLACK_API = "https://slack.com/api"


class SlackChannel(Channel):
    """Slack messaging via Web API."""

    channel_type = ChannelType.SLACK

    def __init__(self, token: str = "", channel: str = ""):
        self.token = token or config.slack_token
        self.channel = channel or config.slack_channel
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.token}"},
            )
        return self._client

    async def send_message(self, text: str, chat_id: str = "") -> bool:
        target = chat_id or self.channel
        if not self.token or not target:
            log.warning("slack.not_configured")
            return False
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{SLACK_API}/chat.postMessage",
                json={"channel": target, "text": text, "mrkdwn": True},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                log.error("slack.api_error", error=data.get("error"))
                return False
            self.connected = True
            return True
        except Exception as e:
            log.error("slack.send_failed", error=str(e))
            return False

    async def start(self) -> None:
        if not self.token:
            log.info("slack.skipped", reason="no token")
            return
        try:
            client = await self._get_client()
            resp = await client.post(f"{SLACK_API}/auth.test")
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                self.connected = True
                log.info("slack.connected", team=data.get("team"), user=data.get("user"))
            else:
                log.warning("slack.auth_failed", error=data.get("error"))
        except Exception as e:
            log.warning("slack.connect_failed", error=str(e))

    async def stop(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self.connected = False
