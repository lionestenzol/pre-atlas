"""Pure-function network engine for the Network agent.

All functions are pure: data in, result out. Zero I/O.
Handles contact management, relationship tracking, outreach scheduling,
and opportunity-to-contact matching.
"""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any


def _gen_id(prefix: str, data: str, now_iso: str) -> str:
    raw = f"{prefix}:{data}:{now_iso}"
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def compute_active_relationships(
    contacts: dict[str, dict[str, Any]],
    interactions: list[dict[str, Any]],
    now_iso: str,
    days: int = 30,
) -> int:
    """Count contacts with at least one interaction in the last N days."""
    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        return 0

    cutoff = now - timedelta(days=days)
    active_ids: set[str] = set()

    for ix in interactions:
        try:
            ix_date = datetime.fromisoformat(ix.get("date", "") + "T00:00:00+00:00")
            if ix_date >= cutoff:
                active_ids.add(ix["contact_id"])
        except (ValueError, TypeError):
            continue

    # Only count contacts that exist
    return len(active_ids & set(contacts.keys()))


def compute_collaboration_score(
    registry: dict[str, Any],
    now_iso: str,
) -> float:
    """Weighted collaboration score (0-100).

    Components:
      active contacts (40%): contacts with status active or warm
      recent interactions (30%): interactions in last 14 days
      pipeline health (30%): opportunities not closed
    """
    contacts = registry.get("contacts", {})
    interactions = registry.get("interactions", [])
    opportunities = registry.get("opportunities", [])

    if not contacts:
        return 0.0

    # Active contacts: warm + active as % of total
    active_count = sum(
        1 for c in contacts.values()
        if c.get("status") in ("warm", "active")
    )
    contact_ratio = min(1.0, active_count / max(1, len(contacts)))

    # Recent interactions (last 14 days)
    try:
        now = datetime.fromisoformat(now_iso)
        cutoff = now - timedelta(days=14)
        recent = sum(
            1 for ix in interactions
            if _parse_date(ix.get("date", "")) >= cutoff
        )
    except (ValueError, TypeError):
        recent = 0
    interaction_score = min(1.0, recent / 5.0)  # 5 interactions = full score

    # Pipeline health: non-closed opportunities
    pipeline = sum(1 for o in opportunities if o.get("stage") != "closed")
    pipeline_score = min(1.0, pipeline / 3.0)  # 3 active opportunities = full score

    return round(
        (contact_ratio * 40 + interaction_score * 30 + pipeline_score * 30),
        1,
    )


def _parse_date(date_str: str) -> datetime:
    """Parse a date string, appending time if needed."""
    if not date_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        if "T" in date_str:
            return datetime.fromisoformat(date_str)
        return datetime.fromisoformat(date_str + "T00:00:00+00:00")
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def compute_outreach_due(
    contacts: dict[str, dict[str, Any]],
    now_iso: str,
) -> list[dict[str, Any]]:
    """Find contacts past their follow-up date."""
    try:
        now = datetime.fromisoformat(now_iso)
    except (ValueError, TypeError):
        return []

    today = now.strftime("%Y-%m-%d")
    due: list[dict[str, Any]] = []

    for cid, contact in contacts.items():
        follow_up = contact.get("next_follow_up")
        if follow_up and follow_up <= today:
            due.append({
                "contact_id": cid,
                "name": contact.get("name", ""),
                "company": contact.get("company", ""),
                "next_follow_up": follow_up,
                "status": contact.get("status", "cold"),
                "days_overdue": (now.date() - datetime.fromisoformat(follow_up + "T00:00:00").date()).days,
            })

    return sorted(due, key=lambda d: -d["days_overdue"])


