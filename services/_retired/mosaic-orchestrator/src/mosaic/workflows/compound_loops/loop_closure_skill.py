"""Loop 1: Closure → Skill Growth.

When loops are closed, detect what skills were exercised and update skill signals.
True closures generate growth; archives do not.
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

# Map conversation domains to skill tags (aligned with atlas_config.KERNEL.user_skills)
DOMAIN_TO_SKILLS: dict[str, list[str]] = {
    "technical": ["python", "ai_ml", "automation", "data"],
    "business": ["sales", "writing", "prompt_engineering"],
    "execution": ["automation", "pattern_recognition"],
    "learning": ["ai_ml", "data", "prompt_engineering"],
    "processing": ["pattern_recognition", "writing"],
    "personal": [],
    "admin": [],
}

ACTIVE_LEARNING_THRESHOLD = 3  # skill appears in 3+ closures → active_learning=True


def compute_closure_to_skill(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute skill growth signals from recent loop closures AND subtask completions.

    Reads:
        snapshot.auto_actor_log — loops_closed[] with convo_id and decision
        snapshot.classifications — domain per convo_id
        snapshot.skills_metrics — current skill state
        snapshot.project_goals — completed subtasks with skill tags

    Returns:
        LoopResult with signal_delta for skills domain.
    """
    actor_log = snapshot.auto_actor_log
    classifications = snapshot.classifications
    skills = snapshot.skills_metrics

    # Guard: need at least skills_metrics
    if "error" in skills:
        return LoopResult(
            fired=False,
            input_summary="Missing data: skills_metrics",
        )

    # Source 1: truly closed loops from auto_actor (original path)
    skill_counts: dict[str, int] = {}
    true_closures: list[dict[str, Any]] = []

    if "error" not in actor_log and "error" not in classifications:
        loops_closed: list[dict[str, Any]] = actor_log.get("loops_closed", [])
        true_closures = [lc for lc in loops_closed if lc.get("decision") == "CLOSE"]

        for closure in true_closures:
            convo_id = closure.get("convo_id", "")
            domain = _extract_domain(classifications, convo_id)
            for skill in DOMAIN_TO_SKILLS.get(domain, []):
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    # Source 2: completed subtasks from project goals (chain igniter)
    subtask_skill_count = 0
    project_goals = snapshot.project_goals
    if "error" not in project_goals:
        for goal in project_goals.get("goals", []):
            for ms in goal.get("milestones", []):
                for st in ms.get("subtasks", []):
                    if st.get("status") == "done" and st.get("tags"):
                        subtask_skill_count += 1
                        for tag in st["tags"]:
                            skill_counts[tag] = skill_counts.get(tag, 0) + 1

    # Need at least one source of skill signal
    if not true_closures and subtask_skill_count == 0:
        loops_total = len(actor_log.get("loops_closed", [])) if "error" not in actor_log else 0
        return LoopResult(
            fired=False,
            input_summary=f"{loops_total} loops in log, 0 true closures, 0 subtask completions",
        )

    growth_delta = len(true_closures) + subtask_skill_count
    active_learning = any(count >= ACTIVE_LEARNING_THRESHOLD for count in skill_counts.values())

    current_growth = skills.get("growth_count", 0)
    current_utilization = skills.get("utilization_pct", 0)

    # Utilization bump: each closure/subtask adds ~2% utilization (capped at 100)
    utilization_bump = min(100, current_utilization + growth_delta * 2)

    signal_delta = {
        "skills": {
            "growth_count": current_growth + growth_delta,
            "active_learning": active_learning,
            "utilization_pct": utilization_bump,
        },
        # Individual skill usage for skill_registry.json updates
        "skill_usage_update": skill_counts,
    }

    skills_exercised = [k for k, v in sorted(skill_counts.items(), key=lambda x: -x[1])]
    sources = []
    if true_closures:
        sources.append(f"{len(true_closures)} closures")
    if subtask_skill_count:
        sources.append(f"{subtask_skill_count} subtasks")

    return LoopResult(
        fired=True,
        input_summary=f"{' + '.join(sources)} → {len(skill_counts)} skills",
        output_summary=f"Skills exercised: {', '.join(skills_exercised[:5])}. Growth +{growth_delta}",
        signal_delta=signal_delta,
        confidence=min(1.0, growth_delta / 3),
    )


def _extract_domain(classifications: dict[str, Any], convo_id: str) -> str:
    """Extract the domain for a conversation from classifications data."""
    # Classifications may be a flat dict {convo_id: {domain, ...}} or nested
    if convo_id in classifications:
        entry = classifications[convo_id]
        if isinstance(entry, dict):
            return entry.get("domain", "personal")
    # Fallback: scan for matching convo_id in list format
    for key, val in classifications.items():
        if isinstance(val, dict) and val.get("convo_id") == convo_id:
            return val.get("domain", "personal")
    return "personal"
