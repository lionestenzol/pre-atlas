"""Skill: /pending — list pending governance actions awaiting /approve.

Reads delta-kernel's GET /api/actions/pending (populated by the governance
daemon's Phase 3C wiring, governance_daemon.ts:826). Completes the chat loop
alongside /approve: /pending shows the ids, /approve <id> confirms one.
"""
import structlog

from openclaw.channels.base import Message
from openclaw.delta import fetch_pending_actions

log = structlog.get_logger()


async def handle_pending(message: Message) -> str:
    """List pending actions awaiting confirmation."""
    try:
        pending = await fetch_pending_actions()
    except Exception as e:
        log.warning("skill.pending_failed", error=str(e))
        return f"Could not fetch pending actions: {e}"

    if not pending:
        return "No pending actions."

    lines = [f"*Pending Actions* ({len(pending)})"]
    for action in pending:
        label = action.get("label") or action.get("action_type", "unknown")
        action_type = action.get("action_type", "unknown")
        expires_at = action.get("expires_at")
        expiry_note = f" · expires {expires_at}" if expires_at is not None else ""
        lines.append(f"`{action.get('id')}` [{action_type}] {label}{expiry_note}")
    lines.append("\nApprove one with `/approve <id>`.")
    return "\n".join(lines)
