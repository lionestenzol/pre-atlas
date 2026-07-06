"""Loop 5: Risk Cascade.

When drift_detector fires alerts, cascade impact to ALL domain signals.
Reduces prediction confidence, flags non-critical automation for pause.
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

DRIFT_SCORE_HIGH = 5         # drift_score >= this triggers full cascade
PREDICTION_DEGRADATION = 0.2  # reduce prediction confidences by 20%
ALERT_SEVERITY_WEIGHTS: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def compute_risk_cascade(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute risk cascade from drift alerts across all domains.

    Reads:
        snapshot.drift_alerts — drift_score, alerts[]
        snapshot.daily_payload — risk, predictions
        snapshot.prediction_results — loop_predictions confidence values
        snapshot.governance_state — lane_violations[]

    Returns:
        LoopResult with cascade constraints and prediction degradation.
    """
    drift = snapshot.drift_alerts
    payload = snapshot.daily_payload
    gov = snapshot.governance_state

    if "error" in drift:
        return LoopResult(fired=False, input_summary="Missing drift_alerts")

    drift_score = drift.get("drift_score", 0)
    alerts: list[dict[str, Any]] = drift.get("alerts", [])

    if not alerts and drift_score == 0:
        return LoopResult(
            fired=False,
            input_summary="No drift alerts, score=0",
        )

    # Compute risk pressure from alert severities
    risk_pressure = sum(
        ALERT_SEVERITY_WEIGHTS.get(a.get("severity", "LOW"), 1)
        for a in alerts
    )

    # Determine cascade severity
    if drift_score >= DRIFT_SCORE_HIGH or risk_pressure >= 6:
        cascade_severity = "HIGH"
    elif drift_score >= 3 or risk_pressure >= 3:
        cascade_severity = "MEDIUM"
    else:
        cascade_severity = "LOW"

    # Build constraints per domain
    constraints: list[dict[str, str]] = []
    pause_automation = False

    if cascade_severity == "HIGH":
        pause_automation = True
        constraints.append({
            "source_domain": "risk",
            "target_domain": "ALL",
            "constraint": f"Drift cascade: score={drift_score}, {len(alerts)} alerts",
            "severity": "HIGH",
        })

    # Specific alert type effects
    alert_types = {a.get("type", "") for a in alerts}

    if "archive_gaming" in alert_types:
        constraints.append({
            "source_domain": "risk",
            "target_domain": "project",
            "constraint": "Archive gaming detected — project score degraded",
            "severity": "HIGH",
        })

    if "closure_drought" in alert_types:
        constraints.append({
            "source_domain": "risk",
            "target_domain": "project",
            "constraint": "Closure drought — execution stalled",
            "severity": "MEDIUM",
        })

    if "energy_drought" in alert_types:
        constraints.append({
            "source_domain": "risk",
            "target_domain": "energy",
            "constraint": "Energy drought — sustained depletion",
            "severity": "HIGH",
        })

    # Lane violations compound risk
    lane_violations = gov.get("lane_violations", []) if "error" not in gov else []
    if lane_violations:
        constraints.append({
            "source_domain": "risk",
            "target_domain": "project",
            "constraint": f"{len(lane_violations)} lane violations active",
            "severity": "MEDIUM",
        })

    risk_level = payload.get("risk", "MEDIUM") if "error" not in payload else "MEDIUM"

    signal_delta = {
        "cascade_severity": cascade_severity,
        "prediction_degradation": PREDICTION_DEGRADATION if cascade_severity != "LOW" else 0,
        "automation_paused": pause_automation,
        "risk_pressure": risk_pressure,
        "alert_types": list(alert_types),
        "constraints": constraints,
    }

    return LoopResult(
        fired=True,
        input_summary=f"drift_score={drift_score}, alerts={len(alerts)}, risk={risk_level}",
        output_summary=(
            f"Cascade: {cascade_severity}. "
            f"Prediction degradation: {PREDICTION_DEGRADATION if cascade_severity != 'LOW' else 0}. "
            f"Automation {'PAUSED' if pause_automation else 'active'}"
        ),
        signal_delta=signal_delta,
        confidence=0.85,
    )
