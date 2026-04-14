"""Pure-function progress calculator for project goal hierarchy.

All functions are pure: data in, result out. Zero I/O.
Used by loop_project_health.py and loop_compound_score.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def compute_subtask_progress(subtasks: list[dict[str, Any]]) -> float:
    """Percentage of subtasks completed (0-100). Returns 0 if no subtasks."""
    if not subtasks:
        return 0.0
    done = sum(1 for s in subtasks if s.get("status") == "done")
    return (done / len(subtasks)) * 100.0


def compute_milestone_progress(milestone: dict[str, Any]) -> float:
    """Progress of a single milestone based on its subtasks."""
    return compute_subtask_progress(milestone.get("subtasks", []))


def compute_goal_progress(goal: dict[str, Any]) -> float:
    """Progress of a goal, weighted by subtask count across milestones.

    A milestone with 10 subtasks contributes more weight than one with 2.
    Returns 0 if no milestones or no subtasks exist.
    """
    milestones = goal.get("milestones", [])
    if not milestones:
        return 0.0

    total_subtasks = 0
    total_done = 0
    for ms in milestones:
        subtasks = ms.get("subtasks", [])
        total_subtasks += len(subtasks)
        total_done += sum(1 for s in subtasks if s.get("status") == "done")

    if total_subtasks == 0:
        return 0.0
    return (total_done / total_subtasks) * 100.0


def find_blocked_by_deps(subtasks: list[dict[str, Any]]) -> list[str]:
    """Return IDs of subtasks whose dependencies are not all satisfied."""
    done_ids = {s["subtask_id"] for s in subtasks if s.get("status") == "done"}
    blocked: list[str] = []
    for s in subtasks:
        deps = s.get("depends_on", [])
        if deps and not all(d in done_ids for d in deps):
            blocked.append(s["subtask_id"])
    return blocked


def compute_deadline_pressure(goal: dict[str, Any], now_iso: str) -> float:
    """Deadline pressure score (0-100). 0 = no pressure, 100 = overdue.

    Ramps when elapsed time exceeds 75% but progress is behind expected.
    """
    due_at = goal.get("due_at")
    if not due_at:
        return 0.0

    try:
        now = datetime.fromisoformat(now_iso)
        due = datetime.fromisoformat(due_at)
    except (ValueError, TypeError):
        return 0.0

    if now >= due:
        return 100.0

    # Use goal created_at or generated_at as start reference, fallback to 30 days before due
    total_seconds = (due - (due.replace(day=1) if due.day > 1 else due)).total_seconds()
    if total_seconds <= 0:
        # Fallback: assume 30-day window
        total_seconds = 30 * 24 * 3600

    # Recalculate with a proper start: 30 days before due
    start = due.replace(tzinfo=due.tzinfo) if due.tzinfo else due
    window_start = datetime(start.year, start.month, max(1, start.day), tzinfo=start.tzinfo)
    # Simple: use 30-day window from (due - 30d)
    from datetime import timedelta
    window_start = due - timedelta(days=30)
    total_seconds = (due - window_start).total_seconds()
    elapsed_seconds = (now - window_start).total_seconds()

    if elapsed_seconds <= 0 or total_seconds <= 0:
        return 0.0

    elapsed_pct = min(1.0, elapsed_seconds / total_seconds)
    progress_pct = compute_goal_progress(goal) / 100.0

    # No pressure if ahead of schedule
    if progress_pct >= elapsed_pct:
        return 0.0

    # Ramp pressure when behind schedule, especially past 75%
    gap = elapsed_pct - progress_pct
    if elapsed_pct > 0.75:
        gap *= 1.5

    return min(100.0, gap * 100.0)


def compute_project_health_signals(
    goals_data: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Aggregate project health signals from goal hierarchy.

    Returns dict with keys usable by loop_compound_score and loop_project_health.
    """
    goals = goals_data.get("goals", [])
    if not goals:
        return {
            "total_goals": 0,
            "active_goals": 0,
            "done_goals": 0,
            "avg_progress": 0.0,
            "max_deadline_pressure": 0.0,
            "blocked_count": 0,
            "decomposition_coverage": 0.0,
            "completed_subtasks": [],
            "skill_tags": {},
        }

    active_goals = [g for g in goals if g.get("status") == "active"]
    done_goals = [g for g in goals if g.get("status") == "done"]

    # Progress across active goals
    progresses = [compute_goal_progress(g) for g in active_goals] if active_goals else [0.0]
    avg_progress = sum(progresses) / len(progresses)

    # Deadline pressure (max across all active goals)
    pressures = [compute_deadline_pressure(g, now_iso) for g in active_goals]
    max_pressure = max(pressures) if pressures else 0.0

    # Blocked subtasks
    blocked_count = 0
    for g in active_goals:
        for ms in g.get("milestones", []):
            blocked_count += len(find_blocked_by_deps(ms.get("subtasks", [])))

    # Decomposition coverage: % of active goals that have at least 1 milestone with subtasks
    decomposed = sum(
        1 for g in active_goals
        if any(ms.get("subtasks") for ms in g.get("milestones", []))
    )
    decomposition_coverage = (decomposed / len(active_goals) * 100.0) if active_goals else 0.0

    # Collect completed subtasks and their skill tags
    completed_subtasks: list[dict[str, Any]] = []
    skill_tags: dict[str, int] = {}
    for g in goals:
        for ms in g.get("milestones", []):
            for st in ms.get("subtasks", []):
                if st.get("status") == "done":
                    completed_subtasks.append({
                        "subtask_id": st["subtask_id"],
                        "title": st.get("title", ""),
                        "tags": st.get("tags", []),
                        "completed_at": st.get("completed_at"),
                    })
                    for tag in st.get("tags", []):
                        skill_tags[tag] = skill_tags.get(tag, 0) + 1

    return {
        "total_goals": len(goals),
        "active_goals": len(active_goals),
        "done_goals": len(done_goals),
        "avg_progress": round(avg_progress, 1),
        "max_deadline_pressure": round(max_pressure, 1),
        "blocked_count": blocked_count,
        "decomposition_coverage": round(decomposition_coverage, 1),
        "completed_subtasks": completed_subtasks,
        "skill_tags": skill_tags,
    }
