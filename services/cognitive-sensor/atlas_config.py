"""
Atlas Governance Configuration
Layer 0 (North Star) + Layer 1 (Profile/Kernel) + Layer 4 (Autonomy Split)

This is the single source of truth for all governance rules.
Every agent reads from here. Nothing is hardcoded elsewhere.
"""

from enum import IntEnum

# ============================================================
# LAYER 0 — NORTH STAR
# The objective function the entire system optimizes toward.
# ============================================================

NORTH_STAR = {
    "weekly": "Ship 1 asset (doc, tool, GPT, chapter, client deliverable)",
    "monthly": "Generate revenue from AI consulting or products",
    "system": "Increase closure_ratio, decrease active_lanes",
    "guard": "Block new ideas unless current lane is shipped or archived",
}

# Measurable targets
TARGETS = {
    "max_active_lanes": 2,
    "weekly_ship_target": 1,         # assets shipped per week
    "min_closure_ratio": 15.0,       # below this = CLOSURE mode
    "max_open_loops": 20,            # above this = CLOSURE mode
    "idea_moratorium": True,         # no new ideas until current lanes ship
    "max_research_minutes": 30,      # before must build
    "min_build_minutes": 90,         # per focused block
    "daily_work_blocks": 3,          # target blocks per day
}


# ============================================================
# LAYER 1 — PROFILE (Behavioral Kernel)
# System characteristics, not personality.
# ============================================================

KERNEL = {
    "strengths": [
        "pattern_recognition",
        "system_architecture",
        "ai_fluency",
        "fast_synthesis",
        "sublimation_engine",       # converts pain → creation
        "relentless_return",        # never permanently quits
    ],
    "weaknesses": [
        "novelty_drift",            # new idea > finishing old one
        "justification_loops",      # 13,233 "because" statements
        "over_research",            # research binges as avoidance
        "phone_escape",             # #1 derailment factor
        "non_shipping",             # 0.0 closure ratio
        "all_or_nothing",           # 7,248 absolute statements
    ],
    "preferences": {
        "interface": "command_briefs",    # not dashboards
        "decisions": "binary",            # approve/reject, not open-ended
        "leverage": "high_only",          # don't present low-impact options
    },
    "constraints": {
        "max_lanes": 2,
        "scope": "smallest_shippable",
        "no_analysis_loops": True,        # process → decide, don't loop
    },
    "user_skills": {
        "python", "ai_ml", "automation", "prompt_engineering",
        "data", "sales", "writing", "pattern_recognition",
    },
    "skills_gaps": {
        "design", "marketing", "javascript", "finance", "devops",
    },
}


# ============================================================
# LAYER 4 — AUTONOMY LEVELS
# Standardized scale all agents must use.
# ============================================================

class AutonomyLevel(IntEnum):
    ADVISORY = 0       # Analyze/suggest only. No state change.
    DRAFT_ROUTE = 1    # Create artifacts, queue actions. Requires approval.
    EXECUTE_REPORT = 2 # Execute within scope, log, escalate on edge cases.
    SILENT = 3         # Reserved for future safe idempotent ops.


# ============================================================
# AGENT REGISTRY
# Every agent's autonomy level and contract.
# ============================================================

