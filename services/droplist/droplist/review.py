"""drop-review: read packets.jsonl and surface unresolved work. Read-only.

No LLM. No mutation. Reports malformed lines instead of crashing on them.
Groups by status / domain / workflow / assigned_to / needs_human_decision and
puts unresolved (open / routed / waiting) packets first.
"""

from __future__ import annotations

from collections import Counter

from . import storage

UNRESOLVED = {"open", "routed", "waiting"}


def _counts(packets: list[dict], key: str) -> dict[str, int]:
    return dict(Counter(p.get(key, "?") for p in packets).most_common())


def build_review(
    recent: int | None = None,
    domain: str | None = None,
    status: str | None = None,
    needs_decision: bool = False,
) -> dict:
    """Return a structured review. Caller renders it."""
    packets, bad_lines = storage.read_with_errors(storage.PACKETS)

    if recent is not None:
        packets = packets[-recent:]

    filtered = packets
    if domain:
        filtered = [p for p in filtered if p.get("domain") == domain]
    if status:
        filtered = [p for p in filtered if p.get("status") == status]
    if needs_decision:
        filtered = [p for p in filtered if p.get("needs_human_decision")]

    # unresolved first, then everything else, each newest-last as stored
    unresolved = [p for p in filtered if p.get("status") in UNRESOLVED]
    resolved = [p for p in filtered if p.get("status") not in UNRESOLVED]

    return {
        "total": len(packets),
        "shown": len(filtered),
        "malformed_lines": bad_lines,
        "by_status": _counts(filtered, "status"),
        "by_domain": _counts(filtered, "domain"),
        "by_workflow": _counts(filtered, "selected_workflow"),
        "by_assigned": _counts(filtered, "assigned_to"),
        "needs_decision_count": sum(1 for p in filtered if p.get("needs_human_decision")),
        "unresolved": unresolved,
        "resolved": resolved,
    }
