"""Loop 3: Completion → Financial Signal.

Track assets shipped, estimate revenue impact, flag financial pressure.
Revenue is projected (not actual) — stored in compound state, not pushed to finance signal.
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

# Conservative revenue estimates per asset type
REVENUE_ESTIMATES: dict[str, float] = {
    "product": 500.0,
    "service": 2000.0,
    "content": 100.0,
    "tool": 300.0,
    "automation": 200.0,
}

FINANCIAL_PRESSURE_RUNWAY = 2  # months — below this with no completions = HIGH pressure


def compute_completion_to_finance(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute financial projections from completion activity.

    Reads:
        snapshot.completion_stats — closed_week, closed_life
        snapshot.governance_state — active_lanes with type
        snapshot.finance_metrics — runway_months, money_delta
        snapshot.project_goals — subtask completions as supplementary closure signal

    Returns:
        LoopResult with projected_income in signal_delta (not pushed to finance signal).
    """
    stats = snapshot.completion_stats
    gov = snapshot.governance_state
    finance = snapshot.finance_metrics

    if "error" in finance:
        return LoopResult(
            fired=False,
            input_summary="Missing data: finance_metrics",
        )

    closed_week = stats.get("closed_week", 0) if "error" not in stats else 0

    # Supplement with subtask completions from project goals
    subtask_completions = 0
    project_goals = snapshot.project_goals
    if "error" not in project_goals:
        for goal in project_goals.get("goals", []):
            for ms in goal.get("milestones", []):
                subtask_completions += sum(
                    1 for st in ms.get("subtasks", []) if st.get("status") == "done"
                )
    # Each 3 subtask completions ≈ 1 closure equivalent for financial projection
    effective_closed = closed_week + (subtask_completions // 3)

    runway_months = finance.get("runway_months", 12)

    # Determine lane types for revenue estimation
    active_lanes = gov.get("active_lanes", []) if "error" not in gov else []
    lane_types: list[str] = []
    for lane in active_lanes:
        if isinstance(lane, dict):
            lane_types.append(lane.get("type", "content"))
        elif isinstance(lane, str):
            lane_types.append("content")

    # Estimate revenue: effective_closed × average lane revenue
    estimated_revenue = 0.0
    if effective_closed > 0 and lane_types:
        avg_revenue = sum(REVENUE_ESTIMATES.get(lt, 100.0) for lt in lane_types) / len(lane_types)
        estimated_revenue = effective_closed * avg_revenue
    elif effective_closed > 0:
        estimated_revenue = effective_closed * 100.0  # default content estimate

    # Financial pressure detection
    financial_pressure = "LOW"
    if runway_months < FINANCIAL_PRESSURE_RUNWAY and effective_closed == 0:
        financial_pressure = "HIGH"
    elif runway_months < FINANCIAL_PRESSURE_RUNWAY:
        financial_pressure = "MEDIUM"

    signal_delta = {
        "finance": {
            "projected_income": estimated_revenue,
            "financial_pressure": financial_pressure,
            "assets_shipped_week": effective_closed,
        }
    }

    subtask_note = f" (+{subtask_completions} subtasks)" if subtask_completions else ""
    return LoopResult(
        fired=effective_closed > 0 or financial_pressure != "LOW",
        input_summary=f"closed_week={closed_week}{subtask_note}, runway={runway_months}mo, lanes={len(lane_types)}",
        output_summary=(
            f"Projected revenue: ${estimated_revenue:.0f}. "
            f"Financial pressure: {financial_pressure}"
        ),
        signal_delta=signal_delta,
        confidence=0.5 if estimated_revenue > 0 else 0.3,
    )
