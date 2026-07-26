"""Loop 7: Project Health — chain igniter.

Reads the goal-milestone-subtask hierarchy, computes progress signals,
and emits skill tags from completed subtasks as synthetic closures.
This is the mechanism that heats the compound chain:
  subtask completions → Loop 1 (closure→skill) → Loop 2 (skill→network) → Loop 3 (finance)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .project_progress import compute_project_health_signals


def compute_project_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute project health and emit chain-igniting signals."""
    goals_data = snapshot.project_goals

    if "error" in goals_data:
        return LoopResult(
            fired=False,
            input_summary="project_goals.json not available",
            output_summary="Skipped — no project hierarchy data",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_project_health_signals(goals_data, now_iso)

    # Don't fire if no goals exist
    if signals["total_goals"] == 0:
        return LoopResult(
            fired=False,
            input_summary="0 goals in hierarchy",
            output_summary="No goals to track",
        )

    # Build signal delta — this is what ignites the chain
    signal_delta: dict[str, Any] = {
        "avg_progress": signals["avg_progress"],
        "active_goals": signals["active_goals"],
        "done_goals": signals["done_goals"],
        "decomposition_coverage": signals["decomposition_coverage"],
        "blocked_count": signals["blocked_count"],
    }

    # Skill tags from completed subtasks → feeds Loop 1 (closure→skill)
    if signals["skill_tags"]:
        signal_delta["skills_from_subtasks"] = signals["skill_tags"]

    # Subtask completion count → synthetic closure signal
    subtask_completion_count = len(signals["completed_subtasks"])
    if subtask_completion_count > 0:
        signal_delta["subtask_completions"] = subtask_completion_count

    # Deadline pressure constraints
    constraints: list[dict[str, str]] = []
    if signals["max_deadline_pressure"] > 50:
        constraints.append({
            "source_domain": "project",
            "target_domain": "energy",
            "constraint": f"Deadline pressure at {signals['max_deadline_pressure']}% — prioritize project work over exploration",
            "severity": "HIGH" if signals["max_deadline_pressure"] > 75 else "MEDIUM",
        })
        signal_delta["constraints"] = constraints

    # Decomposition gap warning
    if signals["decomposition_coverage"] < 50 and signals["active_goals"] > 0:
        signal_delta["decomposition_warning"] = (
            f"Only {signals['decomposition_coverage']}% of active goals have subtask breakdowns"
        )

    fired = True
    input_summary = f"{signals['active_goals']} active goals, {subtask_completion_count} subtasks completed"
    output_summary_parts = [f"Progress: {signals['avg_progress']}%"]
    if signals["skill_tags"]:
        output_summary_parts.append(f"Skills: {', '.join(signals['skill_tags'].keys())}")
    if constraints:
        output_summary_parts.append(f"Deadline pressure: {signals['max_deadline_pressure']}%")

    return LoopResult(
        fired=fired,
        input_summary=input_summary,
        output_summary=" | ".join(output_summary_parts),
        signal_delta=signal_delta,
    )
