"""MiroFish client — wraps REST API on port 3003.

Integrates with:
  - POST /api/v1/simulations     (start simulation)
  - GET  /api/v1/simulations     (list simulations)
  - GET  /api/v1/simulations/:id (get simulation detail)
  - GET  /api/v1/simulations/:id/report (get report)
  - DELETE /api/v1/simulations/:id (delete simulation)
  - GET  /api/v1/health          (health check)
"""
import asyncio
import structlog
import httpx
from typing import Any

log = structlog.get_logger()

MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0


class MirofishClient:
    """Async HTTP client for MiroFish swarm engine."""

    def __init__(self, base_url: str = "http://localhost:3003"):
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
                    log.warning("mirofish_client.retry", path=path, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
        log.error("mirofish_client.failed", path=path, error=str(last_err))
        raise last_err

    async def health(self) -> dict:
        """Check MiroFish health."""
        return await self._request("GET", "/api/v1/health")

    async def start_simulation(
        self, topic: str, agent_count: int = 20, tick_count: int = 10,
        document_text: str | None = None,
    ) -> dict:
        """Start a new simulation."""
        payload = {
            "topic": topic,
            "agent_count": agent_count,
            "tick_count": tick_count,
        }
        if document_text:
            payload["document_text"] = document_text
        return await self._request("POST", "/api/v1/simulations", json=payload)

    async def list_simulations(self) -> dict:
        """List all simulations."""
        return await self._request("GET", "/api/v1/simulations")

    async def get_simulation(self, simulation_id: str, from_tick: int = 0) -> dict:
        """Get simulation detail with tick data."""
        return await self._request(
            "GET", f"/api/v1/simulations/{simulation_id}",
            params={"from_tick": from_tick},
        )

    async def get_report(self, simulation_id: str) -> dict:
        """Get the simulation report."""
        return await self._request("GET", f"/api/v1/simulations/{simulation_id}/report")

    async def delete_simulation(self, simulation_id: str) -> dict:
        """Delete a simulation."""
        return await self._request("DELETE", f"/api/v1/simulations/{simulation_id}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
