"""Loop 6: Compound Score.

Single 0-100 score measuring overall system health across all domains.
Weighted average with critical-domain penalty (any domain <30 drags score down).
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

# Domain weights (must sum to 1.0)
DOMAIN_WEIGHTS: dict[str, float] = {
    "project": 0.25,
    "skill": 0.15,
    "network": 0.10,
    "finance": 0.20,
    "energy": 0.20,
    "risk": 0.10,
}

CRITICAL_THRESHOLD = 30    # domain score below this triggers penalty
CRITICAL_PENALTY = 0.15    # 15% drag per critical domain


def compute_domain_score_project(snapshot: CompoundSnapshot) -> float:
    """0-100 score for project health.

    6 components:
      closure_momentum (25) — existing closure_ratio signal
      progress_signal  (25) — avg goal progress from project hierarchy
      decomp_health    (15) — % of goals with milestone breakdowns
      deadline_health  (15) — inverse of deadline pressure
      build_allowed    (10) — governance flag
      completion_bonus (10) — closed_week count

    Backward compat: when project_goals.json is missing, new signals
    default to neutral values producing scores similar to the old formula.
    """
    from .project_progress import compute_project_health_signals
    from datetime import datetime, timezone

    payload = snapshot.daily_payload
    stats = snapshot.completion_stats

    if "error" in payload:
        return 50.0

    # Component 1: closure momentum (max 25)
    closure_ratio = payload.get("closure_ratio", 0)
    if isinstance(closure_ratio, str):
        closure_ratio = float(closure_ratio.rstrip("%")) if closure_ratio else 0
    if closure_ratio <= 1.0:
        closure_ratio *= 100
    closure_momentum = min(25.0, closure_ratio * 0.25)

    # Component 5: build allowed (max 10)
    build_allowed = 10.0 if payload.get("build_allowed", False) else 0.0

    # Component 6: completion bonus (max 10)
    closed_week = stats.get("closed_week", 0) if "error" not in stats else 0
    completion_bonus = min(10.0, closed_week * 5.0)

    # Components 2-4: from project goals hierarchy
    goals_data = snapshot.project_goals
    if "error" in goals_data or not goals_data.get("goals"):
        # Neutral defaults when no hierarchy exists
        progress_signal = 12.5
        decomp_health = 7.5
        deadline_health = 15.0
    else:
        now_iso = datetime.now(timezone.utc).isoformat()
        signals = compute_project_health_signals(goals_data, now_iso)

        # Component 2: progress signal (max 25)
        progress_signal = signals["avg_progress"] * 0.25

        # Component 3: decomposition health (max 15)
        decomp_health = signals["decomposition_coverage"] * 0.15

        # Component 4: deadline health (max 15) — inverse of pressure
        deadline_health = max(0.0, 15.0 - signals["max_deadline_pressure"] * 0.15)

    return min(100.0, closure_momentum + progress_signal + decomp_health + deadline_health + build_allowed + completion_bonus)


def compute_domain_score_skill(snapshot: CompoundSnapshot) -> float:
    """0-100 score for skill health.

    Prefers live data from skill_registry when available,
    falls back to skills_metrics.json for backward compat.
    """
    from .skill_progression import compute_skill_health_signals
    from datetime import datetime, timezone

    registry = snapshot.skill_registry
    skills = snapshot.skills_metrics

    if "error" not in registry and registry.get("skills"):
        # Live computation from skill registry
        now_iso = datetime.now(timezone.utc).isoformat()
        signals = compute_skill_health_signals(registry, now_iso)

        utilization = signals["utilization_pct"]
        mastery = min(30.0, signals["mastery_count"] * 10.0)
        growth = min(20.0, signals["growth_count"] * 5.0)
        learning_bonus = 10.0 if signals["active_learning"] else 0.0
    elif "error" not in skills:
        # Fallback to stale metrics file
        utilization = skills.get("utilization_pct", 0)
        mastery = min(30.0, skills.get("mastery_count", 0) * 10.0)
        growth = min(20.0, skills.get("growth_count", 0) * 5.0)
        learning_bonus = 10.0 if skills.get("active_learning", False) else 0.0
    else:
        return 50.0

    return min(100.0, utilization * 0.4 + mastery + growth + learning_bonus)


def compute_domain_score_network(snapshot: CompoundSnapshot) -> float:
    """0-100 score for network health.

    Prefers live data from network_registry when available,
    falls back to network_metrics.json for backward compat.

    5 components:
      collaboration_score  (30) — from real interactions
      active_relationships (25) — contacts interacted with in 30 days
      outreach_health      (20) — inverse of overdue follow-ups
      pipeline_value       (15) — active opportunities
      base                 (10) — minimum if registry exists
    """
    registry = snapshot.network_registry
    network = snapshot.network_metrics

    if "error" not in registry and registry.get("contacts"):
        from .network_engine import compute_network_health_signals
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        signals = compute_network_health_signals(registry, now_iso)

        # Component 1: collaboration (max 30)
        collab = min(30.0, signals["collaboration_score"] * 0.3)

        # Component 2: active relationships (max 25)
        active = min(25.0, signals["active_relationships"] * 8.0)

        # Component 3: outreach health (max 20) — fewer overdue = healthier
        overdue = signals["outreach_due_count"]
        outreach_health = max(0.0, 20.0 - overdue * 5.0)

        # Component 4: pipeline (max 15)
        pipeline = min(15.0, signals["pipeline_count"] * 5.0)

        # Component 5: base (10 for having a registry)
        base = 10.0

        return min(100.0, collab + active + outreach_health + pipeline + base)

    # Fallback to stale metrics
    if "error" in network:
        return 50.0

    collab = network.get("collaboration_score", 0)
    relationships = min(30.0, network.get("active_relationships", 0) * 10.0)
    outreach = min(20.0, network.get("outreach_this_week", 0) * 10.0)

    return min(100.0, collab * 0.5 + relationships + outreach)


def compute_domain_score_finance(snapshot: CompoundSnapshot) -> float:
    """0-100 score for financial health.

    Prefers live data from financial_ledger when available,
    falls back to finance_metrics.json for backward compat.

    6 components:
      runway_score       (30) — months of runway
      income_trend       (20) — income growth vs last month
      budget_health      (20) — inverse of avg budget variance
      cash_position      (15) — positive balance indicator
      projection_conf    (10) — based on data points available
      alert_penalty     (-20) — per active alert
    """
    ledger = snapshot.financial_ledger
    finance = snapshot.finance_metrics

    if "error" not in ledger and ledger.get("transactions") is not None:
        from .finance_engine import compute_finance_health_signals
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        signals = compute_finance_health_signals(ledger, now_iso)

        # Component 1: runway (max 30)
        runway_score = min(30.0, signals["runway_months"] * 5.0)

        # Component 2: income trend (max 20)
        trend = signals["income_trend"]
        income_trend = 10.0 + min(10.0, max(-10.0, trend * 10.0))

        # Component 3: budget health (max 20) — lower variance = healthier
        avg_var = signals["avg_budget_variance"]
        budget_health = max(0.0, 20.0 - avg_var * 10.0)

        # Component 4: cash position (max 15)
        balance = signals["balance"]
        cash_position = 15.0 if balance > 1000 else (10.0 if balance > 0 else 0.0)

        # Component 5: projection confidence (max 10)
        projection_conf = signals["projection_confidence"] * 10.0

        # Component 6: alert penalty (-20 per alert, floored at -40)
        alert_penalty = max(-40.0, signals["alert_count"] * -20.0)

        return max(0.0, min(100.0,
            runway_score + income_trend + budget_health +
            cash_position + projection_conf + alert_penalty
        ))

    # Fallback to stale finance_metrics
    if "error" in finance:
        return 50.0

    runway = finance.get("runway_months", 0)
    money_delta = finance.get("money_delta", 0)
    runway_score = min(60.0, runway * 10.0)
    delta_score = 20.0 if money_delta > 0 else (0.0 if money_delta == 0 else -10.0)
    base = 20.0

    return max(0.0, min(100.0, base + runway_score + delta_score))


def compute_domain_score_energy(snapshot: CompoundSnapshot) -> float:
    """0-100 score for energy health.

    Uses energy_log trends when available for richer scoring.
    Falls back to energy_metrics.json for backward compat.
    """
    energy = snapshot.energy_metrics
    energy_log = snapshot.energy_log

    if "error" in energy:
        return 50.0

    energy_level = energy.get("energy_level", 50)
    mental_load = energy.get("mental_load", 5)
    sleep_quality = energy.get("sleep_quality", 3)
    burnout_penalty = -30.0 if energy.get("burnout_risk", False) else 0.0
    red_alert_penalty = -20.0 if energy.get("red_alert_active", False) else 0.0

    # Base score from metrics
    load_score = max(0.0, (10 - mental_load) * 5)
    sleep_score = sleep_quality * 6
    base = energy_level * 0.4 + load_score + sleep_score + burnout_penalty + red_alert_penalty

    # Trend bonus/penalty from energy_log
    if "error" not in energy_log and energy_log.get("entries"):
        from .energy_engine import compute_energy_health_signals
        from datetime import datetime, timezone

        signals = compute_energy_health_signals(energy_log, datetime.now(timezone.utc).isoformat())
        trend = signals["trends"]

        # Improving trend bonus (+10), declining penalty (-10)
        if trend["direction"] == "improving":
            base += 10.0
        elif trend["direction"] == "declining":
            base -= 10.0

        # Auto-update burnout from log detection
        if signals["burnout"]["burnout_detected"]:
            burnout_penalty = -30.0
            base += burnout_penalty  # Apply if not already applied

    return max(0.0, min(100.0, base))


def compute_domain_score_risk(snapshot: CompoundSnapshot) -> float:
    """0-100 score for risk health (100 = no risk, 0 = critical).

    Base score from drift detection, with bonuses for active mitigation
    and penalties for unresolved interference.
    """
    drift = snapshot.drift_alerts
    if "error" in drift:
        return 70.0

    drift_score = drift.get("drift_score", 0)
    alert_count = len(drift.get("alerts", []))

    # Base: invert drift
    base = 100.0
    base -= drift_score * 10
    base -= alert_count * 5

    # Mitigation bonuses from risk_state
    risk_state = snapshot.risk_state
    if "error" not in risk_state:
        plans = risk_state.get("active_plans", [])
        interference = risk_state.get("interference_signals", [])
        guardrails = risk_state.get("guardrails")

        # Having mitigation plans = self-correcting (+10)
        if plans:
            base += 10.0

        # Active guardrails = system is protected (+5)
        if guardrails and guardrails.get("risk_level") not in ("LOW", None):
            base += 5.0

        # Unresolved interference = additional risk (-10)
        if interference:
            base -= min(10.0, len(interference) * 5.0)

    return max(0.0, min(100.0, base))


def compute_compound_score(
    snapshot: CompoundSnapshot,
    loop_results: dict[str, LoopResult],
) -> tuple[int, dict[str, float]]:
    """Compute the 0-100 compound score and per-domain scores.

    The compound score is the weighted average of domain scores,
    with a penalty when any domain is in critical range (<30).
    A single critical domain drags the entire score down.

    Returns:
        (compound_score, domain_scores)
    """
    scores = {
        "project": compute_domain_score_project(snapshot),
        "skill": compute_domain_score_skill(snapshot),
        "network": compute_domain_score_network(snapshot),
        "finance": compute_domain_score_finance(snapshot),
        "energy": compute_domain_score_energy(snapshot),
        "risk": compute_domain_score_risk(snapshot),
    }

    # Weighted average
    weighted = sum(scores[k] * DOMAIN_WEIGHTS[k] for k in DOMAIN_WEIGHTS)

    # Critical domain penalty
    critical_count = sum(1 for v in scores.values() if v < CRITICAL_THRESHOLD)
    penalty = critical_count * CRITICAL_PENALTY
    compound = max(0, int(weighted * (1 - penalty)))

    return compound, scores
