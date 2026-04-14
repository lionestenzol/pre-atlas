"""Loop 2: Skill Mastery → Network Leverage.

When skills reach mastery thresholds, identify network opportunities
that leverage those skills.
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

MASTERY_THRESHOLD = 3       # mastery_count >= this triggers network opportunities
UTILIZATION_THRESHOLD = 70  # utilization_pct >= this confirms active skill usage
NETWORK_BOTTLENECK = 40     # collaboration_score < this = network is the bottleneck
COLLABORATION_BUMP = 5      # points added to collaboration_score when opportunities found


def compute_skill_to_network(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute network leverage opportunities from skill mastery.

    Reads:
        snapshot.skill_registry — live mastery/utilization (preferred)
        snapshot.skills_metrics — fallback mastery_count, utilization_pct
        snapshot.strategic_priorities — top_clusters with revenue_tag
        snapshot.network_metrics — collaboration_score, active_relationships

    Returns:
        LoopResult with signal_delta for network domain.
    """
    skills = snapshot.skills_metrics
    priorities = snapshot.strategic_priorities
    network = snapshot.network_metrics

    if "error" in network:
        return LoopResult(
            fired=False,
            input_summary="Missing data: network_metrics",
        )

    # Prefer live computation from skill_registry over stale skills_metrics
    registry = snapshot.skill_registry
    if "error" not in registry and registry.get("skills"):
        from .skill_progression import compute_skill_health_signals
        from datetime import datetime, timezone
        signals = compute_skill_health_signals(registry, datetime.now(timezone.utc).isoformat())
        mastery_count = signals["mastery_count"]
        utilization_pct = signals["utilization_pct"]
    elif "error" not in skills:
        mastery_count = skills.get("mastery_count", 0)
        utilization_pct = skills.get("utilization_pct", 0)
    else:
        return LoopResult(
            fired=False,
            input_summary="Missing data: skills_metrics and skill_registry",
        )
    collaboration_score = network.get("collaboration_score", 0)

    if mastery_count < MASTERY_THRESHOLD or utilization_pct < UTILIZATION_THRESHOLD:
        return LoopResult(
            fired=False,
            input_summary=(
                f"mastery={mastery_count} (need {MASTERY_THRESHOLD}), "
                f"utilization={utilization_pct}% (need {UTILIZATION_THRESHOLD}%)"
            ),
        )

    # Scan strategic priorities for productizable clusters
    opportunities: list[str] = []
    if "error" not in priorities:
        clusters = priorities.get("top_clusters", [])
        for cluster in clusters:
            revenue_tag = cluster.get("revenue_tag", "")
            if revenue_tag in ("productizable_system", "infrastructure_build", "consulting_ready"):
                opportunities.append(
                    f"{cluster.get('label', 'unknown')}: {revenue_tag}"
                )

    is_bottleneck = collaboration_score < NETWORK_BOTTLENECK
    new_collab = min(100, collaboration_score + COLLABORATION_BUMP)

    signal_delta = {
        "network": {
            "collaboration_score": new_collab,
        }
    }

    bottleneck_note = " BOTTLENECK: network score below threshold." if is_bottleneck else ""
    opp_text = f"{len(opportunities)} leverage opportunities" if opportunities else "no productizable clusters"

    return LoopResult(
        fired=True,
        input_summary=f"mastery={mastery_count}, utilization={utilization_pct}%, collab={collaboration_score}",
        output_summary=f"{opp_text}.{bottleneck_note} Collaboration +{COLLABORATION_BUMP}",
        signal_delta=signal_delta,
        confidence=min(1.0, mastery_count / 5),
    )
