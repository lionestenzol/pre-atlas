"""HTTP client for Optogon path-runtime engine (:3010)."""

from __future__ import annotations

from typing import Any

import httpx

from cortex.config import config


class OptogonClient:
    def __init__(self) -> None:
        self._base = config.OPTOGON_URL
        # Longer timeout than UASC: /session/run can walk up to 30 internal turns,
        # each potentially invoking codex/sub-skills.
        self._client = httpx.AsyncClient(base_url=self._base, timeout=60.0)

    async def health(self) -> bool:
        try:
            r = await self._client.get("/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def run_session(
        self,
        path_id: str,
        initial_context: dict[str, Any] | None = None,
        context_package: dict[str, Any] | None = None,
        sitepull_audit_dir: str | None = None,
    ) -> dict[str, Any]:
        """Drive an Optogon path autonomously to completion (or a blocking node).

        Maps to POST /session/run on Optogon. Returns the full response dict
        including session_id, state, response, signals, outputs, turns_walked,
        and closed flags.
        """
        payload: dict[str, Any] = {"path_id": path_id}
        if initial_context is not None:
            payload["initial_context"] = initial_context
        if context_package is not None:
            payload["context_package"] = context_package
        if sitepull_audit_dir is not None:
            payload["sitepull_audit_dir"] = sitepull_audit_dir
        r = await self._client.post("/session/run", json=payload)
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
