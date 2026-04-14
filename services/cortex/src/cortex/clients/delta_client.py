"""HTTP client for delta-kernel (:3001)."""

from __future__ import annotations

import httpx

from cortex.config import config


class DeltaClient:
    def __init__(self) -> None:
        self._base = config.DELTA_URL
        headers = {}
        if config.DELTA_API_KEY:
            headers["Authorization"] = f"Bearer {config.DELTA_API_KEY}"
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=10.0)

    async def health(self) -> bool:
        try:
            r = await self._client.get("/api/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_state(self) -> dict:
        r = await self._client.get("/api/state")
        r.raise_for_status()
        return r.json()

    async def post_timeline_event(self, event: dict) -> dict:
        # Normalize to delta timeline format: {type, source, data}
        payload = {
            "type": event.pop("type", event.pop("event", "AUTO_EXECUTED")),
            "source": event.pop("source", "cortex"),
            "data": event,  # remaining fields become data
        }
        r = await self._client.post("/api/timeline", json=payload)
        r.raise_for_status()
        return r.json()

    async def update_task_status(self, task_id: str, status: str, metadata: dict | None = None) -> dict:
        payload = {"task_id": task_id, "status": status}
        if metadata:
            payload["metadata"] = metadata
        r = await self._client.post("/api/tasks/status", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_pending_tasks(self) -> list[dict]:
        r = await self._client.get("/api/tasks", params={"status": "ready"})
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