AGENTS = {
    # === Existing agents (idea pipeline) ===
    "agent_excavator": {
        "purpose": "Extract ideas from all conversations",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["memory_db.json", "results.db"],
        "outputs": ["excavated_ideas_raw.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "agent_deduplicator": {
        "purpose": "Merge duplicate ideas via cosine similarity",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["excavated_ideas_raw.json"],
        "outputs": ["ideas_deduplicated.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "agent_classifier": {
        "purpose": "Build hierarchy, dependencies, alignment scores",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["ideas_deduplicated.json", "DEEP_PSYCHOLOGICAL_PROFILE.md"],
        "outputs": ["ideas_classified.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "agent_orchestrator": {
        "purpose": "Priority scoring, tiers, execution order",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["ideas_classified.json"],
        "outputs": ["idea_registry.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "agent_reporter": {
        "purpose": "Generate IDEA_REGISTRY.md",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["idea_registry.json"],
        "outputs": ["IDEA_REGISTRY.md"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },

    # === Audit agents ===
    "agent_classifier_convo": {
        "purpose": "Classify conversations by domain, outcome, trajectory",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["memory_db.json", "results.db"],
        "outputs": ["conversation_classifications.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "agent_synthesizer": {
        "purpose": "Generate 30-question behavioral audit",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["*.md analysis files", "conversation_classifications.json", "idea_registry.json"],
        "outputs": ["BEHAVIORAL_AUDIT.md"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },

    # === Governance agents (NEW) ===
    "governor_daily": {
        "purpose": "Run daily ingest, analysis, backlog maintenance, and brief generation",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["cognitive_state.json", "idea_registry.json", "conversation_classifications.json", "completion_stats.json"],
        "outputs": ["daily_brief.md", "governance_state.json"],
        "can_modify_files": True,
        "can_trigger_agents": True,
    },
    "governor_weekly": {
        "purpose": "Run weekly aggregation, lane review, and governor packet generation",
        "autonomy": AutonomyLevel.DRAFT_ROUTE,
        "mode": "ai_for_you",
        "inputs": ["governance_state.json", "idea_registry.json", "BEHAVIORAL_AUDIT.md"],
        "outputs": ["weekly_governor_packet.md"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "backlog_maintainer": {
        "purpose": "Merge duplicates, kill low-score items, enforce 2-lane integrity",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["idea_registry.json", "governance_state.json"],
        "outputs": ["idea_registry.json (mutated)", "backlog_maintenance_log.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
    "idea_parker": {
        "purpose": "Auto-park new ideas not aligned with active lanes",
        "autonomy": AutonomyLevel.EXECUTE_REPORT,
        "mode": "ai_for_itself",
        "inputs": ["idea_registry.json", "governance_state.json"],
        "outputs": ["ideas_reservoir.json"],
        "can_modify_files": True,
        "can_trigger_agents": False,
    },
}


# ============================================================
# LANE MANAGEMENT
# Active lanes the system is allowed to work on.
# ============================================================

ACTIVE_LANES = [
    {
        "id": "lane_1",
        "name": "Power Dynamics Book + Companion GPT",
        "type": "product",
        "status": "in_progress",
        "ship_criteria": "Published on Kindle/Gumroad with companion GPT live",
        "deadline_weeks": 4,
    },
    {
        "id": "lane_2",
        "name": "AI Automation Consulting (First Client)",
        "type": "service",
        "status": "in_progress",
        "ship_criteria": "1 paid engagement completed",
        "deadline_weeks": 8,
    },
]

# Ideas reservoir: parked ideas that can't enter active lanes
# until a lane slot opens (something ships or gets archived)
IDEAS_RESERVOIR_RULES = {
    "max_active_lanes": TARGETS["max_active_lanes"],
    "promotion_requires": "governor_approval",  # you must explicitly promote
    "auto_park_threshold": 0.0,  # any new idea auto-parks (moratorium)
}


# ============================================================
# ROUTING THRESHOLDS
# Same as existing system, centralized here.
# ============================================================

ROUTING = {
    "closure_ratio_critical": 15.0,   # below = CLOSURE mode
    "open_loops_critical": 20,        # above = CLOSURE mode
    "open_loops_caution": 10,         # above = MAINTENANCE mode
    "min_loop_score": 18000,          # only conversations above this score count as open loops
    # else = BUILD mode
}


def compute_mode(closure_ratio: float, open_loops: int) -> tuple:
    """Single source of truth for Python-side mode routing.

    Returns: (mode, risk, build_allowed)

    Python handles 3 modes (CLOSURE, MAINTENANCE, BUILD).
    RECOVER, COMPOUND, SCALE require signals Python doesn't track
    (sleep_hours, assets_shipped, money_delta) and are handled by
    the TypeScript governance daemon.
    """
    if closure_ratio < ROUTING["closure_ratio_critical"] or open_loops > ROUTING["open_loops_critical"]:
        return "CLOSURE", "HIGH", False
    elif open_loops > ROUTING["open_loops_caution"]:
        return "MAINTENANCE", "MEDIUM", True
    else:
        return "BUILD", "LOW", True


# ============================================================
# DAILY BRIEF TEMPLATE
# Structure for the governor's daily brief.
# ============================================================

DAILY_BRIEF_TEMPLATE = {
    "sections": [
        "mode",           # CLOSURE / MAINTENANCE / BUILD
        "world_changed",  # 3 bullets: what changed
        "leverage_moves", # 3 bullets: top moves for today (within lanes)
        "automation_target",  # 1 bullet: what to remove from manual
        "decisions",      # binary approve/reject asks
    ],
    "max_decisions": 3,   # don't overwhelm with choices
    "format": "markdown",
}


# ============================================================
# WEEKLY PACKET TEMPLATE
# Structure for the governor's weekly review.
# ============================================================

WEEKLY_PACKET_TEMPLATE = {
    "sections": [
        "reality_check",       # where time/attention actually went
        "lane_progress",       # what shipped, what moved, what stalled
        "autonomy_proposals",  # promote/demote agent levels
        "lane_integrity",      # did governor try to create lane 3?
        "stop_list",           # what to ruthlessly stop
        "decisions",           # 3-5 yes/no choices
    ],
    "max_decisions": 5,
    "format": "markdown",
}
