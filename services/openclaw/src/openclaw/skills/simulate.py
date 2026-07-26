"""Skill: /simulate — trigger a swarm simulation.

MiroFish (:3003) was retired (festival FA0001) and its successor, cognitive-sensor,
exposes no simulation endpoint. Re-point when a simulation surface lands.
"""
import structlog

from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_simulate(message: Message) -> str:
    """Swarm simulations aren't available in the current fleet."""
    topic = message.text.strip()
    if not topic:
        return "Usage: /simulate <topic>"
    return (
        "Simulations aren't available right now "
        "(mirofish retired, no successor simulation endpoint)."
    )
