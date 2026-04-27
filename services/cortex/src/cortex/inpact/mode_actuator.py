"""Mode Actuator — translates Atlas governance mode into inPACT state changes.

Closes the governance→execution loop: when routing.ts transitions to a mode,
this module writes the corresponding inPACT actions.

Mode policies (defaults; can be tuned):
  RECOVER    : strip today's plan to baseline-only; unstart all In Progress tasks
  CLOSURE    : archive stalled tasks older than ARCHIVE_DAYS
  MAINTENANCE: no-op (steady state)
  BUILD      : no-op (manual planning)
  COMPOUND   : allow auto-promotion of Stalled back to In Progress on activity
  SCALE      : no-op (Cortex is trusted to add tasks — handled by orchestrator)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from cortex.inpact.client import InpactClient
from cortex.inpact.pattern_breaker import ARCHIVE_DAYS, _parse_iso

log = logging.getLogger("cortex.inpact.mode_actuator")


async def _get_mode(inpact: InpactClient) -> str | None:
    unified = await inpact.get_unified()
    if not unified:
        return None
    return (unified.get("derived") or {}).get("mode")


async def _apply_closure(state: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Archive Stalled tasks older than ARCHIVE_DAYS."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ARCHIVE_DAYS)
    tasks = list(state.get("AZTask") or [])
    history = state.get("History") or {}
    completed = list(history.get("completedTasks") or [])

    archived = 0
    remaining: list[dict[str, Any]] = []
    for t in tasks:
        if t.get("status") == "Stalled":
            stalled_at = _parse_iso(t.get("stalledAt"))
            if stalled_at and stalled_at.tzinfo is None:
                stalled_at = stalled_at.replace(tzinfo=timezone.utc)
            if stalled_at and stalled_at < cutoff:
                completed.append({
                    "id": t.get("id"),
                    "letter": t.get("letter"),
                    "task": t.get("task"),
                    "status": "Archived",
                    "archivedAt": now.isoformat(),
                    "reason": "stalled_archive",
                })
                archived += 1
                continue
        remaining.append(t)

    return {
        "AZTask": remaining,
        "History": {**history, "completedTasks": completed},
    }, archived


async def _apply_recover(state: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Strip today's plan to baseline-only; unstart In Progress tasks."""
    today = datetime.now(timezone.utc).date().isoformat()
    plans = dict(state.get("DayPlans") or {})
    plan = dict(plans.get(today) or {})

    blocks = plan.get("time_blocks") or []
    # Keep at most 2 blocks
    plan["time_blocks"] = blocks[:2]
    plans[today] = plan

    tasks = list(state.get("AZTask") or [])
    unstarted = 0
    for t in tasks:
        if t.get("status") == "In Progress":
            t["status"] = "Not Started"
            unstarted += 1

    return {"DayPlans": plans, "AZTask": tasks}, unstarted


async def apply_mode_actions(inpact: InpactClient, mode: str | None = None) -> dict[str, Any]:
    """Dispatch on current mode; write state changes accordingly."""
    mode = mode or await _get_mode(inpact)
    if not mode:
        return {"ok": False, "reason": "no_mode_available"}

    state = await inpact.get_state()
    # Avoid re-applying on the same mode multiple times per day
    last_applied = (state.get("_ModeActuatorMeta") or {}).get("last_applied") or {}
    today = datetime.now(timezone.utc).date().isoformat()
    if last_applied.get(mode) == today:
        return {"ok": True, "mode": mode, "skipped": "already_applied_today"}

    updates: dict[str, Any] = {}
    effect_count = 0
    if mode == "CLOSURE":
        updates, effect_count = await _apply_closure(state)
    elif mode == "RECOVER":
        updates, effect_count = await _apply_recover(state)
    else:
        return {"ok": True, "mode": mode, "skipped": "no_action_for_mode"}

    updates["_ModeActuatorMeta"] = {
        "last_applied": {**last_applied, mode: today},
        "last_run": datetime.now(timezone.utc).isoformat(),
    }
    await inpact.merge_state(updates)
    log.info("Mode Actuator: mode=%s applied (effect_count=%d)", mode, effect_count)
    return {"ok": True, "mode": mode, "effects": effect_count}
