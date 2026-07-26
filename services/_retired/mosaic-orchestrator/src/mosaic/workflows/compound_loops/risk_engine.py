"""Pure-function risk mitigation engine.

All functions are pure: data in, result out. Zero I/O.
Generates mitigation plans, detects interference patterns,
computes adaptive guardrails, and sets recovery targets.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any


# --- Mitigation Plans Per Alert Type ---

MITIGATION_PLAYBOOK: dict[str, dict[str, Any]] = {
    "closure_drought": {
        "actions": [
            "Decompose the oldest open loop into 2-3 subtasks",
            "Pick the smallest subtask and close it by end of day",
            "If blocked, archive with honest reason — not as fake closure",
        ],
        "estimated_days": 2,
        "success_criteria": ["1+ genuine closure in 48h", "closure_quality >= 70%"],
    },
    "archive_gaming": {
        "actions": [
            "Next closure must produce an artifact (doc, code, shipped asset)",
            "Review last 3 archives — reclassify any that had real output as closures",
            "Set quality gate: no archive without 1-sentence value extraction",
        ],
        "estimated_days": 3,
        "success_criteria": ["closure_quality >= 70% for 3 consecutive days", "0 empty archives"],
    },
    "energy_drought": {
        "actions": [
            "Cancel all deep work blocks today — lightweight tasks only",
            "Target 8h sleep tonight (set alarm, no screens after 10pm)",
            "15-minute walk outside before next work session",
            "If energy < 20, take full rest day — no guilt",
        ],
        "estimated_days": 2,
        "success_criteria": ["energy_level >= 40 for 2 consecutive days", "sleep_hours >= 7"],
    },
    "overexertion": {
        "actions": [
            "Mandatory 1-day rest — no loop closures, no deep work",
            "Tomorrow: max 1 work block, lightweight only",
            "Log energy before and after each session to calibrate",
        ],
        "estimated_days": 1,
        "success_criteria": ["energy_level stable or improving", "no closure attempts while energy < 30"],
    },
    "mode_stagnation": {
        "actions": [
            "Review why mode hasn't changed — what signal is stuck?",
            "Force 24h in adjacent mode (if CLOSURE, try MAINTENANCE)",
            "Identify the single biggest blocker and decompose it",
            "If truly stuck, archive 3 lowest-priority loops to shift closure_ratio",
        ],
        "estimated_days": 3,
        "success_criteria": ["mode change within 72h", "closure_ratio moves 5+ points"],
    },
}


def generate_mitigation_plan(
    alert: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Generate a mitigation plan for a specific drift alert."""
    alert_type = alert.get("type", "unknown")
    severity = alert.get("severity", "MEDIUM")

    playbook = MITIGATION_PLAYBOOK.get(alert_type)
    if not playbook:
        return {
            "alert_type": alert_type,
            "severity": severity,
            "actions": [f"Investigate {alert_type} alert and determine root cause"],
            "estimated_days": 3,
            "success_criteria": [f"drift_score reduced by 2+ points"],
            "created_at": now_iso,
        }

    return {
        "alert_type": alert_type,
        "severity": severity,
        "actions": playbook["actions"],
        "estimated_days": playbook["estimated_days"],
        "success_criteria": playbook["success_criteria"],
        "created_at": now_iso,
    }


# --- Interference Detection ---

def detect_interference(
    energy_trends: dict[str, Any],
    drift_alerts: dict[str, Any],
    completion_stats: dict[str, Any],
    energy_level: float,
) -> list[dict[str, Any]]:
    """Detect personal interference patterns from cross-signal analysis."""
    signals: list[dict[str, Any]] = []

    drift_score = drift_alerts.get("drift_score", 0) if "error" not in drift_alerts else 0
    alerts = drift_alerts.get("alerts", []) if "error" not in drift_alerts else []
    alert_types = {a.get("type") for a in alerts}

    closed_week = completion_stats.get("closed_week", 0) if "error" not in completion_stats else 0
    energy_direction = energy_trends.get("direction", "stable")
    energy_delta = energy_trends.get("delta", 0)

    # Pattern 1: Avoidance/procrastination
    # Energy OK but no closures + high drift = avoiding work
    if energy_level >= 40 and closed_week == 0 and drift_score >= 3:
        signals.append({
            "type": "internal",
            "pattern": "avoidance_procrastination",
            "impact": "blocks_execution",
            "confidence": min(0.9, 0.5 + drift_score * 0.1),
            "response": "Pick the smallest possible task and do only that. 15-minute timer. No switching.",
        })

    # Pattern 2: Overexertion despite depletion
    # Energy declining but closures happening = pushing through burnout
    if energy_direction == "declining" and closed_week > 0 and energy_level < 40:
        signals.append({
            "type": "internal",
            "pattern": "overexertion_despite_depletion",
            "impact": "reduces_quality",
            "confidence": 0.8,
            "response": "Stop closing loops today. Rest is the highest-leverage action right now.",
        })

    # Pattern 3: Directive resistance
    # High drift + energy OK = system gives direction but user ignores
    if drift_score >= 5 and energy_level >= 50:
        signals.append({
            "type": "internal",
            "pattern": "directive_resistance",
            "impact": "delays_start",
            "confidence": min(0.85, 0.4 + drift_score * 0.1),
            "response": "Review today's directive. If it feels wrong, change it — but don't ignore it.",
        })

    # Pattern 4: External blocker
    # No closures + no energy issue + no drift pattern = something external
    if closed_week == 0 and energy_level >= 50 and drift_score < 3:
        signals.append({
            "type": "external",
            "pattern": "possible_external_blocker",
            "impact": "blocks_execution",
            "confidence": 0.5,
            "response": "Check: are you waiting on someone? A tool? A decision? Name the blocker.",
        })

    # Pattern 5: Energy collapse
    # Rapid energy decline = environmental or health issue
    if energy_delta < -15 and energy_level < 35:
        signals.append({
            "type": "environmental",
            "pattern": "energy_collapse",
            "impact": "blocks_execution",
            "confidence": 0.85,
            "response": "Health check: sleep deficit, illness, or environmental stressor? Address root cause before work.",
        })

    return signals


