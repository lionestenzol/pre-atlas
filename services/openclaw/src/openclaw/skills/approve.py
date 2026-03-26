"""Skill: /approve — approve a pending governance decision."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_approve(message: Message) -> str:
    """Approve a pending item by ID."""
    item_id = message.text.strip()
    if not item_id:
        return "Usage: /approve <item_id>"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.orchestrator_url}/api/v1/approve",
                json={"item_id": item_id, "approved": True},
            )
            resp.raise_for_status()
            data = resp.json()
        return f"Approved: `{item_id}` — {data.get('message', 'OK')}"
    except Exception as e:
        log.warning("skill.approve_failed", error=str(e))
        return f"Could not approve: {e}"
