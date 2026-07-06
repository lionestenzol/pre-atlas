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


async def confirm_pending_action(action_id: str) -> tuple[int, dict]:
    """Confirm a pending action via delta-kernel's confirmation gate.

    POSTs `/api/actions/confirm/{id}` with a bearer token from the open
    `/api/auth/token` route. Returns `(status_code, response_json)` rather than
    raising on non-2xx, because the gate's outcomes are semantically distinct
    and callers map them to user-facing messages: 404 not found, 409 already
    resolved, 410 expired, 403 blocked by mode gate. Raises only on transport
    or token-fetch failure.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        tok_resp = await client.get(f"{config.delta_url}/api/auth/token")
        tok_resp.raise_for_status()
        token = tok_resp.json()["token"]

        resp = await client.post(
            f"{config.delta_url}/api/actions/confirm/{action_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            body = resp.json()
        except ValueError:
            body = {}
        return resp.status_code, body


async def fetch_pending_actions() -> list[dict]:
    """Return the live list of PENDING actions from delta-kernel.

    Shape per item (server.ts GET /api/actions/pending): id, action_type,
    target_entity_id, label, status, created_at, expires_at, token. Raises on
    transport/auth/HTTP failure so callers can surface the error, matching
    fetch_delta_derived's contract.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        tok_resp = await client.get(f"{config.delta_url}/api/auth/token")
        tok_resp.raise_for_status()
        token = tok_resp.json()["token"]

        resp = await client.get(
            f"{config.delta_url}/api/actions/pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json().get("pending_actions", [])
