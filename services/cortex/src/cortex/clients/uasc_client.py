"""HTTP client for UASC executor (:3008)."""

from __future__ import annotations

import httpx

from cortex.config import config


class UascClient:
    def __init__(self) -> None:
        self._base = config.UASC_URL
        self._client = httpx.AsyncClient(base_url=self._base, timeout=30.0)

    async def health(self) -> bool:
        try:
            r = await self._client.get("/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def exec_command(self, token: str, params: dict | None = None) -> dict:
        """Execute a UASC command token (e.g., @WORK, @BUILD, @CLOSE_LOOP)."""
        payload = {"token": token}
        if params:
            payload["params"] = params
        r = await self._client.post("/exec", json=payload)
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
