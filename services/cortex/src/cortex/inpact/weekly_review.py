"""Weekly Review — drafts a Sunday reflection from the last 7 days of activity.

Removes friction from the reflection step, which decays first when stall patterns
emerge. The draft is inserted into state.Reflections.weekly; user approves/edits.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cortex.inpact.client import InpactClient
from cortex.inpact.pattern_breaker import compute_pattern_metrics, _parse_iso

log = logging.getLogger("cortex.inpact.weekly_review")


def _in_last_7d(ts: str | None, now: datetime) -> bool:
    d = _parse_iso(ts)
    if not d:
        return False
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (now - d) <= timedelta(days=7)


def draft_reflection(state: dict[str, Any], now: datetime | None = None) -> str:
    """Compose a narrative reflection from the last 7 days of state."""
    now = now or datetime.now(timezone.utc)
    week_of = (now - timedelta(days=now.weekday())).date().isoformat()

    wins = [w for w in (state.get("MomentumWins") or [])
            if _in_last_7d(w.get("timestamp") or w.get("date"), now)]
    journal = [j for j in (state.get("Journal") or [])
               if _in_last_7d(j.get("createdAt") or j.get("date"), now)]
    plans = state.get("DayPlans") or {}
    ratings = []
    for date_key, plan in plans.items():
        try:
            d = datetime.fromisoformat(date_key).replace(tzinfo=timezone.utc)
            if (now - d) <= timedelta(days=7) and plan.get("rating"):
                ratings.append(plan["rating"])
        except ValueError:
            continue

    metrics = compute_pattern_metrics(state, now=now)
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    # Top 3 wins by recency
    top_wins = wins[-3:][::-1]

    lines: list[str] = []
    lines.append(f"# Weekly Review · Week of {week_of}")
    lines.append("")
    lines.append("## By the numbers")
    lines.append(f"- Tasks started: {metrics['started_last_7d']}")
    lines.append(f"- Tasks completed: {metrics['completed_last_7d']}")
    lines.append(f"- Currently stalled: {metrics['stalled_now']}")
    lines.append(f"- Stall rate: {metrics['stall_rate_pct']}%")
    lines.append(f"- Days rated: {len(ratings)}" + (f" (avg {avg_rating}/5)" if avg_rating else ""))
    lines.append(f"- Wins logged: {len(wins)}")
    lines.append(f"- Journal entries: {len(journal)}")
    lines.append("")
    if top_wins:
        lines.append("## Top wins")
        for w in top_wins:
            desc = w.get("description") or "(no description)"
            lines.append(f"- {desc}")
        lines.append("")
    lines.append("## Draft — edit before finalizing")
    if metrics["stalled_now"] >= 3:
        lines.append("- Multiple stalled tasks. Choose: close or restart — don't carry silently.")
    elif metrics["completed_last_7d"] == 0:
        lines.append("- No tasks completed. What is the one thing that would change that?")
    else:
        lines.append("- What worked? What should repeat next week?")
    lines.append("- What to carry forward:")
    lines.append("- What to drop:")
    return "\n".join(lines)


async def insert_weekly_draft(inpact: InpactClient, force: bool = False) -> dict[str, Any]:
    """Insert a weekly reflection draft into Reflections.weekly (Sunday or force)."""
    now = datetime.now(timezone.utc)
    if not force and now.weekday() != 6:  # 6 = Sunday
        return {"ok": True, "skipped": "not_sunday"}

    state = await inpact.get_state()
    reflections = state.get("Reflections") or {"weekly": [], "monthly": [], "quarterly": [], "yearly": []}
    weekly = list(reflections.get("weekly") or [])

    week_of = (now - timedelta(days=now.weekday())).date().isoformat()
    already = any(r.get("weekOf") == week_of and r.get("auto") for r in weekly)
    if already and not force:
        return {"ok": True, "skipped": "already_drafted"}

    draft = draft_reflection(state, now=now)
    weekly.append({
        "id": secrets.token_urlsafe(6),
        "date": now.date().isoformat(),
        "weekOf": week_of,
        "text": draft,
        "auto": True,
        "status": "draft",
    })
    reflections["weekly"] = weekly
    await inpact.merge_state({"Reflections": reflections})
    log.info("Weekly Review: inserted draft for week %s", week_of)
    return {"ok": True, "weekOf": week_of}
