"""Loop 13: Automation Health — scheduled task tracking and execution readiness.

Reads the automation queue, identifies due tasks, evaluates conditions,
and reports automation system health.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .automation_engine import compute_automation_health_signals, compute_due_tasks, evaluate_conditions


def compute_automation_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute automation health from the task queue."""
    queue = snapshot.automation_queue

    if "error" in queue:
        return LoopResult(
            fired=False,
            input_summary="automation_queue.json not available",
            output_summary="Skipped — no automation queue data",
        )

    tasks = queue.get("tasks", [])
    if not tasks:
        return LoopResult(
            fired=True,
            input_summary="0 tasks in automation queue",
            output_summary="Empty queue — add scheduled tasks to begin automation",
            signal_delta={"automation_warning": "No scheduled tasks configured."},
        )

    # Get energy and drift for condition evaluation
    energy = snapshot.energy_metrics
    drift = snapshot.drift_alerts
    energy_level = energy.get("energy_level", 50) if "error" not in energy else 50
    drift_score = drift.get("drift_score", 0) if "error" not in drift else 0

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_automation_health_signals(queue, now_iso, energy_level, drift_score)

    # Build signal delta
    signal_delta: dict[str, Any] = {
        "automation_health": {
            "active_tasks": signals["active_tasks"],
            "tasks_due": signals["tasks_due"],
            "tasks_blocked": signals["tasks_blocked"],
            "tasks_ready": signals["tasks_ready"],
            "success_rate": signals["execution_success_rate"],
        },
    }

    # List due tasks for execution
    due = compute_due_tasks(queue, now_iso)
    if due:
        due_summary: list[dict[str, Any]] = []
        for t in due:
            can_run, reason = evaluate_conditions(t, energy_level, drift_score)
            due_summary.append({
                "task_id": t["id"],
                "action": t["action"],
                "hours_overdue": t.get("hours_overdue", 0),
                "can_run": can_run,
                "block_reason": reason if not can_run else None,
            })
        signal_delta["due_tasks"] = due_summary

    if signals["tasks_blocked"] > 0:
        signal_delta["automation_blocked"] = (
            f"{signals['tasks_blocked']} tasks blocked by conditions (energy={energy_level}, drift={drift_score})"
        )

    # Build summaries
    input_summary = (
        f"{signals['active_tasks']} active tasks, "
        f"{signals['tasks_due']} due, "
        f"{signals['total_runs']} total runs"
    )

    output_parts = [
        f"Due: {signals['tasks_due']}",
        f"Ready: {signals['tasks_ready']}",
        f"Blocked: {signals['tasks_blocked']}",
        f"Success: {signals['execution_success_rate']:.0%}",
    ]

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
    )
