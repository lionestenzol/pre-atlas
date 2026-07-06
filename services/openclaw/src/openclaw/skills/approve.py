"""Skill: /approve — approve a pending governance decision.

Wired to delta-kernel's confirmation gate: POST /api/actions/confirm/:id (:3001,
src/api/server.ts ~2625), populated by the governance daemon's Phase 3C calls to
`createPendingAction` (governance_daemon.ts:826). Successor to the approval path
lost when mosaic-orchestrator (:3005) was retired (festival FA0001).
"""
import httpx
import structlog

from openclaw.channels.base import Message
from openclaw.delta import confirm_pending_action

log = structlog.get_logger()


async def handle_approve(message: Message) -> str:
    """Confirm a pending action through delta-kernel's confirmation gate."""
    item_id = message.text.strip()
    if not item_id:
        return "Usage: /approve <item_id>"

    try:
        status, body = await confirm_pending_action(item_id)
    except httpx.HTTPError as exc:
        log.error("approve.confirm_unreachable", item_id=item_id, error=str(exc))
        return f"Could not reach delta-kernel to approve `{item_id}` — {exc}"

    if status == 200:
        execution = body.get("execution") or {}
        run_id = execution.get("run_id", "n/a")
        exec_status = execution.get("status", "unknown")
        return f"Approved `{item_id}` — execution {exec_status} (run {run_id})."
    if status == 404:
        return f"No pending action found with id `{item_id}`."
    if status == 409:
        return f"`{item_id}` was already resolved — {body.get('error', 'already handled')}."
    if status == 410:
        return f"`{item_id}` has expired and can no longer be approved."
    if status == 403:
        return f"Blocked by mode gate — {body.get('error', 'not allowed in the current mode')}."

    log.error("approve.unexpected_status", item_id=item_id, status=status, body=body)
    return f"delta-kernel returned an unexpected {status} for `{item_id}`."
