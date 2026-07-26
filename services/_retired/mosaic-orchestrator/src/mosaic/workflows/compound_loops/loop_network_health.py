"""Loop 11: Network Health — contact-based relationship tracking.

Reads the network registry, computes active relationships and collaboration
score from real interaction data. Matches Loop 2's leverage opportunities
to specific contacts. Emits outreach reminders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .network_engine import compute_network_health_signals, match_opportunities_to_contacts


def compute_network_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute network health signals from the network registry."""
    registry = snapshot.network_registry

    if "error" in registry:
        return LoopResult(
            fired=False,
            input_summary="network_registry.json not available",
            output_summary="Skipped — no network registry data",
        )

    contacts = registry.get("contacts", {})
    if not contacts:
        return LoopResult(
            fired=True,
            input_summary="0 contacts in registry",
            output_summary="Empty network — add contacts to begin tracking",
            signal_delta={
                "network": {
                    "collaboration_score": 0,
                    "active_relationships": 0,
                    "outreach_this_week": 0,
                },
                "network_warning": "No contacts in registry. Network domain will remain critical.",
            },
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_network_health_signals(registry, now_iso)

    # Build signal delta — updates network_metrics.json
    signal_delta: dict[str, Any] = {
        "network": {
            "collaboration_score": int(signals["collaboration_score"]),
            "active_relationships": signals["active_relationships"],
            "outreach_this_week": 0,  # Will be counted from interactions
        },
    }

    # Count outreach this week (interactions in last 7 days)
    try:
        now = datetime.fromisoformat(now_iso)
        from datetime import timedelta
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        outreach_week = sum(
            1 for ix in registry.get("interactions", [])
            if ix.get("date", "") >= week_ago
        )
        signal_delta["network"]["outreach_this_week"] = outreach_week
    except (ValueError, TypeError):
        pass

    # Match Loop 2 leverage opportunities to contacts
    priorities = snapshot.strategic_priorities
    if "error" not in priorities:
        clusters = priorities.get("top_clusters", [])
        opp_labels = [
            f"{c.get('label', '')}: {c.get('revenue_tag', '')}"
            for c in clusters
            if c.get("revenue_tag") in ("productizable_system", "infrastructure_build", "consulting_ready")
        ]
        matches = match_opportunities_to_contacts(opp_labels, contacts)
        if matches:
            signal_delta["opportunity_matches"] = matches[:5]

    # Outreach due reminders
    if signals["outreach_due_count"] > 0:
        signal_delta["outreach_reminders"] = signals["outreach_due"]

    # Build summaries
    input_summary = (
        f"{signals['total_contacts']} contacts, "
        f"{signals['active_relationships']} active, "
        f"{signals['interaction_count']} interactions"
    )

    output_parts = [
        f"Collab: {signals['collaboration_score']:.0f}",
        f"Active: {signals['active_relationships']}",
    ]
    if signals["outreach_due_count"] > 0:
        output_parts.append(f"{signals['outreach_due_count']} follow-ups due")
    if signals["pipeline_value"] > 0:
        output_parts.append(f"Pipeline: ${signals['pipeline_value']:.0f}")

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
    )
