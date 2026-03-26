"""OpenClaw client — wraps REST API on port 3004.

Integrates with:
  - POST /api/v1/notify        (send notification)
  - GET  /api/v1/channels      (list channels)
  - GET  /api/v1/health        (health check)
"""
import asyncio
import structlog
import httpx
from typing import Any

log = structlog.get_logger()

MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0


class OpenClawClient:
    """Async HTTP client for OpenClaw messaging gateway."""

    def __init__(self, base_url: str = "http://localhost:3004"):
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """HTTP request with retry logic (2 attempts, exponential backoff)."""
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self.client.request(method, path, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, httpx.ConnectError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    log.warning("openclaw_client.retry", path=path, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
        log.error("openclaw_client.failed", path=path, error=str(last_err))
        raise last_err

    async def health(self) -> dict:
        """Check OpenClaw health."""
        return await self._request("GET", "/api/v1/health")

    async def notify(self, channel: str, message: str, priority: str = "normal") -> dict:
        """Send a notification via OpenClaw."""
        return await self._request("POST", "/api/v1/notify", json={
            "channel": channel,
            "message": message,
            "priority": priority,
        })

    async def list_channels(self) -> dict:
        """List available notification channels."""
        return await self._request("GET", "/api/v1/channels")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
