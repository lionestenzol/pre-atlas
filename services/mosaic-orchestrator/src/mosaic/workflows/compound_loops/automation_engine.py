"""Pure-function automation engine for the Automation agent.

All functions are pure: data in, result out. Zero I/O.
Handles scheduled task evaluation, condition checking, and execution logging.
"""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any


# Schedule intervals in hours
SCHEDULE_INTERVALS: dict[str, int] = {
    "daily": 24,
    "weekly": 168,
    "every_48h": 48,
    "every_12h": 12,
    "hourly": 1,
}


def compute_due_tasks(
    queue: dict[str, Any],
    now_iso: str,
) -> list[dict[str, Any]]:
    """Find tasks that are past their next_run_at."""
    tasks = queue.get("tasks", [])
    due: list[dict[str, Any]] = []

    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        return []

    for task in tasks:
        if task.get("status") != "active":
            continue

        next_run = task.get("next_run_at")
        if not next_run:
            continue

        try:
            next_dt = datetime.fromisoformat(next_run)
            if now >= next_dt:
                hours_overdue = (now - next_dt).total_seconds() / 3600
                due.append({
                    **task,
                    "hours_overdue": round(hours_overdue, 1),
                })
        except (ValueError, TypeError):
            continue

    return sorted(due, key=lambda t: -t.get("hours_overdue", 0))


def evaluate_conditions(
    task: dict[str, Any],
    energy_level: float,
    drift_score: float,
) -> tuple[bool, str]:
    """Check if task conditions are met. Returns (can_run, reason)."""
    conditions = task.get("conditions", {})

    energy_min = conditions.get("energy_min")
    if energy_min is not None and energy_level < energy_min:
        return False, f"Energy {energy_level} below minimum {energy_min}"

    drift_max = conditions.get("drift_max")
    if drift_max is not None and drift_score > drift_max:
        return False, f"Drift {drift_score} above maximum {drift_max}"

    return True, "All conditions met"


def advance_schedule(
    task: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Compute next_run_at from schedule. Returns updated task."""
    updated = copy.deepcopy(task)
    schedule = task.get("schedule", "daily")

    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        return updated

    # One-shot tasks complete after running
    if task.get("type") == "one_shot":
        updated["status"] = "completed"
        updated["last_run_at"] = now_iso
        updated["next_run_at"] = None
        return updated

    # Reminder tasks also complete
    if task.get("type") == "reminder":
        updated["status"] = "completed"
        updated["last_run_at"] = now_iso
        updated["next_run_at"] = None
        return updated

    # Recurring tasks advance
    hours = SCHEDULE_INTERVALS.get(schedule, 24)
    next_run = now + timedelta(hours=hours)

    updated["last_run_at"] = now_iso
    updated["next_run_at"] = next_run.isoformat()
    return updated


def log_execution(
    queue: dict[str, Any],
    task_id: str,
    success: bool,
    output: str = "",
    duration_seconds: float = 0,
    now_iso: str = "",
) -> dict[str, Any]:
    """Return new queue with execution result logged and schedule advanced."""
    updated = copy.deepcopy(queue)
    history = updated.setdefault("execution_history", [])

    history.append({
        "task_id": task_id,
        "run_at": now_iso or datetime.now(timezone.utc).isoformat(),
        "success": success,
        "output": output[:500],
        "duration_seconds": round(duration_seconds, 2),
    })

    # Keep last 100 results
    updated["execution_history"] = history[-100:]

    # Advance the task's schedule
    for i, task in enumerate(updated.get("tasks", [])):
        if task["id"] == task_id:
            updated["tasks"][i] = advance_schedule(task, now_iso)
            break

    updated["generated_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    return updated


def add_task(
    queue: dict[str, Any],
    task_type: str,
    action: str,
    schedule: str = "daily",
    conditions: dict[str, Any] | None = None,
    now_iso: str = "",
) -> tuple[dict[str, Any], str]:
    """Return new queue with task added. Immutable."""
    updated = copy.deepcopy(queue)
    tasks = updated.setdefault("tasks", [])

    task_id = f"task_{hashlib.sha256(f'{action}:{now_iso}'.encode()).hexdigest()[:12]}"

    try:
        now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)

    # Compute first next_run_at
    if task_type == "one_shot":
        next_run = schedule  # schedule IS the datetime for one_shot
    elif task_type == "reminder":
        next_run = schedule
    else:
        hours = SCHEDULE_INTERVALS.get(schedule, 24)
        next_run = (now + timedelta(hours=hours)).isoformat()

    tasks.append({
        "id": task_id,
        "type": task_type,
        "action": action,
        "schedule": schedule,
        "last_run_at": None,
        "next_run_at": next_run,
        "status": "active",
        "conditions": conditions or {},
    })

    updated["generated_at"] = now_iso or now.isoformat()
    return updated, task_id


def compute_automation_health_signals(
    queue: dict[str, Any],
    now_iso: str,
    energy_level: float = 50,
    drift_score: float = 0,
) -> dict[str, Any]:
    """Aggregate automation health signals."""
    tasks = queue.get("tasks", [])
    history = queue.get("execution_history", [])

    active_tasks = [t for t in tasks if t.get("status") == "active"]
    due = compute_due_tasks(queue, now_iso)

    # Count blocked (due but conditions not met)
    blocked = 0
    for t in due:
        can_run, _ = evaluate_conditions(t, energy_level, drift_score)
        if not can_run:
            blocked += 1

    # Execution success rate (last 20 runs)
    recent_runs = history[-20:]
    if recent_runs:
        success_rate = sum(1 for r in recent_runs if r.get("success")) / len(recent_runs)
    else:
        success_rate = 1.0  # No failures if no runs

    return {
        "total_tasks": len(tasks),
        "active_tasks": len(active_tasks),
        "tasks_due": len(due),
        "tasks_blocked": blocked,
        "tasks_ready": len(due) - blocked,
        "execution_success_rate": round(success_rate, 2),
        "total_runs": len(history),
    }
