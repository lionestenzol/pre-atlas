"""HTTP client for aegis-fabric (:3002)."""

from __future__ import annotations

import httpx

from cortex.config import config


class AegisClient:
    def __init__(self) -> None:
        self._base = config.AEGIS_URL
        self._headers = {"X-API-Key": config.AEGIS_API_KEY}
        self._client = httpx.AsyncClient(
            base_url=self._base, headers=self._headers, timeout=10.0
        )

    async def health(self) -> bool:
        try:
            r = await self._client.get("/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def submit_action(self, action: str, params: dict) -> dict:
        """Submit an agent action through aegis policy gate.

        Returns dict with 'status' key: 'executed', 'denied', or 'pending_approval'.
        """
        payload = {
            "agent_id": config.AEGIS_AGENT_ID,
            "action": action,
            "params": params,
            "metadata": {"provider": "custom", "model_id": "cortex"},
        }
        r = await self._client.post("/api/v1/agent/action", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_pending_approvals(self) -> list[dict]:
        r = await self._client.get("/api/v1/approvals")
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("approvals", [])

    async def simulate_policy(self, action: str, params: dict) -> dict:
        payload = {
            "agent_id": config.AEGIS_AGENT_ID,
            "action": action,
            "params": params,
        }
        r = await self._client.post("/api/v1/policies/simulate", json=payload)
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
