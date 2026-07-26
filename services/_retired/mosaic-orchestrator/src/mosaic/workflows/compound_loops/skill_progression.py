"""Pure-function skill progression calculator.

All functions are pure: data in, result out. Zero I/O.
Used by loop_skill_health.py, loop_compound_score.py, and API endpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any


# Proficiency thresholds (usage_count → level)
PROFICIENCY_THRESHOLDS: list[tuple[int, str]] = [
    (15, "mastered"),
    (7, "proficient"),
    (3, "developing"),
    (0, "novice"),
]

# Core skills from atlas_config.py KERNEL.user_skills
CORE_SKILLS: frozenset[str] = frozenset({
    "python", "ai_ml", "automation", "prompt_engineering",
    "data", "sales", "writing", "pattern_recognition",
})


def compute_proficiency(usage_count: int) -> str:
    """Map usage count to proficiency level."""
    for threshold, level in PROFICIENCY_THRESHOLDS:
        if usage_count >= threshold:
            return level
    return "novice"


def compute_mastery_count(registry: dict[str, Any]) -> int:
    """Count skills at 'mastered' proficiency."""
    skills = registry.get("skills", {})
    return sum(1 for s in skills.values() if s.get("proficiency") == "mastered")


def compute_growth_count(registry: dict[str, Any]) -> int:
    """Count skills at 'developing' or 'proficient' — actively growing."""
    skills = registry.get("skills", {})
    return sum(
        1 for s in skills.values()
        if s.get("proficiency") in ("developing", "proficient")
    )


def compute_utilization(registry: dict[str, Any]) -> float:
    """Percentage of total usage on core skills (0-100)."""
    skills = registry.get("skills", {})
    if not skills:
        return 0.0

    core_usage = sum(
        s.get("usage_count", 0) for sid, s in skills.items()
        if s.get("category") == "core"
    )
    total_usage = sum(s.get("usage_count", 0) for s in skills.values())

    if total_usage == 0:
        return 0.0
    return (core_usage / total_usage) * 100.0


def compute_active_learning(registry: dict[str, Any]) -> bool:
    """True if any gap skill has been used 3+ times (learning beyond comfort zone)."""
    skills = registry.get("skills", {})
    return any(
        s.get("usage_count", 0) >= 3
        for s in skills.values()
        if s.get("category") == "gap"
    )


def find_stagnant_skills(registry: dict[str, Any], now_iso: str, days: int = 7) -> list[str]:
    """Find skills not used in the last N days that were previously active."""
    skills = registry.get("skills", {})
    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        return []

    cutoff = now - timedelta(days=days)
    stagnant: list[str] = []
    for sid, s in skills.items():
        last_used = s.get("last_used_at")
        if not last_used or s.get("usage_count", 0) < 3:
            continue
        try:
            last = datetime.fromisoformat(last_used)
            if last < cutoff:
                stagnant.append(sid)
        except (ValueError, TypeError):
            continue
    return stagnant


def recommend_next_skills(
    registry: dict[str, Any],
    lane_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Recommend skills to develop next based on gap analysis and lane alignment.

    Priority: gap skills needed by active lanes > gap skills > emerging skills.
    """
    skills = registry.get("skills", {})
    lane_tags = lane_tags or []
    lane_set = set(lane_tags)

    recs: list[dict[str, Any]] = []
    for sid, s in skills.items():
        if s.get("proficiency") in ("proficient", "mastered"):
            continue  # Already strong

        score = 0.0
        reason = ""

        if s.get("category") == "gap":
            score += 30.0
            reason = "gap skill"
        elif s.get("category") == "emerging":
            score += 10.0
            reason = "emerging skill"
        else:
            continue  # Core skills don't need recommendation

        if sid in lane_set:
            score += 50.0
            reason = f"needed by active lane + {reason}"

        # Prefer skills with some usage (momentum)
        usage = s.get("usage_count", 0)
        if usage > 0:
            score += min(10.0, usage * 2.0)

        recs.append({
            "skill_id": sid,
            "category": s.get("category"),
            "current_proficiency": s.get("proficiency"),
            "usage_count": usage,
            "priority_score": round(score, 1),
            "reason": reason,
        })

    return sorted(recs, key=lambda r: -r["priority_score"])[:5]


def apply_skill_usage(
    registry: dict[str, Any],
    skill_tags: dict[str, int],
    source_id: str,
    now_iso: str,
) -> dict[str, Any]:
    """Return updated registry with incremented usage counts and recalculated proficiency.

    Does NOT mutate the input — returns a new dict.
    """
    import copy
    updated = copy.deepcopy(registry)
    skills = updated.setdefault("skills", {})

    for tag, count in skill_tags.items():
        if tag not in skills:
            # Auto-discover new skill as "emerging"
            skills[tag] = {
                "skill_id": tag,
                "category": "core" if tag in CORE_SKILLS else "emerging",
                "usage_count": 0,
                "proficiency": "novice",
                "last_used_at": None,
                "sources": [],
            }

        entry = skills[tag]
        entry["usage_count"] = entry.get("usage_count", 0) + count
        entry["last_used_at"] = now_iso
        entry["proficiency"] = compute_proficiency(entry["usage_count"])

        sources = entry.get("sources", [])
        if source_id not in sources:
            sources.append(source_id)
            entry["sources"] = sources[-20:]  # Keep last 20

    updated["generated_at"] = now_iso
    return updated


def compute_skill_health_signals(registry: dict[str, Any], now_iso: str) -> dict[str, Any]:
    """Aggregate skill health signals from the registry.

    Returns dict usable by loop_compound_score and loop_skill_health.
    """
    skills = registry.get("skills", {})
    if not skills:
        return {
            "mastery_count": 0,
            "growth_count": 0,
            "utilization_pct": 0.0,
            "active_learning": False,
            "total_skills": 0,
            "stagnant_skills": [],
            "recommendations": [],
        }

    # Collect lane tags from project goals if available (not pure, but needed for recs)
    lane_tags: list[str] = []
    for s in skills.values():
        if s.get("category") in ("gap", "emerging") and s.get("usage_count", 0) > 0:
            lane_tags.append(s["skill_id"])

    return {
        "mastery_count": compute_mastery_count(registry),
        "growth_count": compute_growth_count(registry),
        "utilization_pct": round(compute_utilization(registry), 1),
        "active_learning": compute_active_learning(registry),
        "total_skills": len(skills),
        "stagnant_skills": find_stagnant_skills(registry, now_iso),
        "recommendations": recommend_next_skills(registry),
    }