def match_opportunities_to_contacts(
    skill_opportunities: list[str],
    contacts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match skill leverage opportunities (from Loop 2) to contacts by tags."""
    if not skill_opportunities or not contacts:
        return []

    # Parse opportunity labels for keywords
    opp_keywords = set()
    for opp in skill_opportunities:
        for word in opp.lower().replace(":", " ").replace("_", " ").split():
            if len(word) > 3:
                opp_keywords.add(word)

    matches: list[dict[str, Any]] = []
    for cid, contact in contacts.items():
        contact_tags = set(t.lower() for t in contact.get("tags", []))
        overlap = opp_keywords & contact_tags
        if overlap:
            matches.append({
                "contact_id": cid,
                "name": contact.get("name", ""),
                "company": contact.get("company", ""),
                "matched_tags": list(overlap),
                "match_strength": len(overlap),
            })

    return sorted(matches, key=lambda m: -m["match_strength"])


def add_contact(
    registry: dict[str, Any],
    name: str,
    title: str = "",
    company: str = "",
    email: str = "",
    status: str = "cold",
    tags: list[str] | None = None,
    next_follow_up: str | None = None,
    notes: str = "",
    now_iso: str = "",
) -> tuple[dict[str, Any], str]:
    """Return new registry with contact added. Immutable."""
    updated = copy.deepcopy(registry)
    contacts = updated.setdefault("contacts", {})

    contact_id = _gen_id("c", name, now_iso)

    contacts[contact_id] = {
        "contact_id": contact_id,
        "name": name,
        "title": title,
        "company": company,
        "email": email,
        "status": status,
        "tags": tags or [],
        "last_contact_at": None,
        "next_follow_up": next_follow_up,
        "notes": notes,
    }

    updated["generated_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    return updated, contact_id


def log_interaction(
    registry: dict[str, Any],
    contact_id: str,
    interaction_type: str,
    outcome: str = "neutral",
    notes: str = "",
    date: str = "",
    now_iso: str = "",
) -> tuple[dict[str, Any], str]:
    """Return new registry with interaction logged. Updates contact status."""
    updated = copy.deepcopy(registry)
    contacts = updated.setdefault("contacts", {})
    interactions = updated.setdefault("interactions", [])

    if contact_id not in contacts:
        return updated, ""

    if not date:
        try:
            date = datetime.fromisoformat(now_iso).strftime("%Y-%m-%d") if now_iso else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ix_id = _gen_id("ix", f"{contact_id}:{date}", now_iso)

    interactions.append({
        "id": ix_id,
        "contact_id": contact_id,
        "date": date,
        "type": interaction_type,
        "outcome": outcome,
        "notes": notes,
    })

    # Update contact status based on outcome
    contact = contacts[contact_id]
    contact["last_contact_at"] = now_iso or datetime.now(timezone.utc).isoformat()

    if outcome == "positive":
        contact["status"] = "active"
    elif outcome == "neutral" and contact["status"] == "cold":
        contact["status"] = "warm"

    # Auto-schedule follow-up (7 days for active, 14 for warm, 30 for cold)
    days_ahead = {"active": 7, "warm": 14, "cold": 30, "dormant": 30}
    follow_days = days_ahead.get(contact["status"], 14)
    try:
        follow_date = datetime.fromisoformat(date + "T00:00:00") + timedelta(days=follow_days)
        contact["next_follow_up"] = follow_date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass

    # Keep last 200 interactions
    updated["interactions"] = interactions[-200:]
    updated["generated_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    return updated, ix_id


def compute_network_health_signals(
    registry: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Aggregate network health signals for compound scoring."""
    contacts = registry.get("contacts", {})
    interactions = registry.get("interactions", [])
    opportunities = registry.get("opportunities", [])

    active_rels = compute_active_relationships(contacts, interactions, now_iso)
    collab_score = compute_collaboration_score(registry, now_iso)
    outreach_due = compute_outreach_due(contacts, now_iso)

    # Pipeline value
    pipeline_value = sum(
        o.get("value_estimate", 0)
        for o in opportunities
        if o.get("stage") not in ("closed", None)
    )

    return {
        "total_contacts": len(contacts),
        "active_relationships": active_rels,
        "collaboration_score": collab_score,
        "outreach_due_count": len(outreach_due),
        "outreach_due": outreach_due[:5],
        "pipeline_value": pipeline_value,
        "pipeline_count": sum(1 for o in opportunities if o.get("stage") != "closed"),
        "interaction_count": len(interactions),
    }
