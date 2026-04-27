"""Orchestrator — morning planner, midday check, evening reviewer.

These are the daily cadence agents. Each is idempotent-per-day via _OrchestratorMeta.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from cortex.inpact.client import InpactClient

log = logging.getLogger("cortex.inpact.orchestrator")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _meta(state: dict[str, Any]) -> dict[str, Any]:
    return dict(state.get("_OrchestratorMeta") or {})


def _default_template(day_type: str) -> dict[str, Any]:
    """Fallback template if state.DayTypeTemplates is empty."""
    templates = {
        "A": {
            "name": "Optimal",
            "timeBlocks": [
                {"time": "06:00", "title": "Morning Routine"},
                {"time": "08:00", "title": "Deep Work Block"},
                {"time": "12:00", "title": "Break / Walk"},
                {"time": "13:00", "title": "Execution Block"},
                {"time": "18:00", "title": "Evening Routine"},
            ],
            "goals": {
                "baseline": "Ship 1 meaningful outcome",
                "stretch": "Ship 2 outcomes + review",
            },
        },
        "B": {
            "name": "Low Energy",
            "timeBlocks": [
                {"time": "07:00", "title": "Gentle Start"},
                {"time": "09:00", "title": "One focused task"},
                {"time": "13:00", "title": "Rest"},
            ],
            "goals": {"baseline": "Complete 1 small task", "stretch": "Tidy space"},
        },
        "C": {
            "name": "Chaos",
            "timeBlocks": [
                {"time": "09:00", "title": "Triage"},
                {"time": "14:00", "title": "Most urgent thing"},
            ],
            "goals": {"baseline": "Survive the day intact", "stretch": "Close 1 loop"},
        },
    }
    return templates.get(day_type, templates["A"])


async def morning_plan(inpact: InpactClient, default_day_type: str = "A") -> dict[str, Any]:
    """Create today's plan if absent. Uses default_day_type from state.Settings."""
    today = _today()
    state = await inpact.get_state()
    plans = dict(state.get("DayPlans") or {})

    if plans.get(today):
        return {"ok": True, "skipped": "plan_exists"}

    day_type = (state.get("Settings") or {}).get("defaultDayType") or default_day_type
    template = (state.get("DayTypeTemplates") or {}).get(day_type) or _default_template(day_type)

    plan = {
        "id": secrets.token_urlsafe(6),
        "date": today,
        "day_type": day_type,
        "time_blocks": [
            {"id": secrets.token_urlsafe(6), "time": b["time"], "title": b["title"], "completed": False}
            for b in template.get("timeBlocks", [])
        ],
        "baseline_goal": {"text": (template.get("goals") or {}).get("baseline", ""), "completed": False},
        "stretch_goal": {"text": (template.get("goals") or {}).get("stretch", ""), "completed": False},
        "notes": "",
        "rating": None,
        "routines_completed": {},
        "auto": True,
    }
    plans[today] = plan

    meta = dict(state.get("_OrchestratorMeta") or {})
    meta["last_morning_plan"] = today
    await inpact.merge_state({"DayPlans": plans, "_OrchestratorMeta": meta})
    log.info("Morning Plan: created %s-day plan for %s", day_type, today)
    return {"ok": True, "day_type": day_type, "blocks": len(plan["time_blocks"])}


async def midday_check(inpact: InpactClient) -> dict[str, Any]:
    """Log a timeline note indicating block progress at midday."""
    today = _today()
    state = await inpact.get_state()
    meta = dict(state.get("_OrchestratorMeta") or {})
    if meta.get("last_midday_check") == today:
        return {"ok": True, "skipped": "already_checked_today"}

    plan = (state.get("DayPlans") or {}).get(today)
    if not plan:
        return {"ok": True, "skipped": "no_plan"}

    blocks = plan.get("time_blocks") or []
    done = sum(1 for b in blocks if b.get("completed"))
    pct = round((done / len(blocks)) * 100) if blocks else 0

    # Append a lightweight note; no nagging notification
    existing = plan.get("notes") or ""
    stamp = datetime.now(timezone.utc).strftime("%H:%M")
    plan["notes"] = (existing + f"\n[{stamp}] midday check: {done}/{len(blocks)} ({pct}%)").strip()

    plans = dict(state.get("DayPlans") or {})
    plans[today] = plan
    meta["last_midday_check"] = today
    await inpact.merge_state({"DayPlans": plans, "_OrchestratorMeta": meta})
    log.info("Midday Check: %d/%d blocks (%d%%)", done, len(blocks), pct)
    return {"ok": True, "progress": f"{done}/{len(blocks)}", "pct": pct}


async def evening_review(inpact: InpactClient) -> dict[str, Any]:
    """Draft a journal entry summarizing the day."""
    today = _today()
    state = await inpact.get_state()
    meta = dict(state.get("_OrchestratorMeta") or {})
    if meta.get("last_evening_review") == today:
        return {"ok": True, "skipped": "already_reviewed_today"}

    plan = (state.get("DayPlans") or {}).get(today) or {}
    blocks = plan.get("time_blocks") or []
    done_blocks = sum(1 for b in blocks if b.get("completed"))
    wins_today = [w for w in (state.get("MomentumWins") or []) if w.get("date") == today]
    tasks = state.get("AZTask") or []
    active = [t for t in tasks if t.get("status") == "In Progress"]
    stalled = [t for t in tasks if t.get("status") == "Stalled"]

    lines = [
        f"Evening review · {today}",
        f"Blocks: {done_blocks}/{len(blocks)}",
        f"Wins today: {len(wins_today)}",
        f"Tasks active: {len(active)}  stalled: {len(stalled)}",
    ]
    if plan.get("rating"):
        lines.append(f"Rating: {plan['rating']}/5")
    text = "\n".join(lines)

    journal = list(state.get("Journal") or [])
    journal.append({
        "id": secrets.token_urlsafe(6),
        "date": today,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "auto": True,
    })

    meta["last_evening_review"] = today
    await inpact.merge_state({"Journal": journal, "_OrchestratorMeta": meta})
    log.info("Evening Review: drafted journal entry for %s", today)
    return {"ok": True}
