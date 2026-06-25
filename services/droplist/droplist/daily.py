"""Daily Command DAG, executed as a rules-based brief (no LLM).

Walks the daily_command_dag node order against packets.jsonl:
  pull_open_packets -> retrieve_deadlines_unresolved_items -> group_by_domain
  -> choose_top_3_moves -> list_urgent_admin -> list_waiting_on
  -> list_decisions_needed -> output_brief

"Open" means anything not yet resolved: open / routed / waiting (not
logged / shipped / archived).
"""

from __future__ import annotations

from . import storage

_OPEN_STATES = {"open", "routed", "waiting"}

# who can actually move a packet forward right now
_ACTIONABLE = {"me", "claude_code", "claude", "script", "spark"}


def _is_open(p: dict) -> bool:
    return p.get("status") in _OPEN_STATES


def _priority(p: dict) -> float:
    """Higher = surface sooner. Pure function of packet fields."""
    score = 0.0
    if p.get("needs_human_decision"):
        score += 5
    t = p.get("type")
    if t == "warning":
        score += 5
    elif t == "problem":
        score += 3
    elif t == "follow_up":
        score += 2
    if p.get("status") == "waiting":
        score += 1
    # things you personally hold are the bottleneck; surface them
    if p.get("assigned_to") == "me":
        score += 1.5
    # money/admin tends to be time-bound
    if p.get("domain") == "money_admin":
        score += 1
    return score


def build_brief() -> dict:
    """Return a structured brief. Caller decides how to render it."""
    packets = storage.read_all(storage.PACKETS)
    open_packets = [p for p in packets if _is_open(p)]

    by_domain: dict[str, list[dict]] = {}
    for p in open_packets:
        by_domain.setdefault(p.get("domain", "general"), []).append(p)

    ranked = sorted(open_packets, key=_priority, reverse=True)

    top_3 = [p for p in ranked if p.get("assigned_to") in _ACTIONABLE][:3]
    urgent_admin = [p for p in open_packets if p.get("domain") == "money_admin"]
    waiting_on = [p for p in open_packets if p.get("status") == "waiting"]
    decisions = [
        p for p in open_packets
        if p.get("needs_human_decision") or p.get("type") == "decision"
    ]

    return {
        "total_open": len(open_packets),
        "by_domain": {d: len(v) for d, v in sorted(by_domain.items())},
        "top_3_moves": top_3,
        "urgent_admin": urgent_admin,
        "waiting_on": waiting_on,
        "decisions_needed": decisions,
    }
