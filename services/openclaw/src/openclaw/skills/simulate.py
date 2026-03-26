"""Skill: /simulate — trigger a MiroFish simulation."""
import structlog
import httpx

from openclaw.config import config
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_simulate(message: Message) -> str:
    """Start a MiroFish simulation on the given topic."""
    topic = message.text.strip()
    if not topic:
        return "Usage: /simulate <topic>"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{config.mirofish_url}/api/v1/simulations",
                json={"topic": topic, "agent_count": 20, "tick_count": 10},
            )
            resp.raise_for_status()
            data = resp.json()

        sim_id = data.get("simulation_id", "unknown")
        return f"Simulation started: `{sim_id}`\nTopic: {topic}\nAgents: 20, Ticks: 10"
    except Exception as e:
        log.warning("skill.simulate_failed", error=str(e))
        return f"Could not start simulation: {e}"
