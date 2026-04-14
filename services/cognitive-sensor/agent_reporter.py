"""
Agent 5: Reporter
Takes idea_registry.json and generates IDEA_REGISTRY.md — a human-readable
formatted report with tables, hierarchy trees, evolution timelines,
dependency graphs, skills analysis, and recommendations.

Input:  idea_registry.json
Output: IDEA_REGISTRY.md
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE = Path(__file__).parent.resolve()


def load_registry():
    """Load the idea registry."""
    path = BASE / "idea_registry.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_header(registry):
    """Generate report header."""
    meta = registry["metadata"]
    tiers = meta.get("tier_breakdown", {})

    lines = [
        "# Idea Registry",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total Ideas:** {meta['total_ideas']}",
        f"**Max Priority:** {meta.get('max_priority', 0):.2f}",
        f"**Avg Priority:** {meta.get('avg_priority', 0):.2f}",
        "",
        "| Tier | Count |",
        "|------|-------|",
    ]

    for tier_name in ["execute_now", "next_up", "backlog", "archive"]:
        count = tiers.get(tier_name, 0)
        display = tier_name.replace("_", " ").title()
        lines.append(f"| {display} | {count} |")

    lines.append("")
    return "\n".join(lines)


def generate_executive_summary(registry):
    """Generate executive summary with top priority ideas."""
    lines = [
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Top 5 by priority
    full = registry.get("full_registry", [])
    top5 = sorted(full, key=lambda x: x.get("priority_score", 0), reverse=True)[:5]

    if top5:
        lines.append("### Top 5 Priority Ideas")
        lines.append("")
        lines.append("| Rank | Idea | Priority | Category | Status | Alignment |")
        lines.append("|------|------|----------|----------|--------|-----------|")

        for i, idea in enumerate(top5, 1):
            title = idea.get("canonical_title", "Untitled")[:45]
            priority = idea.get("priority_score", 0)
            cat = idea.get("category", "?").replace("_", " ")
            status = idea.get("status", "?")
            align = idea.get("alignment_score", 0)
            lines.append(f"| {i} | {title} | {priority:.2f} | {cat} | {status} | {align:.2f} |")

        lines.append("")

    # Priority breakdown for #1
    if top5:
        top = top5[0]
        pb = top.get("priority_breakdown", {})
        lines.append(f"**#1 Priority Breakdown:** ")
        parts = []
        for k, v in pb.items():
            parts.append(f"{k}={v:.3f}")
        lines.append(", ".join(parts))
        lines.append("")

    # Gateways
    gateways = registry.get("gateway_ideas", [])
    if gateways:
        lines.append("### Gateway Ideas (Unlock Others)")
        lines.append("")
        lines.append("| Idea | Unlocks |")
        lines.append("|------|---------|")
        for gw in gateways[:5]:
            title = gw.get("canonical_title", "Untitled")[:50]
            count = gw.get("unlocks_count", 0)
            lines.append(f"| {title} | {count} ideas |")
        lines.append("")

    return "\n".join(lines)


def generate_tier_section(registry, tier_name, display_name):
    """Generate a section for a specific tier."""
    tiers = registry.get("tiers", {})
    items = tiers.get(tier_name, [])

    if not items:
        return f"\n## {display_name}\n\nNo ideas in this tier.\n"

    lines = [
        "---",
        "",
        f"## {display_name} ({len(items)} ideas)",
        "",
        "| # | Idea | Priority | Category | Status | Complexity | Mentions |",
        "|---|------|----------|----------|--------|------------|----------|",
    ]

    for i, item in enumerate(items, 1):
        title = item.get("canonical_title", "Untitled")[:40]
        priority = item.get("priority_score", 0)
        cat = item.get("category", "?").replace("_", " ")
        status = item.get("status", "?")
        complexity = item.get("complexity", "?")
        mentions = item.get("mention_count", 1)
        lines.append(f"| {i} | {title} | {priority:.2f} | {cat} | {status} | {complexity} | {mentions} |")

    lines.append("")

    # Show dependencies for execute_now tier
    if tier_name == "execute_now":
        items_with_deps = [item for item in items if item.get("dependencies")]
        if items_with_deps:
            lines.append("**Dependencies:**")
            for item in items_with_deps:
                title = item["canonical_title"][:40]
                deps = ", ".join(item["dependencies"])
                lines.append(f"- {title} depends on: {deps}")
            lines.append("")

    return "\n".join(lines)


def generate_vision_clusters(registry):
    """Generate vision cluster visualization."""
    clusters = registry.get("vision_clusters", [])
    if not clusters:
        return ""

    full = registry.get("full_registry", [])
    ideas_by_id = {idea["canonical_id"]: idea for idea in full}

    lines = [
        "---",
        "",
        "## Vision Clusters",
        "",
    ]

    # Sort by size
    sorted_clusters = sorted(clusters, key=lambda x: x.get("size", 0), reverse=True)

    for vc in sorted_clusters[:15]:
        name = vc.get("name", "Unnamed")
        size = vc.get("size", 0)
        idea_ids = vc.get("idea_ids", [])

        lines.append(f"### {name} ({size} ideas)")
        lines.append("")

        # Build mini tree
        for cid in idea_ids[:10]:
            idea = ideas_by_id.get(cid, {})
            title = idea.get("canonical_title", cid)[:50]
            status = idea.get("status", "?")
            priority = idea.get("priority_score", 0)
            tier = idea.get("tier", "?")

            status_icon = {
                "idea": "[ ]",
                "started": "[~]",
                "stalled": "[!]",
                "completed": "[x]",
                "abandoned": "[-]",
            }.get(status, "[ ]")

            lines.append(f"- {status_icon} {title} (p={priority:.2f}, {tier})")

        if len(idea_ids) > 10:
            lines.append(f"- ... and {len(idea_ids) - 10} more")

        lines.append("")

    return "\n".join(lines)


def generate_evolution_timelines(registry):
    """Generate evolution timelines for top ideas."""
    full = registry.get("full_registry", [])

    # Find ideas with most mentions (evolved over time)
    multi_mention = [idea for idea in full if idea.get("mention_count", 1) > 1]
    multi_mention.sort(key=lambda x: x.get("mention_count", 1), reverse=True)

    if not multi_mention:
        return ""

    lines = [
        "---",
        "",
        "## Evolution Timelines",
        "",
        "Ideas that recurred across multiple conversations, showing how they evolved.",
        "",
    ]

    for idea in multi_mention[:10]:
        title = idea.get("canonical_title", "Untitled")
        mentions = idea.get("mention_count", 1)
        timeline = idea.get("version_timeline", [])

        lines.append(f"### {title} ({mentions} mentions)")
        lines.append("")
        lines.append("```")

        for entry in timeline:
            date = entry.get("date", "unknown")
            convo_title = entry.get("convo_title", "")[:50]
            note = entry.get("evolution_note", "")
            quote = entry.get("key_quote", "")

            lines.append(f"{date}  {note}")
            lines.append(f"         \"{convo_title}\"")
            if quote:
                lines.append(f"         > {quote[:80]}")
            lines.append("")

        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def generate_category_breakdown(registry):
    """Generate category statistics."""
    full = registry.get("full_registry", [])
    if not full:
        return ""

    cats = Counter(idea.get("category", "uncategorized") for idea in full)

    lines = [
        "---",
        "",
        "## Category Breakdown",
        "",
        "| Category | Count | Avg Priority | Top Tier Count |",
        "|----------|-------|-------------|----------------|",
    ]

    for cat, count in cats.most_common():
        cat_ideas = [idea for idea in full if idea.get("category") == cat]
        avg_p = sum(idea.get("priority_score", 0) for idea in cat_ideas) / max(len(cat_ideas), 1)
        top_tier = sum(1 for idea in cat_ideas if idea.get("tier") in ("execute_now", "next_up"))
        display = cat.replace("_", " ").title()
        lines.append(f"| {display} | {count} | {avg_p:.2f} | {top_tier} |")

    lines.append("")
    return "\n".join(lines)


def generate_skills_analysis(registry):
    """Generate skills gap analysis."""
    full = registry.get("full_registry", [])
    if not full:
        return ""

    # Count skill requirements
    skill_counts = Counter()
    for idea in full:
        for skill in idea.get("skills_required", []):
            skill_counts[skill] += 1

    if not skill_counts:
        return ""

    # User's current skills
    user_skills = {
        "python", "ai_ml", "automation", "prompt_engineering",
        "data", "sales", "writing", "pattern_recognition",
    }

    lines = [
        "---",
        "",
        "## Skills Analysis",
        "",
        "| Skill | Required By | Status |",
        "|-------|-------------|--------|",
    ]

    for skill, count in skill_counts.most_common():
        display = skill.replace("_", " ").title()
        status = "Have" if skill in user_skills else "GAP"
        lines.append(f"| {display} | {count} ideas | {status} |")

    lines.append("")

    # Gaps summary
    gaps = [s for s in skill_counts if s not in user_skills]
    if gaps:
        lines.append("**Skills gaps to address:**")
        for gap in gaps:
            display = gap.replace("_", " ").title()
            lines.append(f"- {display} (needed by {skill_counts[gap]} ideas)")
        lines.append("")

    return "\n".join(lines)


def generate_recommendations(registry):
    """Generate actionable recommendations."""
    full = registry.get("full_registry", [])
    tiers = registry.get("tiers", {})
    gateways = registry.get("gateway_ideas", [])

    lines = [
        "---",
        "",
        "## Recommendations",
        "",
    ]

    # 1. What to do first
    execute_now = tiers.get("execute_now", [])
    if execute_now:
        top = execute_now[0]
        lines.append(f"**1. Start with:** {top['canonical_title']}")
        lines.append(f"   - Priority: {top['priority_score']:.2f}")
        lines.append(f"   - Category: {top['category'].replace('_', ' ')}")
        lines.append(f"   - Complexity: {top['complexity']}")
        if top.get("child_ideas"):
            lines.append(f"   - Enables {len(top['child_ideas'])} downstream ideas")
        lines.append("")

    # 2. Gateway advice
    if gateways:
        gw = gateways[0]
        lines.append(f"**2. Gateway idea:** {gw['canonical_title']}")
        lines.append(f"   - Unlocks {gw['unlocks_count']} other ideas")
        lines.append(f"   - Completing this creates maximum downstream momentum")
        lines.append("")

    # 3. What to archive
    archive = tiers.get("archive", [])
    if archive:
        lines.append(f"**3. Archive {len(archive)} ideas** that are abandoned or low priority")
        lines.append("   - These are not worth cognitive space right now")
        lines.append("   - They're preserved in the registry if you need them later")
        lines.append("")

    # 4. Category focus
    cat_counts = Counter(idea.get("category", "") for idea in full if idea.get("tier") in ("execute_now", "next_up"))
    if cat_counts:
        top_cat = cat_counts.most_common(1)[0]
        lines.append(f"**4. Your strongest category:** {top_cat[0].replace('_', ' ').title()} ({top_cat[1]} actionable ideas)")
        lines.append("   - This is where your skills and interests converge")
        lines.append("")

    # 5. Stalled ideas
    stalled = [idea for idea in full if idea.get("status") == "stalled"]
    if stalled:
        lines.append(f"**5. {len(stalled)} stalled ideas** need a decision: finish or archive")
        for s in stalled[:5]:
            lines.append(f"   - {s.get('canonical_title', 'Untitled')[:50]}")
        lines.append("")

    return "\n".join(lines)


def generate_execution_sequence(registry):
    """Generate the recommended execution order."""
    exec_seq = registry.get("execution_sequence", [])
    full = registry.get("full_registry", [])
    ideas_by_id = {idea["canonical_id"]: idea for idea in full}

    if not exec_seq:
        return ""

    lines = [
        "---",
        "",
        "## Execution Sequence",
        "",
        "Dependency-aware order. Complete earlier items before later ones.",
        "",
        "| Order | Idea | Tier | Priority |",
        "|-------|------|------|----------|",
    ]

    # Only show non-archive ideas
    shown = 0
    for cid in exec_seq:
        idea = ideas_by_id.get(cid, {})
        tier = idea.get("tier", "archive")
        if tier == "archive":
            continue
        shown += 1
        if shown > 30:
            lines.append(f"| ... | *{len(exec_seq) - 30} more ideas* | | |")
            break
        title = idea.get("canonical_title", cid)[:45]
        priority = idea.get("priority_score", 0)
        lines.append(f"| {shown} | {title} | {tier} | {priority:.2f} |")

    lines.append("")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("AGENT 5: REPORTER")
    print("Generating IDEA_REGISTRY.md")
    print("=" * 60)

    registry = load_registry()
    print(f"\nLoaded registry with {registry['metadata']['total_ideas']} ideas")

    # Build report sections
    sections = [
        generate_header(registry),
        generate_executive_summary(registry),
        generate_tier_section(registry, "execute_now", "Execute Now"),
        generate_tier_section(registry, "next_up", "Next Up"),
        generate_vision_clusters(registry),
        generate_evolution_timelines(registry),
        generate_execution_sequence(registry),
        generate_category_breakdown(registry),
        generate_skills_analysis(registry),
        generate_recommendations(registry),
        generate_tier_section(registry, "backlog", "Backlog"),
        generate_tier_section(registry, "archive", "Archive"),
    ]

    # Footer
    sections.append("\n---\n")
    sections.append(f"*Generated by agent_reporter.py | {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    sections.append(f"*Data: {registry['metadata']['total_ideas']} ideas from conversation analysis*")

    # Combine
    report = "\n".join(s for s in sections if s)

    # Write
    out_path = BASE / "IDEA_REGISTRY.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{'=' * 60}")
    print(f"REPORT COMPLETE")
    print(f"{'=' * 60}")
    print(f"Output: {out_path.name}")
    print(f"Length: {len(report):,} characters, {len(report.splitlines())} lines")
    print(f"\nWrote {out_path.name}")


if __name__ == "__main__":
    main()
