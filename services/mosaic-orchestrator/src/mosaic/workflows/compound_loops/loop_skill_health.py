"""Loop 8: Skill Health — keeps mastery_count current.

Reads the skill registry, computes mastery/utilization/growth signals,
and pushes them back to skills_metrics.json. This is what makes
Loop 2 (skill→network) fire by keeping mastery_count accurate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .skill_progression import compute_skill_health_signals


def compute_skill_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute skill health signals from the skill registry."""
    registry = snapshot.skill_registry

    if "error" in registry:
        return LoopResult(
            fired=False,
            input_summary="skill_registry.json not available",
            output_summary="Skipped — no skill registry data",
        )

    skills = registry.get("skills", {})
    if not skills:
        return LoopResult(
            fired=False,
            input_summary="0 skills in registry",
            output_summary="No skills to track",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_skill_health_signals(registry, now_iso)

    # Build signal delta — this updates skills_metrics.json
    signal_delta: dict[str, Any] = {
        "skills": {
            "mastery_count": signals["mastery_count"],
            "growth_count": signals["growth_count"],
            "utilization_pct": signals["utilization_pct"],
            "active_learning": signals["active_learning"],
        },
    }

    # Stagnation warnings
    if signals["stagnant_skills"]:
        signal_delta["stagnation_warning"] = (
            f"{len(signals['stagnant_skills'])} skills stagnant: "
            f"{', '.join(signals['stagnant_skills'][:5])}"
        )

    # Recommendations
    if signals["recommendations"]:
        top_rec = signals["recommendations"][0]
        signal_delta["top_recommendation"] = (
            f"Develop {top_rec['skill_id']} ({top_rec['reason']})"
        )

    # Build summaries
    mastered_skills = [
        sid for sid, s in skills.items()
        if s.get("proficiency") == "mastered"
    ]

    input_summary = (
        f"{len(skills)} skills tracked, "
        f"{signals['mastery_count']} mastered, "
        f"{signals['growth_count']} growing"
    )

    output_parts = [
        f"Mastery: {signals['mastery_count']}",
        f"Util: {signals['utilization_pct']}%",
    ]
    if mastered_skills:
        output_parts.append(f"Mastered: {', '.join(mastered_skills[:4])}")
    if signals["active_learning"]:
        output_parts.append("Active learning: ON")

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
    )
