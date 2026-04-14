"""Loop 9: Analyst — autonomous decision-making with confidence thresholds.

Runs LAST in the compound loop (after all domain scores are computed).
Evaluates pending decisions, auto-executes high-confidence ones,
escalates low-confidence ones for human review.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .analyst_engine import (
    evaluate_loop_closures,
    evaluate_priority_adjustments,
    evaluate_directive_execution,
    evaluate_lane_violations,
    compute_analyst_signals,
)


def compute_analyst_decisions(
    snapshot: CompoundSnapshot,
    domain_scores: dict[str, float] | None = None,
) -> LoopResult:
    """Compute autonomous decisions based on compound state.

    Args:
        snapshot: Immutable data snapshot
        domain_scores: Pre-computed domain scores (passed from compound_loop
                       since this runs after score computation)
    """
    governance = snapshot.governance_state
    drift = snapshot.drift_alerts
    energy = snapshot.energy_metrics
    actor_log = snapshot.auto_actor_log
    priorities = snapshot.strategic_priorities

    # Extract key signals
    drift_score = drift.get("drift_score", 0) if "error" not in drift else 0
    energy_level = energy.get("energy_level", 50) if "error" not in energy else 50

    now_iso = datetime.now(timezone.utc).isoformat()
    all_decisions: list[dict[str, Any]] = []

    # 1. Evaluate loop closures
    if "error" not in actor_log and "error" not in governance:
        all_decisions.extend(
            evaluate_loop_closures(actor_log, governance, drift_score, energy_level, now_iso)
        )

    # 2. Priority adjustments (needs domain scores)
    if domain_scores and "error" not in priorities:
        all_decisions.extend(
            evaluate_priority_adjustments(priorities, domain_scores, drift, now_iso)
        )

    # 3. Directive execution
    if "error" not in governance:
        all_decisions.extend(
            evaluate_directive_execution(governance, energy_level, drift_score, now_iso)
        )

    # 4. Lane violations
    if "error" not in governance:
        all_decisions.extend(
            evaluate_lane_violations(governance, now_iso)
        )

    if not all_decisions:
        return LoopResult(
            fired=False,
            input_summary="No pending decisions to evaluate",
            output_summary="No action needed",
        )

    signals = compute_analyst_signals(all_decisions)

    signal_delta: dict[str, Any] = {
        "analyst_decisions": all_decisions,
        "analyst_stats": signals,
    }

    input_summary = (
        f"{signals['decisions_made']} decisions evaluated "
        f"(energy={energy_level}, drift={drift_score})"
    )

    output_parts = [
        f"Auto: {signals['auto_executed']}",
        f"Escalated: {signals['escalated']}",
        f"Deferred: {signals['deferred']}",
        f"Avg confidence: {signals['avg_confidence']}",
    ]

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
        confidence=signals["avg_confidence"],
    )
