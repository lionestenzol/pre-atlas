"""
Agent 4: Orchestrator
Takes ideas_classified.json and builds the master registry with priority
scoring, execution order, actionable tiers, and gateway identification.

Priority = frequency(20%) + recency(20%) + alignment(25%) + feasibility(15%) + compounding(20%)

Input:  ideas_classified.json
Output: idea_registry.json
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# --- Configuration ---
TIER_THRESHOLDS = {
    "execute_now": 0.45,
    "next_up": 0.30,
    "backlog": 0.12,
    # Below backlog = archive
}

# Skills the user currently has (from profile analysis)
USER_SKILLS = {
    "python", "ai_ml", "automation", "prompt_engineering",
    "data", "sales", "writing", "pattern_recognition",
}

# Reference date for recency calculation
TODAY = datetime.now().strftime("%Y-%m-%d")


def load_classified():
    """Load classified ideas."""
    path = BASE / "ideas_classified.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_frequency_score(idea, max_mentions):
    """Score based on how many times this idea recurs (0-1)."""
    mentions = idea.get("mention_count", 1)
    if max_mentions <= 1:
        return 0.0
    return min(mentions / max_mentions, 1.0)


def compute_recency_score(idea):
    """Score based on how recently the idea was discussed (0-1).
    6-month decay: ideas not mentioned in 180 days score 0.
    """
    last_date_str = idea.get("combined_signals", {}).get("last_date", "unknown")
    if last_date_str == "unknown":
        return 0.0

    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        today = datetime.now()
        days_ago = (today - last_date).days
        if days_ago < 0:
            days_ago = 0
        return max(0, 1.0 - (days_ago / 180))
    except ValueError:
        return 0.0


def compute_feasibility_score(idea):
    """Score based on status, skills available, and dependencies met (0-1)."""
    score = 0.0

    # Status component (0-0.4)
    status = idea.get("status", "idea")
    status_scores = {
        "completed": 0.1,   # Already done, low priority
        "started": 0.4,     # Momentum exists
        "stalled": 0.25,    # Was started, needs push
        "idea": 0.3,        # Fresh start possible
        "abandoned": 0.05,  # Very low feasibility
    }
    score += status_scores.get(status, 0.2)

    # Skills component (0-0.3)
    required = set(idea.get("skills_required", []))
    if not required:
        score += 0.2  # No specific skills = generally feasible
    else:
        available = required & USER_SKILLS
        ratio = len(available) / len(required)
        score += ratio * 0.3

    # Dependencies component (0-0.3)
    deps = idea.get("dependencies", [])
    if not deps:
        score += 0.3  # No dependencies = immediately actionable
    else:
        score += 0.1  # Has dependencies = reduced feasibility

    return min(score, 1.0)


def compute_compounding_score(idea, ideas_by_id):
    """Score based on how many other ideas this one enables (0-1)."""
    children = idea.get("child_ideas", [])
    # Also count ideas that depend on this one
    dependents = 0
    for other in ideas_by_id.values():
        if idea["canonical_id"] in other.get("dependencies", []):
            dependents += 1

    total_enabled = len(children) + dependents
    return min(total_enabled / 5.0, 1.0)


def compute_priority_score(idea, max_mentions, ideas_by_id):
    """Compute weighted priority score (0-1)."""
    freq = compute_frequency_score(idea, max_mentions)
    recency = compute_recency_score(idea)
    alignment = idea.get("alignment_score", 0.0)
    feasibility = compute_feasibility_score(idea)
    compounding = compute_compounding_score(idea, ideas_by_id)

    # Weighted combination
    priority = (
        freq * 0.20 +
        recency * 0.20 +
        alignment * 0.25 +
        feasibility * 0.15 +
        compounding * 0.20
    )

    breakdown = {
        "frequency": round(freq * 0.20, 3),
        "recency": round(recency * 0.20, 3),
        "alignment": round(alignment * 0.25, 3),
        "feasibility": round(feasibility * 0.15, 3),
        "compounding": round(compounding * 0.20, 3),
    }

    return round(priority, 3), breakdown


def assign_tier(idea, priority):
    """Assign idea to a tier based on priority score and status."""
    status = idea.get("status", "idea")

    # Abandoned ideas go to archive regardless of priority
    if status == "abandoned":
        return "archive"

    # Completed ideas go to archive
    if status == "completed":
        return "archive"

    if priority >= TIER_THRESHOLDS["execute_now"]:
        return "execute_now"
    elif priority >= TIER_THRESHOLDS["next_up"]:
        return "next_up"
    elif priority >= TIER_THRESHOLDS["backlog"]:
        return "backlog"
    else:
        return "archive"


def topological_sort(ideas, ideas_by_id):
    """Sort ideas by dependencies (dependencies first), break ties by priority."""
    # Build adjacency list
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    all_ids = set()

    for idea in ideas:
        cid = idea["canonical_id"]
        all_ids.add(cid)
        for dep in idea.get("dependencies", []):
            if dep in ideas_by_id:
                graph[dep].append(cid)
                in_degree[cid] += 1

    # Kahn's algorithm with priority tie-breaking
    queue = []
    for cid in all_ids:
        if in_degree[cid] == 0:
            priority = ideas_by_id[cid].get("priority_score", 0)
            queue.append((-priority, cid))  # Negative for max-priority-first

    queue.sort()
    result = []

    while queue:
        _, cid = queue.pop(0)
        result.append(cid)

        for neighbor in graph[cid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                priority = ideas_by_id[neighbor].get("priority_score", 0)
                queue.append((-priority, neighbor))
                queue.sort()

    # Add any remaining (circular dependencies)
    remaining = all_ids - set(result)
    for cid in remaining:
        result.append(cid)

    return result


def find_gateway_ideas(ideas, ideas_by_id):
    """Find ideas that unlock the most downstream projects."""
    gateways = []

    for idea in ideas:
        cid = idea["canonical_id"]
        children = idea.get("child_ideas", [])

        # Count dependents
        dependents = []
        for other in ideas:
            if cid in other.get("dependencies", []):
                dependents.append(other["canonical_id"])

        unlocks = set(children) | set(dependents)

        if len(unlocks) >= 2:
            gateways.append({
                "canonical_id": cid,
                "canonical_title": idea["canonical_title"],
                "unlocks_count": len(unlocks),
                "unlocked_ideas": list(unlocks),
            })

    gateways.sort(key=lambda x: x["unlocks_count"], reverse=True)
    return gateways


def estimate_complexity(idea):
    """Estimate complexity based on skills, text length, and category."""
    skills = idea.get("skills_required", [])
    category = idea.get("category", "")
    children = len(idea.get("child_ideas", []))
    mentions = idea.get("mention_count", 1)

    score = 0
    score += min(len(skills), 4)  # Cap skill contribution
    score += children  # More children = more complex
    if category in ("big_vision",):
        score += 4
    elif category in ("saas_product",):
        score += 3
    elif category in ("framework_system",):
        score += 2
    elif category in ("ai_automation", "consulting_service"):
        score += 1

    if score > 8:
        return "massive"
    elif score > 5:
        return "complex"
    elif score > 3:
        return "moderate"
    elif score > 1:
        return "simple"
    else:
        return "trivial"


def main():
    print("=" * 60)
    print("AGENT 4: ORCHESTRATOR")
    print("Priority scoring, tiers, and execution order")
    print("=" * 60)

    # Load data
    data = load_classified()
    ideas = data["ideas"]
    vision_clusters = data.get("vision_clusters", [])
    print(f"\nLoaded {len(ideas)} classified ideas")

    if len(ideas) == 0:
        print("No ideas to orchestrate.")
        output = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_ideas": 0,
                "tier_breakdown": {},
            },
            "tiers": {"execute_now": [], "next_up": [], "backlog": [], "archive": []},
            "execution_sequence": [],
            "gateway_ideas": [],
            "vision_clusters": [],
            "full_registry": [],
        }
        out_path = BASE / "idea_registry.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Wrote {out_path.name}")
        return

    # Build lookup
    ideas_by_id = {idea["canonical_id"]: idea for idea in ideas}

    # Find max mentions for normalization
    max_mentions = max(idea.get("mention_count", 1) for idea in ideas)

    # Score and tier all ideas
    print("Computing priority scores...")
    for idea in ideas:
        priority, breakdown = compute_priority_score(idea, max_mentions, ideas_by_id)
        idea["priority_score"] = priority
        idea["priority_breakdown"] = breakdown
        idea["tier"] = assign_tier(idea, priority)
        idea["complexity"] = estimate_complexity(idea)

    # Build tiers
    tiers = {"execute_now": [], "next_up": [], "backlog": [], "archive": []}
    for idea in ideas:
        tier = idea["tier"]
        tiers[tier].append(idea["canonical_id"])

    # Sort within each tier by priority
    for tier_name in tiers:
        tier_ids = tiers[tier_name]
        tier_ids.sort(key=lambda cid: ideas_by_id[cid]["priority_score"], reverse=True)

    # Topological sort for execution sequence
    print("Computing execution sequence...")
    exec_sequence = topological_sort(ideas, ideas_by_id)

    # Find gateway ideas
    print("Identifying gateway ideas...")
    gateways = find_gateway_ideas(ideas, ideas_by_id)

    # Build registry entries (without embeddings — too large)
    registry = []
    for idea in ideas:
        entry = {k: v for k, v in idea.items() if k != "embedding"}
        registry.append(entry)

    # Sort registry by priority
    registry.sort(key=lambda x: x["priority_score"], reverse=True)

    # Build tier detail views
    tier_details = {}
    for tier_name, tier_ids in tiers.items():
        tier_details[tier_name] = []
        for cid in tier_ids:
            idea = ideas_by_id[cid]
            tier_details[tier_name].append({
                "canonical_id": cid,
                "canonical_title": idea["canonical_title"],
                "priority_score": idea["priority_score"],
                "priority_breakdown": idea["priority_breakdown"],
                "category": idea["category"],
                "status": idea["status"],
                "complexity": idea["complexity"],
                "mention_count": idea["mention_count"],
                "alignment_score": idea["alignment_score"],
                "dependencies": idea.get("dependencies", []),
                "child_ideas": idea.get("child_ideas", []),
            })

    # Build output
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_ideas": len(ideas),
            "reference_date": TODAY,
            "tier_breakdown": {k: len(v) for k, v in tiers.items()},
            "max_priority": max(idea["priority_score"] for idea in ideas),
            "avg_priority": round(sum(idea["priority_score"] for idea in ideas) / len(ideas), 3),
        },
        "tiers": tier_details,
        "execution_sequence": exec_sequence,
        "gateway_ideas": gateways,
        "vision_clusters": vision_clusters,
        "full_registry": registry,
    }

    # Validate before write
    require_valid(output, "IdeaRegistry.v1.json", "orchestrator")

    # Write
    out_path = BASE / "idea_registry.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"ORCHESTRATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total ideas: {len(ideas)}")
    print()
    print("Tier breakdown:")
    for tier_name, tier_ids in tiers.items():
        print(f"  {tier_name:<15} {len(tier_ids):>4}")
    print()

    # Show Execute Now tier
    if tier_details["execute_now"]:
        print("EXECUTE NOW:")
        for item in tier_details["execute_now"][:8]:
            print(f"  [{item['priority_score']:.2f}] {item['canonical_title'][:55]}")
            print(f"         cat={item['category']}  status={item['status']}  complexity={item['complexity']}")
        print()

    # Show gateways
    if gateways:
        print("Gateway ideas (unlock others):")
        for gw in gateways[:5]:
            print(f"  [{gw['unlocks_count']} unlocked] {gw['canonical_title'][:55]}")
        print()

    print(f"Wrote {out_path.name}")


if __name__ == "__main__":
    main()
