"""
Governor: Daily Pipeline
AI-FOR-ITSELF behaviors (Level 2):
  - Ingest and classify new conversations
  - Update governance state
  - Maintain backlog (merge dupes, kill low-score, enforce 2-lane)
  - Park new ideas outside active lanes

AI-FOR-YOU behavior (Level 1):
  - Generate daily brief with binary decisions

Input:  cognitive_state.json, idea_registry.json, conversation_classifications.json,
        completion_stats.json, daily_payload.json
Output: daily_brief.md, governance_state.json
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from atlas_config import (
    NORTH_STAR, TARGETS, KERNEL, ACTIVE_LANES,
    IDEAS_RESERVOIR_RULES, ROUTING, DAILY_BRIEF_TEMPLATE,
    AutonomyLevel, compute_mode as _compute_mode
)

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


def compute_mode(cognitive_state, completion_stats):
    """Determine operating mode from system state.
    Delegates to atlas_config.compute_mode (single source of truth).
    """
    closure = cognitive_state.get("closure", {})
    ratio = closure.get("ratio", 0)
    open_count = closure.get("open", 0)
    closure_quality = closure.get("closure_quality", 100.0)
    return _compute_mode(ratio, open_count, closure_quality)


def compute_lane_status(idea_registry):
    """Check active lane health."""
    lane_status = []
    for lane in ACTIVE_LANES:
        status = {
            "id": lane["id"],
            "name": lane["name"],
            "status": lane["status"],
            "ship_criteria": lane["ship_criteria"],
            "blocked": False,
            "block_reason": None,
        }

        # Check if lane has moved (look for related ideas in registry)
        tiers = idea_registry.get("tiers", {})
        execute_now = tiers.get("execute_now", [])
        next_up = tiers.get("next_up", [])

        # Simple heuristic: lane is "active" if we find related ideas in top tiers
        lane_name_lower = lane["name"].lower()
        related_count = 0
        for item in execute_now + next_up:
            if any(word in item.get("canonical_title", "").lower() for word in lane_name_lower.split()[:3]):
                related_count += 1

        status["related_ideas_in_pipeline"] = related_count
        lane_status.append(status)

    return lane_status


def detect_lane_violations(idea_registry):
    """Detect if new ideas are trying to create a third lane."""
    violations = []
    lane_names = [l["name"].lower() for l in ACTIVE_LANES]

    tiers = idea_registry.get("tiers", {})
    for item in tiers.get("execute_now", []) + tiers.get("next_up", []):
        title = item.get("canonical_title", "").lower()
        # If an idea doesn't match any active lane keywords, it's a potential violation
        matches_lane = False
        for lane_name in lane_names:
            lane_words = set(lane_name.split())
            title_words = set(title.split())
            if lane_words & title_words:
                matches_lane = True
                break
        if not matches_lane and item.get("status") in ("started", "idea"):
            violations.append({
                "title": item.get("canonical_title", "?"),
                "priority": item.get("priority_score", 0),
                "recommendation": "park",
            })

    return violations[:5]  # Cap at 5


def compute_world_changed(cognitive_state, classifications, idea_registry):
    """Generate 3 bullets about what changed."""
    bullets = []

    # Loop status
    closure = cognitive_state.get("closure", {})
    open_count = closure.get("open", 0)
    ratio = closure.get("ratio", 0)
    closure_quality = closure.get("closure_quality", 100.0)
    truly_closed = closure.get("truly_closed", 0)
    archived = closure.get("archived", 0)
    quality_warning = " **[!] LOW**" if closure_quality < 30 else ""
    bullets.append(f"Open loops: {open_count}, Decision ratio: {ratio:.1f}%, Closure quality: {closure_quality:.1f}%{quality_warning} ({truly_closed} closed, {archived} archived)")

    # Classification stats
    stats = classifications.get("statistics", {})
    domain = stats.get("domain_breakdown", {})
    outcome = stats.get("outcome_breakdown", {})
    if outcome:
        looped = outcome.get("looped", 0)
        produced = outcome.get("produced", 0)
        total = sum(outcome.values())
        bullets.append(f"Conversations: {looped}/{total} looped ({looped/max(total,1)*100:.0f}%), {produced} produced output")

    # Idea registry
    meta = idea_registry.get("metadata", {})
    total_ideas = meta.get("total_ideas", 0)
    tier_breakdown = meta.get("tier_breakdown", {})
    execute_count = tier_breakdown.get("execute_now", 0)
    next_count = tier_breakdown.get("next_up", 0)
    bullets.append(f"Idea registry: {total_ideas} total, {execute_count} execute-now, {next_count} next-up")

    return bullets


def compute_leverage_moves(mode, lane_status, idea_registry, cognitive_state=None):
    """Generate top leverage moves using the directive engine (specific, data-driven)."""
    try:
        from directive_engine import generate_directive, get_loops_with_ages
        from behavioral_memory import get_rolling_context, get_compliance_rate

        loops = (cognitive_state or {}).get("loops", [])
        loops_with_ages = get_loops_with_ages(loops)
        behavioral_context = {
            "rolling": get_rolling_context(14),
            "compliance_rate": get_compliance_rate(30),
        }
        result = generate_directive(cognitive_state or {}, loops_with_ages, behavioral_context)

        moves = [result["confrontation"]]
        if result.get("action") and result["action"] != result["confrontation"]:
            moves.append(result["action"])
        if result.get("compliance_note"):
            moves.append(result["compliance_note"])

        # Pad to 3 if needed with mode-aware fallback
        if mode == "CLOSURE" and len(moves) < 3:
            moves.append("Do not start anything new until one loop is truly closed.")
        elif mode == "MAINTENANCE" and len(moves) < 3:
            moves.append(f"Next shippable piece: {ACTIVE_LANES[0]['name']}")
        elif len(moves) < 3:
            moves.append("End of day: write what you shipped, not what you planned.")

        return moves[:3]

    except Exception as e:
        print(f"  [directive_engine] Failed ({e}), using fallback moves")
        # Fallback to generic moves if directive engine fails
        if mode == "CLOSURE":
            return [
                "Close or archive your oldest open loop before doing anything else",
                "Do not start any new work until closure ratio improves",
                "Review stalled loops — finish or archive each one",
            ]
        elif mode == "MAINTENANCE":
            return [
                f"Focus on Lane 1: {ACTIVE_LANES[0]['name']} — next shippable piece?",
                f"Lane 2: {ACTIVE_LANES[1]['name']} — one outreach action" if len(ACTIVE_LANES) > 1 else "Archive 5 backlog ideas",
                "Archive 5 backlog ideas that will never get done",
            ]
        else:
            return [
                f"Build block: 90 minutes on {ACTIVE_LANES[0]['name']}, phone out of room",
                f"Outreach: 1 action toward {ACTIVE_LANES[1]['name']}" if len(ACTIVE_LANES) > 1 else "Ship something today",
                "End of day: write what you shipped, not what you planned",
            ]


def compute_automation_target(classifications):
    """Identify one thing to remove from manual loop."""
    stats = classifications.get("statistics", {})
    outcome = stats.get("outcome_breakdown", {})
    looped = outcome.get("looped", 0)
    total = sum(outcome.values()) if outcome else 1

    if looped / max(total, 1) > 0.5:
        return "51% of conversations loop without resolution. Today's target: end every AI conversation with a written decision, not more analysis."
    elif outcome.get("abandoned", 0) / max(total, 1) > 0.15:
        return "12%+ of conversations are abandoned mid-way. Today: if you start a conversation, finish it with an action item."
    else:
        return "Review one recurring manual task and draft an automation for it."


def compute_decisions(lane_status, violations):
    """Generate binary decisions for the governor."""
    decisions = []

    # Lane violations
    for v in violations[:2]:
        decisions.append({
            "question": f"Park '{v['title']}' (priority {v['priority']:.2f}) — it's outside active lanes?",
            "options": ["Approve (park it)", "Reject (promote to active lane)"],
            "recommendation": "Approve",
        })

    # Lane health
    for lane in lane_status:
        if lane["status"] == "not_started":
            decisions.append({
                "question": f"Lane '{lane['name']}' hasn't started. Begin today?",
                "options": ["Yes, start", "Not today"],
                "recommendation": "Yes, start",
            })

    return decisions[:DAILY_BRIEF_TEMPLATE["max_decisions"]]


def _load_life_context():
    """Load life signals and phase data for brief enrichment."""
    life_path = BASE / "life_signals.json"
    life = {}
    if life_path.exists():
        try:
            life = json.loads(life_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    osint_path = BASE / "cycleboard" / "brain" / "osint_feed.json"
    osint = {}
    if osint_path.exists():
        try:
            osint = json.loads(osint_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return life, osint


PHASE_NAMES = {
    1: "Stabilization", 2: "Leverage Accumulation",
    3: "Extraction & Autonomy", 4: "Scaling", 5: "Generational Infrastructure",
}


def generate_brief(mode, risk, build_allowed, world_changed, leverage_moves, automation_target, decisions, lane_status, ghost_data=None):
    """Generate the daily brief as markdown."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    life, osint = _load_life_context()
    energy = life.get("energy", {})
    finance = life.get("finance", {})
    life_phase = life.get("life_phase", 1)

    lines = []
    lines.append(f"# Daily Brief — {now}")
    lines.append("")

    # Mode banner
    mode_emoji = {"CLOSURE": "[!]", "MAINTENANCE": "[~]", "BUILD": "[+]"}
    lines.append(f"## Mode: {mode_emoji.get(mode, '[ ]')} {mode}")
    lines.append(f"Risk: {risk} | Build allowed: {'Yes' if build_allowed else 'No'} | Phase {life_phase}: {PHASE_NAMES.get(life_phase, '?')}")
    if not build_allowed:
        lines.append("")
        lines.append("> **The governor has blocked BUILD mode.** You are archiving loops, not closing them. Fix this first.")
    lines.append("")

    # Life signals summary
    el = energy.get("energy_level", 50)
    ml = energy.get("mental_load", 5)
    rw = finance.get("runway_months", 3.0)
    burnout = energy.get("burnout_risk", False)
    red_alert = energy.get("red_alert_active", False)

    signal_flags = []
    if el < 30:
        signal_flags.append(f"ENERGY DEPLETED ({el}/100)")
    if burnout:
        signal_flags.append("BURNOUT RISK")
    if red_alert:
        signal_flags.append("RED ALERT ZONE")
    if rw < 2:
        signal_flags.append(f"FINANCIAL CONSTRAINT (runway {rw:.1f}mo)")

    if signal_flags:
        lines.append("> **Active Constraints:** " + " | ".join(signal_flags))
        lines.append("")

    lines.append(f"**Energy:** {el}/100 | **Load:** {ml}/10 | **Runway:** {rw:.1f}mo")
    lines.append("")

    # North Star reminder
    lines.append("**North Star:** " + NORTH_STAR["weekly"])
    lines.append(f"**Active Lanes:** {len(ACTIVE_LANES)} / {TARGETS['max_active_lanes']} max")
    lines.append("")

    # World Context (from Crucix OSINT if available)
    if osint and osint.get("highlights"):
        lines.append("## World Context")
        for highlight in osint["highlights"][:3]:
            lines.append(f"- {highlight}")
        lines.append("")

    # What changed
    lines.append("## What Changed")
    for bullet in world_changed:
        lines.append(f"- {bullet}")
    lines.append("")

    # Active lanes
    lines.append("## Lane Status")
    for lane in lane_status:
        lines.append(f"- **{lane['name']}** — {lane['status']}")
    lines.append("")

    # Leverage moves
    lines.append("## Top Moves Today")
    for i, move in enumerate(leverage_moves, 1):
        lines.append(f"{i}. {move}")
    lines.append("")

    # Genesis insights
    if ghost_data and (ghost_data.get("directives") or ghost_data.get("convergence_directives")):
        lines.append("## Genesis Insights")
        active_dirs = [d for d in ghost_data.get("directives", []) if not d.get("blocked")]
        if active_dirs:
            top = active_dirs[0]
            lines.append(f"- **Top directive**: {top['type']} -- {top['domain']}: {top['suggested_action']}")
        convergences = ghost_data.get("convergence_directives", [])
        if convergences:
            c = convergences[0]
            lines.append(f"- **Convergence**: {c['domains'][0]} + {c['domains'][1]} -- {c['suggested_action']}")
        lines.append("")

    # Automation target
    lines.append("## Automation Target")
    lines.append(f"- {automation_target}")
    lines.append("")

    # Decisions
    if decisions:
        lines.append("## Decisions Required")
        for i, d in enumerate(decisions, 1):
            lines.append(f"**{i}. {d['question']}**")
            for opt in d["options"]:
                lines.append(f"   - [ ] {opt}")
            lines.append(f"   *Recommendation: {d['recommendation']}*")
            lines.append("")

    # Guardrails
    lines.append("## Guardrails Active")
    lines.append(f"- Idea moratorium: {'ON' if TARGETS['idea_moratorium'] else 'OFF'}")
    lines.append(f"- Max research: {TARGETS['max_research_minutes']} min before building")
    lines.append(f"- Work blocks target: {TARGETS['daily_work_blocks']}x {TARGETS['min_build_minutes']} min")
    lines.append(f"- Phone: OUT of room during work blocks")
    lines.append("")

    # Warning signs
    lines.append("## Early Warning Signs")
    lines.append("- You start a new idea not on the active lanes")
    lines.append("- You spend >30 min researching without building")
    lines.append("- You open ChatGPT to 'process' instead of to build")
    lines.append("- You use 'because' to explain why you didn't do a planned task")
    lines.append("")

    return "\n".join(lines)


