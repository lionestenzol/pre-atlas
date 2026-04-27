"""Signal feeder — converts inPACT state into LifeSignals and pushes to delta-kernel.

This is the reverse trigger. inPACT activity becomes governance input automatically.
routing.ts (LOCKED) remains deterministic; we only feed it better data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from cortex.inpact.client import InpactClient

log = logging.getLogger("cortex.inpact.signals")


def _today_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def derive_signals(state: dict[str, Any]) -> dict[str, Any]:
    """Compute bucketed signals from inPACT state.

    Maps inPACT activity to the signal categories the routing core consumes.
    """
    today = _today_date()
    plans = state.get("DayPlans") or {}
    plan = plans.get(today) or {}

    blocks = plan.get("time_blocks") or []
    completed_blocks = sum(1 for b in blocks if b.get("completed"))

    tasks = state.get("AZTask") or []
    active_tasks = [t for t in tasks if t.get("status") in ("In Progress", "Stalled")]
    stalled = [t for t in tasks if t.get("status") == "Stalled"]

    wins_today = sum(
        1 for w in (state.get("MomentumWins") or [])
        if w.get("date") == today
    )

    # Energy signal: mental_load scaled from stall count
    mental_load = min(10, 3 + len(stalled))

    # Open loops approximation: A-Z tasks that are active or stalled
    # (delta-kernel also computes its own open_loops; this one reflects inPACT view)
    signals: dict[str, Any] = {
        "energy": {
            "mental_load": mental_load,
            "burnout_risk": len(stalled) >= 3,
        },
    }

    log.debug(
        "Signals derived: blocks=%d/%d, active=%d, stalled=%d, wins=%d",
        completed_blocks, len(blocks), len(active_tasks), len(stalled), wins_today,
    )
    return signals


async def push_derived_signals(inpact: InpactClient) -> dict[str, Any]:
    """Read inPACT state, derive signals, push to /api/signals/bulk."""
    state = await inpact.get_state()
    signals = derive_signals(state)
    try:
        await inpact.push_signals(signals)
        log.info("Pushed signals from inPACT state")
        return {"ok": True, "signals": signals}
    except Exception as e:
        log.warning("Signal push failed: %s", e)
        return {"ok": False, "error": str(e)}
