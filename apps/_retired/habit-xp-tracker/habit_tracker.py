"""Habit XP/streak tracker — port of conversation #496 "Morning Routine
Assistance" (2025-02-09), Pre Atlas harvest pipeline.

The source thread's real content (buried in a Next.js "npm run dev"
debugging session that never got the app fully working) is a
deterministic scoring rule set for a daily habit check-in:

    Completed            -> +xp,     streak + 1
    Partially Completed   -> +xp/2,  streak unchanged
    Skipped               -> -xp,    streak reset to 0

Implemented here as the engine the source only ever specified in JSON,
never in working code.
"""

COMPLETED = "Completed"
PARTIAL = "Partially Completed"
SKIPPED = "Skipped"


def update_habit(state, status, xp_value):
    """Apply one day's check-in to a habit's {xp, streak} state."""
    xp = state.get("xp", 0)
    streak = state.get("streak", 0)

    if status == COMPLETED:
        return {"xp": xp + xp_value, "streak": streak + 1}
    if status == PARTIAL:
        return {"xp": xp + xp_value // 2, "streak": streak}
    if status == SKIPPED:
        return {"xp": xp - xp_value, "streak": 0}
    raise ValueError(f"unknown status: {status!r}")


def run_check_in(habit_states, xp_values, day_log):
    """Apply a day's check-in across all habits.

    `day_log` maps habit name -> status. Habits absent from the log are
    left unchanged. Returns the updated habit_states dict (new copy).
    """
    updated = dict(habit_states)
    for habit, status in day_log.items():
        current = updated.get(habit, {"xp": 0, "streak": 0})
        updated[habit] = update_habit(current, status, xp_values[habit])
    return updated
