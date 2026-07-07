# Habit XP/Streak Tracker

Extracted from conversation #496 "Morning Routine Assistance" (2025-02-09), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/496_morning-routine-assistance/`), verdict MINE, decided 2026-04-21.

## What this is

Most of this 278-message thread was live `npm run dev` / Next.js debugging (port conflicts, a stray `}` in `page.js`) for a habit-tracker app that the source never got fully working — the conversation ends mid-fix. But the thread also specifies, in JSON, a complete and coherent scoring rule set for daily habit check-ins:

| Status | Effect |
|---|---|
| Completed | `+xp`, streak `+1` |
| Partially Completed | `+xp/2`, streak unchanged |
| Skipped | `-xp`, streak reset to 0 |

`habit_tracker.py` implements this rule set as `update_habit()` (single habit, one day) and `run_check_in()` (a full day's log across multiple habits), since the source only ever specified these rules as data, never as code. 7/7 tests passing, covering all three statuses, multi-day streak accumulation, and habits omitted from a day's log.

## What was left out

The actual React/Next.js `HabitDashboard` component fragments in the thread are ~30 tiny, disconnected edit-and-fix snippets from an interactive debugging session (each 2-8 lines, patching one syntax error at a time) rather than one coherent component — nothing there was salvageable as a standalone UI artifact.

## Run the tests

```
python -m pytest test_habit_tracker.py -v
```
