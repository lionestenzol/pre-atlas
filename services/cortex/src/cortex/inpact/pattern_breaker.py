"""Pattern Breaker — detects the start>jump>switch>stall>stop pattern in inPACT tasks.

Two detection tiers:
  - Day-based: tasks In Progress > N days without activity are flagged `Stalled`.
  - Weekly rollup: count of stalls surfaced on home dashboard via state.PatternMetrics.

The goal is not to nag intra-day. It's to make multi-day drift *visible as a number*.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from cortex.inpact.client import InpactClient

log = logging.getLogger("cortex.inpact.pattern_breaker")

STALL_DAYS = 2           # task In Progress > this many days = stalled
ARCHIVE_DAYS = 7         # stalled > this many days = archived (CLOSURE mode only)


def _parse_iso(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _task_last_activity(task: dict[str, Any]) -> datetime | None:
    """Best-effort: use updatedAt if present, else createdAt."""
    return _parse_iso(task.get("updatedAt")) or _parse_iso(task.get("createdAt"))


def find_stalled_tasks(state: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Return A-Z tasks that have been In Progress for more than STALL_DAYS."""
    now = now or datetime.now(timezone.utc)
    tasks = state.get("AZTask") or []
    stalled: list[dict[str, Any]] = []
    for t in tasks:
        if t.get("status") != "In Progress":
            continue
        last = _task_last_activity(t)
        if not last:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = (now - last).total_seconds() / 86400
        if age_days >= STALL_DAYS:
            stalled.append({**t, "_stall_days": round(age_days, 1)})
    return stalled


def compute_pattern_metrics(state: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Weekly rollup of the pattern."""
    now = now or datetime.now(timezone.utc)
    tasks = state.get("AZTask") or []
    history = state.get("History") or {}
    completed = history.get("completedTasks") or []

    seven_days_ago = now - timedelta(days=7)
    started_last_7d = 0
    stalled_now = 0
    for t in tasks:
        created = _task_last_activity(t)
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created and created >= seven_days_ago:
            started_last_7d += 1
        if t.get("status") == "In Progress":
            last = _task_last_activity(t)
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last and (now - last).total_seconds() / 86400 >= STALL_DAYS:
                stalled_now += 1

    completed_last_7d = sum(
        1 for c in completed
        if (d := _parse_iso(c.get("completedAt") or c.get("date")))
        and (d if d.tzinfo else d.replace(tzinfo=timezone.utc)) >= seven_days_ago
    )

    return {
        "started_last_7d": started_last_7d,
        "completed_last_7d": completed_last_7d,
        "stalled_now": stalled_now,
        "stall_rate_pct": round((stalled_now / started_last_7d) * 100, 1) if started_last_7d else 0.0,
        "computed_at": now.isoformat(),
    }


async def run_pattern_check(inpact: InpactClient) -> dict[str, Any]:
    """Main entry — detect stalls, update status, write PatternMetrics."""
    state = await inpact.get_state()
    stalled = find_stalled_tasks(state)
    metrics = compute_pattern_metrics(state)

    updated_tasks = state.get("AZTask") or []
    if stalled:
        stalled_ids = {t["id"] for t in stalled}
        for t in updated_tasks:
            if t.get("id") in stalled_ids and t.get("status") == "In Progress":
                t["status"] = "Stalled"
                t["stalledAt"] = datetime.now(timezone.utc).isoformat()
        log.info("Pattern Breaker: flagged %d tasks as Stalled", len(stalled))

    await inpact.merge_state({
        "AZTask": updated_tasks,
        "PatternMetrics": metrics,
    })
    return {"stalled_flagged": len(stalled), "metrics": metrics}