def build_governance_state(mode, risk, build_allowed, lane_status, violations):
    """Build persistent governance state for weekly aggregation."""
    life = {}
    life_path = BASE / "life_signals.json"
    if life_path.exists():
        try:
            life = json.loads(life_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "generated_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "mode": mode,
        "risk": risk,
        "build_allowed": build_allowed,
        "life_phase": life.get("life_phase", 1),
        "north_star": NORTH_STAR,
        "active_lanes": [
            {"id": l["id"], "name": l["name"], "status": l["status"]}
            for l in ACTIVE_LANES
        ],
        "lane_status": lane_status,
        "lane_violations": violations,
        "targets": TARGETS,
        "guardrails": {
            "idea_moratorium": TARGETS["idea_moratorium"],
            "max_lanes": TARGETS["max_active_lanes"],
        },
    }


def write_headline(mode, risk, build_allowed, leverage_moves, decisions, cognitive_state):
    """Write a tiny headline JSON for atlas_boot.html to display."""
    closure = cognitive_state.get("closure", {})

    # Load drift alerts if available
    drift_path = BASE / "drift_alerts.json"
    drift_data = {}
    if drift_path.exists():
        try:
            drift_data = json.loads(drift_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Load compliance rate
    compliance_rate = None
    try:
        from behavioral_memory import get_compliance_rate
        rate = get_compliance_rate(30)
        compliance_rate = round(rate * 100) if rate is not None else None
    except Exception:
        pass

    # Load life signals for headline
    life_path = BASE / "life_signals.json"
    life_data = {}
    if life_path.exists():
        try:
            life_data = json.loads(life_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    headline = {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "risk": risk,
        "build_allowed": build_allowed,
        "life_phase": life_data.get("life_phase", 1),
        "energy_level": life_data.get("energy", {}).get("energy_level"),
        "burnout_risk": life_data.get("energy", {}).get("burnout_risk", False),
        "runway_months": life_data.get("finance", {}).get("runway_months"),
        "closure_quality": closure.get("closure_quality", 100.0),
        "open_loops": closure.get("open", 0),
        "top_move": leverage_moves[0] if leverage_moves else "No moves computed",
        "top_decision": decisions[0]["question"] if decisions else None,
        "warning": "Archiving is not closing" if closure.get("closure_quality", 100) < 30 else None,
        # New behavioral fields
        "confrontation": leverage_moves[0] if leverage_moves else None,
        "compliance_rate": compliance_rate,
        "drift_score": drift_data.get("drift_score", 0),
        "drift_alerts": drift_data.get("alerts", []),
    }

    # Inject genesis top directive if available
    ghost_path = BASE / "genesis_output" / "ghost_directives.json"
    if ghost_path.exists():
        try:
            ghost = json.loads(ghost_path.read_text(encoding="utf-8"))
            active_dirs = [d for d in ghost.get("directives", []) if not d.get("blocked")]
            if active_dirs:
                headline["genesis_top"] = active_dirs[0]["suggested_action"]
        except Exception:
            pass

    path = BASE / "governor_headline.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(headline, f, indent=2)
    print(f"Wrote {path.name}")
    return headline


def main():
    print("=" * 60)
    print("GOVERNOR: DAILY PIPELINE")
    print("=" * 60)

    # Refresh OSINT feed before generating brief (graceful if Crucix offline)
    try:
        from crucix_bridge import poll_and_extract
        print("\nRefreshing OSINT feed...")
        osint_result = poll_and_extract()
        print(f"  OSINT: {osint_result['status']} ({len(osint_result.get('highlights', []))} highlights)")
    except Exception as e:
        print(f"  [crucix_bridge] Skipped ({e})")

    # Load current state
    print("\nLoading system state...")
    cognitive_state = read_json("cognitive_state.json")
    idea_registry = read_json("idea_registry.json")
    classifications = read_json("conversation_classifications.json")
    completion_stats = read_json("completion_stats.json")

    # Compute mode
    mode, risk, build_allowed = compute_mode(cognitive_state, completion_stats)
    print(f"Mode: {mode} | Risk: {risk} | Build: {'Yes' if build_allowed else 'No'}")

    # Closure quality check
    closure = cognitive_state.get("closure", {})
    cq = closure.get("closure_quality", 100.0)
    if cq < 30:
        print(f"  [!] CLOSURE QUALITY: {cq}% -- you're archiving, not closing")

    # Lane analysis
    print("Analyzing lane status...")
    lane_status = compute_lane_status(idea_registry)
    violations = detect_lane_violations(idea_registry)
    if violations:
        print(f"  Found {len(violations)} lane violation(s)")

    # World changed
    world_changed = compute_world_changed(cognitive_state, classifications, idea_registry)

    # Leverage moves
    leverage_moves = compute_leverage_moves(mode, lane_status, idea_registry, cognitive_state)

    # Automation target
    automation_target = compute_automation_target(classifications)

    # Decisions
    decisions = compute_decisions(lane_status, violations)

    # Load ghost directives (from Genesis pipeline)
    ghost_data = read_json("genesis_output/ghost_directives.json") or None

    # Generate brief
    print("\nGenerating daily brief...")
    brief = generate_brief(
        mode, risk, build_allowed,
        world_changed, leverage_moves, automation_target,
        decisions, lane_status, ghost_data=ghost_data
    )

    # Write brief
    brief_path = BASE / "daily_brief.md"
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief)
    print(f"Wrote {brief_path.name}")

    # Build and write governance state
    gov_state = build_governance_state(mode, risk, build_allowed, lane_status, violations)
    state_path = BASE / "governance_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(gov_state, f, indent=2)
    print(f"Wrote {state_path.name}")

    # Write headline for atlas_boot.html
    write_headline(mode, risk, build_allowed, leverage_moves, decisions, cognitive_state)

    # Print brief to console
    print(f"\n{'=' * 60}")
    print(brief)


if __name__ == "__main__":
    main()
