"""Async client for inPACT state stored at delta-kernel /api/cycleboard."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from cortex.config import config


class InpactClient:
    """Thin async wrapper around delta-kernel's /api/cycleboard endpoints.

    Uses an asyncio.Lock to serialize read-modify-write sequences across
    concurrent callers sharing the same client (e.g., scheduler + manual
    endpoint calls). Does not protect against races with other processes.
    """

    def __init__(self) -> None:
        headers: dict[str, str] = {}
        if config.DELTA_API_KEY:
            headers["Authorization"] = f"Bearer {config.DELTA_API_KEY}"
        self._client = httpx.AsyncClient(base_url=config.DELTA_URL, headers=headers, timeout=10.0)
        self._rw_lock = asyncio.Lock()

    async def get_state(self) -> dict[str, Any]:
        """Return the full cycleboard state blob."""
        r = await self._client.get("/api/cycleboard")
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data") or {}
        return data.get("data", data) or {}

    async def put_state(self, state: dict[str, Any]) -> None:
        """Write the full state blob."""
        r = await self._client.put("/api/cycleboard", json=state)
        r.raise_for_status()

    async def merge_state(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Read-modify-write merge of top-level keys (atomic per-client)."""
        async with self._rw_lock:
            current = await self.get_state()
            merged = {**current, **updates}
            await self.put_state(merged)
            return merged

    async def transact(self, mutator) -> dict[str, Any]:
        """Apply an (async or sync) mutator(state) -> state under the lock.

        Use when a module reads state, decides updates based on it, and writes
        back — pass the mutator here instead of separate get_state + merge_state
        calls to keep the sequence atomic.
        """
        async with self._rw_lock:
            state = await self.get_state()
            result = mutator(state)
            if asyncio.iscoroutine(result):
                result = await result
            await self.put_state(result if result is not None else state)
            return state

    async def get_unified(self) -> dict[str, Any] | None:
        """Return Atlas /api/state/unified for governance context."""
        try:
            r = await self._client.get("/api/state/unified")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return None

    async def push_signals(self, signals: dict[str, Any]) -> None:
        """POST /api/signals/bulk — feeds the Markov routing core."""
        r = await self._client.post("/api/signals/bulk", json=signals)
        r.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
