"""Loop 14: Risk Mitigation — actionable recovery plans + interference detection.

Runs after risk_cascade, before analyst. Generates mitigation plans
for each active drift alert, detects personal interference patterns,
and computes adaptive guardrails.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .risk_engine import (
    generate_mitigation_plan,
    detect_interference,
    compute_adaptive_guardrails,
    compute_recovery_target,
)


def compute_risk_mitigation(
    snapshot: CompoundSnapshot,
    compound_score: int = 0,
    domain_scores: dict[str, float] | None = None,
) -> LoopResult:
    """Generate mitigation plans and detect interference."""
    drift = snapshot.drift_alerts
    energy = snapshot.energy_metrics
    completion = snapshot.completion_stats
    energy_log = snapshot.energy_log

    drift_score = drift.get("drift_score", 0) if "error" not in drift else 0
    alerts = drift.get("alerts", []) if "error" not in drift else []
    energy_level = energy.get("energy_level", 50) if "error" not in energy else 50

    # Get cascade severity from risk_cascade result (stored in governance)
    governance = snapshot.governance_state
    risk_level = governance.get("risk", "LOW") if "error" not in governance else "LOW"

    # Map risk string to cascade severity
    cascade_map = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
    cascade_severity = cascade_map.get(risk_level, "LOW")

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Generate mitigation plans for each alert
    plans: list[dict[str, Any]] = []
    for alert in alerts:
        plan = generate_mitigation_plan(alert, now_iso)
        plans.append(plan)

    # 2. Detect interference patterns
    energy_trends = {}
    if "error" not in energy_log and energy_log.get("entries"):
        from .energy_engine import detect_trends
        energy_trends = detect_trends(energy_log["entries"])

    interference = detect_interference(
        energy_trends,
        drift,
        snapshot.completion_stats if "error" not in snapshot.completion_stats else {},
        energy_level,
    )

    # 3. Compute adaptive guardrails
    guardrails = compute_adaptive_guardrails(drift_score, energy_level, cascade_severity)

    # 4. Recovery target
    recovery = None
    if compound_score > 0 and domain_scores:
        recovery = compute_recovery_target(compound_score, domain_scores, now_iso)

    # If no alerts and no interference, still fire with guardrails
    if not alerts and not interference:
        return LoopResult(
            fired=True,
            input_summary=f"drift={drift_score}, energy={energy_level}, cascade={cascade_severity}",
            output_summary=f"No active risks. Guardrails: {guardrails['risk_level']}",
            signal_delta={
                "risk_mitigation": {
                    "active_plans": [],
                    "interference_signals": [],
                    "guardrails": guardrails,
                    "recovery_target": recovery,
                },
            },
        )

    # Build signal delta
    signal_delta: dict[str, Any] = {
        "risk_mitigation": {
            "active_plans": plans,
            "interference_signals": interference,
            "guardrails": guardrails,
            "recovery_target": recovery,
        },
    }

    # Build summaries
    input_summary = (
        f"drift={drift_score}, {len(alerts)} alerts, "
        f"energy={energy_level}, cascade={cascade_severity}"
    )

    output_parts = [f"{len(plans)} mitigation plans"]
    if interference:
        patterns = [i["pattern"] for i in interference]
        output_parts.append(f"Interference: {', '.join(patterns)}")
    output_parts.append(f"Guardrails: {guardrails['risk_level']}")
    if recovery:
        output_parts.append(f"Target: {recovery['target_score']}/100 in {recovery['target_days']}d")

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
    )
