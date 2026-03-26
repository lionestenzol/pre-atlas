"""Skill: /status — returns current mode, lanes, and festival progress."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_status(message: Message) -> str:
    """Fetch system status from orchestrator and format for messaging."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{config.orchestrator_url}/api/v1/status")
            resp.raise_for_status()
            data = resp.json()

        mode = data.get("mode", "UNKNOWN")
        lanes = data.get("active_lanes", [])
        lanes_str = ", ".join(lanes) if lanes else "none"

        return (
            f"*System Status*\n"
            f"Mode: `{mode}`\n"
            f"Active lanes: {lanes_str}\n"
            f"Uptime: {data.get('uptime', 'N/A')}"
        )
    except Exception as e:
        log.warning("skill.status_failed", error=str(e))
        return f"Could not fetch status: {e}"
