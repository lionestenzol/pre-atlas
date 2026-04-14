"""Pure-function decision engine for the Analyst agent.

All functions are pure: data in, decision out. Zero I/O.
Confidence thresholds determine auto-execute vs escalate vs defer.
"""
from __future__ import annotations

from typing import Any
import hashlib


# --- Confidence Thresholds ---

AUTO_EXECUTE_THRESHOLD = 0.85
ESCALATE_THRESHOLD = 0.50
ENERGY_EXECUTE_MIN = 50
ENERGY_ESCALATE_MIN = 30
DRIFT_EXECUTE_MAX = 5


def _decision_id(dtype: str, action: str, now_iso: str) -> str:
    """Generate a deterministic decision ID."""
    raw = f"{dtype}:{action}:{now_iso}"
    return f"d_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _make_decision(
    dtype: str,
    confidence: float,
    action: str,
    rationale: str,
    outcome: str,
    now_iso: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a decision dict."""
    return {
        "decision_id": _decision_id(dtype, action, now_iso),
        "type": dtype,
        "confidence": round(confidence, 2),
        "action": action,
        "rationale": rationale,
        "outcome": outcome,
        "created_at": now_iso,
        "approved_at": None,
        "context": context or {},
    }


# --- Loop Closure Decisions ---

def evaluate_loop_closures(
    auto_actor_log: dict[str, Any],
    governance: dict[str, Any],
    drift_score: float,
    energy_level: float,
    now_iso: str,
) -> list[dict[str, Any]]:
    """Evaluate pending loop closure recommendations."""
    decisions: list[dict[str, Any]] = []

    loops_closed = auto_actor_log.get("loops_closed", [])
    active_lanes = {
        lane.get("name", "").lower()
        for lane in governance.get("active_lanes", [])
        if isinstance(lane, dict)
    }

    for loop in loops_closed:
        decision_type = loop.get("decision", "")
        if decision_type not in ("CLOSE", "ARCHIVE"):
            continue

        convo_id = loop.get("convo_id", "unknown")
        title = loop.get("title", convo_id)

        # Lane-critical check: is this loop related to an active lane?
        is_lane_critical = any(
            lane_name in title.lower() for lane_name in active_lanes
        )

        # Compute confidence based on signals
        confidence = 0.7  # base

        if decision_type == "ARCHIVE":
            confidence += 0.15  # archives are lower risk
        if not is_lane_critical:
            confidence += 0.10
        if drift_score < 3:
            confidence += 0.05

        # Clamp
        confidence = min(1.0, confidence)

        # Determine outcome
        if confidence >= AUTO_EXECUTE_THRESHOLD and energy_level > ENERGY_EXECUTE_MIN and not is_lane_critical:
            outcome = "auto_executed"
        elif confidence >= ESCALATE_THRESHOLD:
            outcome = "escalated"
        else:
            outcome = "deferred"

        rationale_parts = [f"{decision_type} recommendation for '{title}'"]
        if is_lane_critical:
            rationale_parts.append("lane-critical (escalated)")
        rationale_parts.append(f"drift={drift_score}, energy={energy_level}")

        decisions.append(_make_decision(
            dtype="close_loop",
            confidence=confidence,
            action=f"{decision_type} loop: {title}",
            rationale=". ".join(rationale_parts),
            outcome=outcome,
            now_iso=now_iso,
            context={"convo_id": convo_id, "decision_type": decision_type, "lane_critical": is_lane_critical},
        ))

    return decisions


# --- Priority Adjustment Decisions ---

DOMAIN_TO_FOCUS_AREA: dict[str, list[str]] = {
    "project": ["Production"],
    "skill": ["Growth"],
    "network": ["Network"],
    "finance": ["Production", "Growth"],
    "energy": ["Personal"],
    "risk": ["Production"],
}


def evaluate_priority_adjustments(
    strategic_priorities: dict[str, Any],
    domain_scores: dict[str, float],
    drift_alerts: dict[str, Any],
    now_iso: str,
) -> list[dict[str, Any]]:
    """Generate priority adjustment decisions based on domain health."""
    decisions: list[dict[str, Any]] = []

    if "error" in strategic_priorities:
        return decisions

    clusters = strategic_priorities.get("top_clusters", [])
    if not clusters:
        return decisions

    # Find weak domains (score < 30)
    weak_domains = {k: v for k, v in domain_scores.items() if v < 30}
    strong_domains = {k: v for k, v in domain_scores.items() if v > 70}

    # Boost clusters aligned with weak domains
    for domain, score in weak_domains.items():
        target_areas = DOMAIN_TO_FOCUS_AREA.get(domain, [])
        for cluster in clusters:
            focus = cluster.get("focus_area", "")
            if focus in target_areas:
                label = cluster.get("label", "unknown")
                gap = cluster.get("gap", "")

                confidence = 0.90  # High confidence — domain is weak, cluster is aligned
                decisions.append(_make_decision(
                    dtype="adjust_priority",
                    confidence=confidence,
                    action=f"Boost priority: {label} (supports weak {domain} domain)",
                    rationale=f"{domain} domain at {score:.0f}/100. Cluster '{label}' in {focus} area with gap={gap}",
                    outcome="auto_executed",
                    now_iso=now_iso,
                    context={"domain": domain, "domain_score": score, "cluster_label": label, "direction": "boost"},
                ))
                break  # One boost per weak domain

    # Demote clusters in domains that are already strong (diminishing returns)
    for domain, score in strong_domains.items():
        target_areas = DOMAIN_TO_FOCUS_AREA.get(domain, [])
        for cluster in reversed(clusters):  # Start from bottom
            focus = cluster.get("focus_area", "")
            if focus in target_areas:
                label = cluster.get("label", "unknown")
                decisions.append(_make_decision(
                    dtype="adjust_priority",
                    confidence=0.70,
                    action=f"Deprioritize: {label} ({domain} domain already strong at {score:.0f})",
                    rationale=f"{domain} domain at {score:.0f}/100 — diminishing returns. Redirect effort to weaker domains",
                    outcome="escalated",
                    now_iso=now_iso,
                    context={"domain": domain, "domain_score": score, "cluster_label": label, "direction": "demote"},
                ))
                break

    return decisions


# --- Directive Execution Decisions ---

def evaluate_directive_execution(
    governance: dict[str, Any],
    energy_level: float,
    drift_score: float,
    now_iso: str,
) -> list[dict[str, Any]]:
    """Evaluate whether the daily directive should auto-execute."""
    decisions: list[dict[str, Any]] = []

    # Check if there's a pending directive via governance targets
    targets = governance.get("targets", {})
    daily_blocks = targets.get("daily_work_blocks", 0)
    min_build = targets.get("min_build_minutes", 0)

    if daily_blocks <= 0:
        return decisions

    confidence = 0.6  # base for directive execution

    if energy_level > ENERGY_EXECUTE_MIN:
        confidence += 0.20
    elif energy_level > ENERGY_ESCALATE_MIN:
        confidence += 0.10

    if drift_score < DRIFT_EXECUTE_MAX:
        confidence += 0.10

    confidence = min(1.0, confidence)

    if energy_level > ENERGY_EXECUTE_MIN and drift_score < DRIFT_EXECUTE_MAX:
        outcome = "auto_executed"
    elif energy_level > ENERGY_ESCALATE_MIN:
        outcome = "escalated"
    else:
        outcome = "deferred"

    decisions.append(_make_decision(
        dtype="execute_directive",
        confidence=confidence,
        action=f"Execute {daily_blocks} work blocks ({min_build}min build minimum)",
        rationale=f"Energy={energy_level}, drift={drift_score}. {'Safe to auto-execute' if outcome == 'auto_executed' else 'Needs review'}",
        outcome=outcome,
        now_iso=now_iso,
        context={"energy": energy_level, "drift_score": drift_score, "daily_blocks": daily_blocks},
    ))

    return decisions


# --- Lane Violation Decisions ---

def evaluate_lane_violations(
    governance: dict[str, Any],
    now_iso: str,
) -> list[dict[str, Any]]:
    """Auto-park lane violations (always high confidence)."""
    decisions: list[dict[str, Any]] = []

    violations = governance.get("lane_violations", [])
    for v in violations:
        title = v.get("title", "unknown")
        priority = v.get("priority", 0)
        rec = v.get("recommendation", "park")

        confidence = 0.95 if priority < 0.3 else 0.80

        decisions.append(_make_decision(
            dtype="park_idea",
            confidence=confidence,
            action=f"Park '{title}' (priority={priority:.2f}, rec={rec})",
            rationale=f"Violates lane focus. Priority {priority:.2f} below threshold",
            outcome="auto_executed" if confidence >= AUTO_EXECUTE_THRESHOLD else "escalated",
            now_iso=now_iso,
            context={"title": title, "priority": priority, "recommendation": rec},
        ))

    return decisions


# --- Aggregate Signals ---

def compute_analyst_signals(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate decision statistics."""
    auto_executed = sum(1 for d in decisions if d["outcome"] == "auto_executed")
    escalated = sum(1 for d in decisions if d["outcome"] == "escalated")
    deferred = sum(1 for d in decisions if d["outcome"] == "deferred")

    confidences = [d["confidence"] for d in decisions]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "decisions_made": len(decisions),
        "auto_executed": auto_executed,
        "escalated": escalated,
        "deferred": deferred,
        "avg_confidence": round(avg_confidence, 2),
        "decision_types": list({d["type"] for d in decisions}),
    }
