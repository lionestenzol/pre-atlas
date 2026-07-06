"""Skill: /approve — approve a pending governance decision.

No live HTTP backend since mosaic-orchestrator (:3005) was retired (festival FA0001).
delta-kernel's pending-action queue isn't wired yet — `createPendingAction` has no
caller (see Pre Atlas/CLAUDE.md "Known gap"). Re-point when that queue is populated.
"""
import structlog

from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_approve(message: Message) -> str:
    """Governance approvals aren't wired to a live service yet."""
    item_id = message.text.strip()
    if not item_id:
        return "Usage: /approve <item_id>"
    return (
        f"Approvals aren't wired to a live service yet — `{item_id}` was not submitted "
        "(orchestrator retired; delta-kernel pending-action queue not yet live)."
    )