# --- Adaptive Guardrails ---

def compute_adaptive_guardrails(
    drift_score: float,
    energy_level: float,
    cascade_severity: str,
) -> dict[str, Any]:
    """Compute graduated guardrails based on risk level."""
    # Determine risk level from multiple signals
    if drift_score >= 7 or (cascade_severity == "HIGH" and energy_level < 30):
        risk_level = "CRITICAL"
    elif drift_score >= 5 or cascade_severity == "HIGH":
        risk_level = "HIGH"
    elif drift_score >= 3 or cascade_severity == "MEDIUM":
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    guardrail_map = {
        "CRITICAL": {
            "risk_level": "CRITICAL",
            "max_work_blocks": 0,
            "automation_scope": "paused",
            "idea_moratorium": True,
            "deep_work_allowed": False,
        },
        "HIGH": {
            "risk_level": "HIGH",
            "max_work_blocks": 1,
            "automation_scope": "all_escalated",
            "idea_moratorium": True,
            "deep_work_allowed": False,
        },
        "MEDIUM": {
            "risk_level": "MEDIUM",
            "max_work_blocks": 2,
            "automation_scope": "escalate_non_archive",
            "idea_moratorium": True,
            "deep_work_allowed": True,
        },
        "LOW": {
            "risk_level": "LOW",
            "max_work_blocks": 3,
            "automation_scope": "full",
            "idea_moratorium": False,
            "deep_work_allowed": True,
        },
    }

    return guardrail_map.get(risk_level, guardrail_map["LOW"])


# --- Recovery Target ---

def compute_recovery_target(
    compound_score: int,
    domain_scores: dict[str, float],
    now_iso: str,
) -> dict[str, Any]:
    """Compute a recovery target based on current compound state."""
    # Target: get compound score to at least 50
    target_score = max(50, compound_score + 15)

    # Find weakest domain for focused recovery
    if domain_scores:
        weakest = min(domain_scores, key=domain_scores.get)
        weakest_score = domain_scores[weakest]
    else:
        weakest = "unknown"
        weakest_score = 0

    # Estimate days based on gap
    gap = target_score - compound_score
    estimated_days = max(1, min(14, gap // 5))

    try:
        now = datetime.fromisoformat(now_iso)
        checkpoint = now + timedelta(days=min(3, estimated_days))
    except (ValueError, TypeError):
        checkpoint = now_iso

    return {
        "target_score": target_score,
        "target_days": estimated_days,
        "current_score": compound_score,
        "weakest_domain": weakest,
        "weakest_score": round(weakest_score, 1),
        "focus": f"Improve {weakest} domain from {weakest_score:.0f} to {weakest_score + 15:.0f}",
        "checkpoint_next": checkpoint.isoformat() if isinstance(checkpoint, datetime) else checkpoint,
    }


# --- Health Signals ---

def compute_risk_health_signals(
    risk_state: dict[str, Any],
    drift_alerts: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate risk health signals for compound scoring."""
    active_plans = risk_state.get("active_plans", []) if "error" not in risk_state else []
    interference = risk_state.get("interference_signals", []) if "error" not in risk_state else []
    guardrails = risk_state.get("guardrails") if "error" not in risk_state else None

    drift_score = drift_alerts.get("drift_score", 0) if "error" not in drift_alerts else 0
    alert_count = len(drift_alerts.get("alerts", [])) if "error" not in drift_alerts else 0

    has_mitigation = len(active_plans) > 0
    has_unresolved_interference = len(interference) > 0
    guardrails_active = guardrails is not None and guardrails.get("risk_level") != "LOW"

    return {
        "drift_score": drift_score,
        "alert_count": alert_count,
        "has_mitigation": has_mitigation,
        "mitigation_count": len(active_plans),
        "interference_count": len(interference),
        "guardrails_active": guardrails_active,
        "guardrail_level": guardrails.get("risk_level", "LOW") if guardrails else "LOW",
    }
