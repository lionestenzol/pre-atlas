"""Skill: /fest — returns festival progress from orchestrator."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_fest(message: Message) -> str:
    """Fetch festival progress from orchestrator."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{config.orchestrator_url}/api/v1/festivals")
            resp.raise_for_status()
            data = resp.json()

        festivals = data.get("festivals", [])
        if not festivals:
            return "No active festivals."

        lines = ["*Festival Progress*"]
        for f in festivals:
            name = f.get("name", "unknown")
            progress = f.get("progress", 0)
            lines.append(f"  {name}: {progress}%")
        return "\n".join(lines)
    except Exception as e:
        log.warning("skill.fest_failed", error=str(e))
        return f"Could not fetch festival data: {e}"
