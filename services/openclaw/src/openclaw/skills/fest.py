"""Skill: /fest — festival progress.

No live HTTP backend since mosaic-orchestrator (:3005) was retired (festival FA0001).
Festival state lives in the `fest` CLI (WSL) / the festival-project filesystem, which
has no HTTP surface. Re-wire here if a festival API lands (candidate: cortex/optogon).
"""
import structlog

from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_fest(message: Message) -> str:
    """Festival progress isn't exposed over HTTP in the current fleet."""
    return (
        "Festival progress isn't available over chat right now "
        "(no live festival API — orchestrator retired). "
        "Run `fest progress` in the terminal."
    )
