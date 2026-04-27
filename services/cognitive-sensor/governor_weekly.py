"""
Governor: Weekly Pipeline
Aggregates daily state, computes lane progress, generates governor packet.

AI-FOR-YOU (Level 1): Produces the weekly packet with 3-5 binary decisions.
You read it, approve/reject, and move on. No juggling raw data.

Input:  governance_state.json, idea_registry.json, conversation_classifications.json,
        completion_stats.json, BEHAVIORAL_AUDIT.md
Output: weekly_governor_packet.md
"""

import json
from pathlib import Path
from datetime import datetime
from atlas_config import (
    NORTH_STAR, TARGETS, ACTIVE_LANES, KERNEL,
    WEEKLY_PACKET_TEMPLATE, AutonomyLevel
)
from lifecycle_summary import summarize as _lifecycle_summarize

BASE = Path(__file__).parent.resolve()


def read_json(name):
    path = BASE / name
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def read_file(name):
    path = BASE / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def compute_reality_check(classifications, idea_registry, completion_stats):
    """Section 1: Where time/attention actually went."""
    lines = []
    lines.append("### Section 1 — Reality Check\n")
    lines.append("*Where your time and attention actually went this period.*\n")

    # Domain distribution
    stats = classifications.get("statistics", {})
    domain = stats.get("domain_breakdown", {})
    total = sum(domain.values()) if domain else 1

    lines.append("**Conversation domain allocation:**")
    lines.append("| Domain | Count | % | Assessment |")
    lines.append("|--------|-------|---|-----------|")
    for d, count in sorted(domain.items(), key=lambda x: x[1], reverse=True):
        pct = count / max(total, 1) * 100
        assessment = ""
        if d == "execution" and pct < 10:
            assessment = "TOO LOW — need more doing, less thinking"
        elif d == "processing" and pct > 20:
            assessment = "HIGH — emotional processing consuming bandwidth"
        elif d == "technical" and pct > 40:
            assessment = "Consider: exploring or building?"
        lines.append(f"| {d} | {count} | {pct:.1f}% | {assessment} |")
    lines.append("")

    # Outcome distribution
    outcome = stats.get("outcome_breakdown", {})
    total_o = sum(outcome.values()) if outcome else 1
    looped = outcome.get("looped", 0)
    produced = outcome.get("produced", 0)

    lines.append("**Conversation outcomes:**")
    lines.append(f"- Looped (no resolution): **{looped}** ({looped/max(total_o,1)*100:.0f}%)")
    lines.append(f"- Produced output: **{produced}** ({produced/max(total_o,1)*100:.0f}%)")
    lines.append(f"- Productive ratio: **{produced/max(total_o,1)*100:.0f}%**")
    lines.append("")

    # Closure ratio
    closed = completion_stats.get("closed_life", 0)
    archived = completion_stats.get("archived_life", 0)
    ratio = completion_stats.get("closure_ratio", 0)
    lines.append(f"**Closure ratio:** {ratio:.1f}% (closed: {closed}, archived: {archived})")
    lines.append("")

    # Idea registry health
    meta = idea_registry.get("metadata", {})
    tier = meta.get("tier_breakdown", {})
    lines.append(f"**Idea registry:** {meta.get('total_ideas', 0)} total")
    lines.append(f"- Execute now: {tier.get('execute_now', 0)}")
    lines.append(f"- Next up: {tier.get('next_up', 0)}")
    lines.append(f"- Backlog: {tier.get('backlog', 0)}")
    lines.append(f"- Archive: {tier.get('archive', 0)}")
    lines.append("")

    return "\n".join(lines)


