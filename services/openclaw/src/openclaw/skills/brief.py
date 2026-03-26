"""Skill: /brief — returns daily brief from cognitive sensor."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_brief(message: Message) -> str:
    """Fetch daily brief from cognitive sensor."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{config.cognitive_url}/api/v1/brief")
            resp.raise_for_status()
            data = resp.json()
        return data.get("brief", "No brief available today.")
    except Exception as e:
        log.warning("skill.brief_failed", error=str(e))
        return f"Could not fetch brief: {e}"
