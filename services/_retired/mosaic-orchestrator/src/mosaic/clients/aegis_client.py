"""Aegis-Fabric client — wraps policy engine REST API on port 3002.

All agent actions go through Aegis for policy evaluation:
  - POST /api/v1/agent/action → ALLOW | DENY | REQUIRE_HUMAN
  - GET  /api/v1/approvals     → pending approval queue
  - POST /api/v1/approvals/:id → approve/reject
"""
import asyncio
import structlog
import httpx
from typing import Any

log = structlog.get_logger()

MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0


class AegisClient:
    """Async HTTP client for aegis-fabric policy engine."""

    def __init__(self, base_url: str = "http://localhost:3002", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.api_key:
                headers["X-Aegis-Key"] = self.api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=30.0, headers=headers
            )
        return self._client

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """HTTP request with retry logic."""
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
                    log.warning("aegis_client.retry", path=path, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
        log.error("aegis_client.failed", path=path, error=str(last_err))
        raise last_err

    # --- Agent Actions ---

    async def submit_action(
        self,
        agent_id: str,
        action_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST /api/v1/agent/action — submit an action for policy evaluation.

        Returns: { decision: "ALLOW"|"DENY"|"REQUIRE_HUMAN", reason, ... }
        """
        body = {
            "agent_id": agent_id,
            "action": {
                "type": action_type,
                "payload": payload,
            },
        }
        return await self._request("POST", "/api/v1/agent/action", json=body)

    # --- Approvals ---

    async def list_approvals(self) -> dict[str, Any]:
        """GET /api/v1/approvals — list pending human approvals."""
        return await self._request("GET", "/api/v1/approvals")

    async def resolve_approval(self, approval_id: str, approved: bool, reason: str = "") -> dict[str, Any]:
        """POST /api/v1/approvals/{id} — approve or reject."""
        body = {"approved": approved, "reason": reason}
        return await self._request("POST", f"/api/v1/approvals/{approval_id}", json=body)

    # --- Health ---

    async def health(self) -> dict[str, Any]:
        """GET /health — basic health check."""
        return await self._request("GET", "/health")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