def compute_lifecycle_shipped(window_days: int = 7):
    """Weekly artifacts shipped — pulls from closures.json via lifecycle_summary."""
    lines = []
    lines.append("### Section 1b — Thread Lifecycle (last 7 days)\n")
    try:
        lc = _lifecycle_summarize(window_days=window_days)
    except Exception as e:
        lines.append(f"*(lifecycle_summary unavailable: {e})*\n")
        return "\n".join(lines)

    terminal = lc.get("terminal_window", {})
    done = terminal.get("DONE", [])
    resolved = terminal.get("RESOLVED", [])
    dropped = terminal.get("DROPPED", [])
    artifacts = lc.get("artifacts_shipped", [])
    counts = lc.get("counts", {})
    in_progress = lc.get("in_progress", [])

    lines.append(f"**Closed this week:** DONE:{len(done)} · RESOLVED:{len(resolved)} · DROPPED:{len(dropped)}")
    lines.append(f"**In progress:** {len(in_progress)} "
                 f"(PLANNED:{counts.get('PLANNED',0)} BUILDING:{counts.get('BUILDING',0)} REVIEWING:{counts.get('REVIEWING',0)})")
    lines.append("")

    if artifacts:
        covs = [a.get("coverage_score") for a in artifacts if isinstance(a.get("coverage_score"), (int, float))]
        avg_cov = (sum(covs) / len(covs)) if covs else None
        lines.append(f"**Artifacts shipped:** {len(artifacts)}" + (f" (avg coverage {avg_cov:.2f})" if avg_cov is not None else ""))
        lines.append("")
        lines.append("| Loop | Title | Artifact | Coverage |")
        lines.append("|------|-------|----------|----------|")
        for a in artifacts:
            cov = a.get("coverage_score")
            cov_str = f"{cov:.2f}" if isinstance(cov, (int, float)) else "-"
            lines.append(f"| #{a.get('loop_id','?')} | {a.get('title','?')} | `{a.get('artifact_path','?')}` | {cov_str} |")
    else:
        lines.append("**Artifacts shipped:** 0")
    lines.append("")

    return "\n".join(lines)


def compute_lane_progress(gov_state):
    """Section 2: What shipped, what moved, what stalled."""
    lines = []
    lines.append("### Section 2 — Lane Progress\n")

    lanes = gov_state.get("active_lanes", ACTIVE_LANES)

    for lane in lanes:
        name = lane.get("name", "?")
        status = lane.get("status", "unknown")
        lines.append(f"**{name}**")
        lines.append(f"- Status: {status}")

        if status == "not_started":
            lines.append(f"- Assessment: NOT STARTED — this lane needs its first action this week")
            lines.append(f"- Ship criteria: {lane.get('ship_criteria', '?')}")
        elif status == "in_progress":
            lines.append(f"- Assessment: IN PROGRESS — track what shipped this week")
        elif status == "stalled":
            lines.append(f"- Assessment: STALLED — decide: push through or archive")
        lines.append("")

    # North Star check
    lines.append("**North Star alignment:**")
    lines.append(f"- Weekly target: {NORTH_STAR['weekly']}")
    lines.append(f"- Assets shipped this week: ___ (fill in)")
    lines.append(f"- Revenue generated: ___ (fill in)")
    lines.append("")

    return "\n".join(lines)


def compute_autonomy_proposals(classifications, idea_registry):
    """Section 3: Propose agent autonomy changes."""
    lines = []
    lines.append("### Section 3 — Autonomy Proposals\n")

    # Based on system maturity, propose promotions
    stats = classifications.get("statistics", {})
    outcome = stats.get("outcome_breakdown", {})
    total = sum(outcome.values()) if outcome else 1
    produced = outcome.get("produced", 0)

    if produced / max(total, 1) > 0.25:
        lines.append("- **Proposal:** Promote `backlog_maintainer` from Level 1 -> Level 2")
        lines.append("  - Reason: Production rate is healthy enough to trust automated backlog cleanup")
        lines.append("  - Risk: Low — only affects internal JSON files")
        lines.append("")
    else:
        lines.append("- **No autonomy changes recommended this week.**")
        lines.append("  - Reason: Production rate too low to justify trusting more to automation")
        lines.append("")

    lines.append("- **Standing rule:** No agent may push public-facing changes without your approval.")
    lines.append("")

    return "\n".join(lines)


def compute_lane_integrity(gov_state, idea_registry):
    """Section 4: Did governor try to create a third lane?"""
    lines = []
    lines.append("### Section 4 — Lane Integrity\n")

    violations = gov_state.get("lane_violations", [])

    if violations:
        lines.append(f"**{len(violations)} lane violation(s) detected:**\n")
        for v in violations:
            lines.append(f"- '{v['title']}' (priority {v.get('priority', 0):.2f}) — outside active lanes")
            lines.append(f"  Recommendation: {v.get('recommendation', 'park')}")
            lines.append("")
        lines.append("These ideas are trying to become a third lane. They should be parked or explicitly promoted.\n")
    else:
        lines.append("No lane violations detected. You stayed within 2 lanes.\n")

    lines.append(f"**Active lanes:** {len(ACTIVE_LANES)} / {TARGETS['max_active_lanes']}")
    lines.append(f"**Idea moratorium:** {'ON' if TARGETS['idea_moratorium'] else 'OFF'}")
    lines.append("")

    return "\n".join(lines)


