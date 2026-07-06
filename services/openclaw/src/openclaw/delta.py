"""Thin client for delta-kernel governance state.

Successor wiring after mosaic-orchestrator (:3005) was retired (festival FA0001).
The orchestrator used to proxy delta-kernel's `/api/state/unified` and reshape it;
openclaw now reads delta-kernel directly. delta-kernel enforces bearer auth, so we
first pull a token from the open `/api/auth/token` route, then read the unified state.
"""
import httpx

from openclaw.config import config


async def fetch_delta_derived() -> dict:
    """Return delta-kernel's derived governance block.

    Shape (keys used by callers): mode, risk, build_allowed, open_loops, streak_days.
    Raises on transport/auth/HTTP failure so callers can surface the error.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        tok_resp = await client.get(f"{config.delta_url}/api/auth/token")
        tok_resp.raise_for_status()
        token = tok_resp.json()["token"]

        resp = await client.get(
            f"{config.delta_url}/api/state/unified",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json().get("derived", {})
