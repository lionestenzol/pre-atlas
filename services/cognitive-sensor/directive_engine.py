"""
Directive Engine — generates specific, confrontational directives from real data.

No LLM. No templates. Just your actual loop names, ages, and compliance numbers.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date

BASE = Path(__file__).parent.resolve()
DB = BASE / "results.db"


def get_loops_with_ages(loops):
    """
    Given a list of loop dicts (from cognitive_state.json['loops']),
    attach age_days by querying convo_time for each convo_id.
    Returns list sorted by age descending (oldest first).
    """
    if not loops:
        return []

    conn = sqlite3.connect(str(DB))
    today = date.today()
    result = []

    for loop in loops:
        convo_id = str(loop.get("convo_id", ""))
        title = loop.get("title", "(untitled)")
        score = loop.get("score", 0)

        row = conn.execute(
            "SELECT date FROM convo_time WHERE convo_id = ?", (convo_id,)
        ).fetchone()

        if row and row[0]:
            try:
                convo_date = date.fromisoformat(str(row[0])[:10])
                age_days = (today - convo_date).days
            except (ValueError, TypeError):
                age_days = None
        else:
            age_days = None

        result.append({
            "convo_id": convo_id,
            "title": title,
            "score": score,
            "age_days": age_days,
        })

    conn.close()

    # Sort: loops with known age first (oldest first), then unknown
    known = sorted([l for l in result if l["age_days"] is not None], key=lambda x: x["age_days"], reverse=True)
    unknown = [l for l in result if l["age_days"] is None]
    return known + unknown


def _avg_loop_age(loops_with_ages):
    """Average age in days across loops that have a known age."""
    ages = [l["age_days"] for l in loops_with_ages if l["age_days"] is not None]
    return sum(ages) / len(ages) if ages else None


def _days_since_last_closure(rolling_context):
    """How many days since closures_today > 0."""
    if not rolling_context:
        return None
    today_str = date.today().isoformat()
    # Walk backwards through snapshots
    for snap in reversed(rolling_context):
        if snap.get("closures_today", 0) > 0:
            try:
                snap_date = date.fromisoformat(snap["date"])
                return (date.today() - snap_date).days
            except (ValueError, KeyError):
                pass
    # No closure found in window
    return len(rolling_context)


def generate_directive(cognitive_state, loops_with_ages, behavioral_context):
    """
    Generate a specific, data-driven directive.

    Returns:
        {
          "confrontation": str  — the main hard-truth statement
          "action": str         — what to do right now
          "compliance_note": str or None  — follow-up on recent compliance
        }
    """
    closure = cognitive_state.get("closure", {})
    closure_quality = closure.get("closure_quality", 100.0)
    open_loops = closure.get("open", 0)

    rolling = behavioral_context.get("rolling", [])
    compliance_rate = behavioral_context.get("compliance_rate")

    avg_age = _avg_loop_age(loops_with_ages)
    days_since_closure = _days_since_last_closure(rolling)

    # --- Build confrontation line ---
    oldest = loops_with_ages[0] if loops_with_ages else None

    if oldest and oldest["age_days"] is not None and oldest["age_days"] > 30:
        avg_str = f"avg: {avg_age:.0f}d" if avg_age else "avg unknown"
        confrontation = (
            f"'{oldest['title']}' has been open {oldest['age_days']} days ({avg_str}). "
            f"Ship it this week or kill it permanently."
        )
    elif oldest and oldest["age_days"] is not None and oldest["age_days"] > 14:
        confrontation = (
            f"'{oldest['title']}' is {oldest['age_days']} days old. "
            f"That's 2 weeks. Decide today: close or archive."
        )
    elif oldest:
        confrontation = (
            f"'{oldest['title']}' is your oldest open loop. "
            f"Close or archive it before opening anything new."
        )
    elif open_loops > 0:
        confrontation = f"You have {open_loops} open loops. Close one before you do anything else."
    else:
        confrontation = "No open loops detected. Create something today."

    # --- Build action line ---
    if closure_quality < 30.0 and open_loops > 0:
        action = (
            f"Close quality is {closure_quality:.0f}% — you've been archiving, not closing. "
            f"Pick 1 loop and actually finish it, not archive it."
        )
    elif days_since_closure is not None and days_since_closure >= 5:
        action = (
            f"{days_since_closure}-day closure drought. "
            f"One real close today — not an archive, a finish."
        )
    elif oldest:
        action = f"Start with '{oldest['title']}'. No new work until it's resolved."
    else:
        action = "Close or archive one loop before building."

    # --- Build compliance note ---
    compliance_note = None
    if compliance_rate is not None:
        followed_count = round(compliance_rate * len(rolling))
        total_assessed = len([r for r in rolling if r.get("directive_followed") is not None])
        if total_assessed >= 3:
            pct = round(compliance_rate * 100)
            if compliance_rate < 0.4:
                compliance_note = (
                    f"You've followed the directive {followed_count} of the last {total_assessed} days ({pct}%). "
                    f"Ignoring it isn't working."
                )
            elif compliance_rate >= 0.7:
                compliance_note = (
                    f"You've followed the directive {pct}% of the last {total_assessed} days. Keep it up."
                )

    return {
        "confrontation": confrontation,
        "action": action,
        "compliance_note": compliance_note,
    }


if __name__ == "__main__":
    # Standalone test — load real data and print directive
    cog_path = BASE / "cognitive_state.json"
    cog = json.loads(cog_path.read_text(encoding="utf-8")) if cog_path.exists() else {}

    from behavioral_memory import get_rolling_context, get_compliance_rate
    loops = cog.get("loops", [])
    loops_with_ages = get_loops_with_ages(loops)

    behavioral_context = {
        "rolling": get_rolling_context(14),
        "compliance_rate": get_compliance_rate(30),
    }

    result = generate_directive(cog, loops_with_ages, behavioral_context)

    print("=== DIRECTIVE ENGINE OUTPUT ===")
    print(f"\nCONFRONTATION:\n  {result['confrontation']}")
    print(f"\nACTION:\n  {result['action']}")
    if result["compliance_note"]:
        print(f"\nCOMPLIANCE:\n  {result['compliance_note']}")
    print()
    print("Loops with ages:")
    for l in loops_with_ages[:5]:
        age = f"{l['age_days']}d" if l["age_days"] is not None else "unknown"
        print(f"  [{age}] {l['title']}")