def compute_stop_list():
    """Section 5: What to ruthlessly stop."""
    lines = []
    lines.append("### Section 5 — Stop List\n")
    lines.append("Based on behavioral audit data, continue stopping:\n")
    lines.append("| Stop | Why | Replacement |")
    lines.append("|------|-----|-------------|")
    lines.append("| New ideas outside active lanes | 527 ideas, 0 completions | Park automatically via idea_parker |")
    lines.append("| Research binges >30 min | Substitutes for execution | Timer -> build after 30 min |")
    lines.append("| Processing people injuries >15 min | 1,011 mentions of disrespect/betrayal processing | Journal dump, then redirect |")
    lines.append("| Phone during work blocks | #1 derailment at 1,509 mentions | Phone in another room |")
    lines.append("| Saying 'I need to plan more first' | Justification engine (13,233x) | Do the next physical action in 5 min |")
    lines.append("")
    return "\n".join(lines)


def compute_decisions(gov_state, idea_registry):
    """Section 6: Binary decisions for the governor."""
    lines = []
    lines.append("### Section 6 — Decisions Required\n")

    decisions = []

    # Lane decisions
    for lane in ACTIVE_LANES:
        if lane["status"] == "not_started":
            decisions.append(f"Start '{lane['name']}' this week?")
        elif lane["status"] == "stalled":
            decisions.append(f"Continue or archive '{lane['name']}'?")

    # Stalled ideas
    meta = idea_registry.get("metadata", {})
    if meta:
        decisions.append("Archive the 207 ideas currently in archive tier (permanent cleanup)?")

    # Moratorium
    if TARGETS["idea_moratorium"]:
        decisions.append("Keep idea moratorium ON for another week?")

    # Format
    for i, d in enumerate(decisions[:WEEKLY_PACKET_TEMPLATE["max_decisions"]], 1):
        lines.append(f"**{i}. {d}**")
        lines.append(f"   - [ ] Yes / Approve")
        lines.append(f"   - [ ] No / Reject")
        lines.append("")

    if not decisions:
        lines.append("No decisions required this week.\n")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("GOVERNOR: WEEKLY PIPELINE")
    print("=" * 60)

    # Load state
    print("\nLoading system state...")
    gov_state = read_json("governance_state.json")
    idea_registry = read_json("idea_registry.json")
    classifications = read_json("conversation_classifications.json")
    completion_stats = read_json("completion_stats.json")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build packet
    print("Generating weekly governor packet...")

    packet = []
    packet.append(f"# Weekly Governor Packet — {now}\n")
    packet.append(f"**Role:** You are the Governor. Read, decide, move on.")
    packet.append(f"**Time required:** 5-10 minutes")
    packet.append(f"**Decisions:** {WEEKLY_PACKET_TEMPLATE['max_decisions']} max\n")
    packet.append("---\n")

    # Sections
    packet.append(compute_reality_check(classifications, idea_registry, completion_stats))
    packet.append("---\n")
    packet.append(compute_lifecycle_shipped(window_days=7))
    packet.append("---\n")
    packet.append(compute_lane_progress(gov_state))
    packet.append("---\n")
    packet.append(compute_autonomy_proposals(classifications, idea_registry))
    packet.append("---\n")
    packet.append(compute_lane_integrity(gov_state, idea_registry))
    packet.append("---\n")
    packet.append(compute_stop_list())
    packet.append("---\n")
    packet.append(compute_decisions(gov_state, idea_registry))

    # Footer
    packet.append("---\n")
    packet.append(f"*Generated by Atlas Governor — {now}*")
    packet.append(f"*North Star: {NORTH_STAR['weekly']}*")

    full_packet = "\n".join(packet)

    # Write
    out_path = BASE / "weekly_governor_packet.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_packet)
    print(f"Wrote {out_path.name}")

    # Print
    print(f"\n{'=' * 60}")
    print(full_packet.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
