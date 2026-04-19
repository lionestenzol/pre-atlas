"""Context hierarchy - confirmed > user > inferred > system.

Per doctrine/03_OPTOGON_SPEC.md Section 8 'Context Hierarchy'.
"""
from __future__ import annotations
from typing import Any, Literal

Tier = Literal["confirmed", "user", "inferred", "system"]
TIER_ORDER: tuple[Tier, ...] = ("confirmed", "user", "inferred", "system")


def empty_context() -> dict[str, dict[str, Any]]:
    return {"confirmed": {}, "user": {}, "inferred": {}, "system": {}}


def resolve(key: str, context: dict[str, dict[str, Any]]) -> tuple[Any, Tier | None]:
    """Return (value, tier) for key, or (None, None) if unknown."""
    for tier in TIER_ORDER:
        if key in context.get(tier, {}):
            return context[tier][key], tier
    return None, None


def set_tier(context: dict[str, dict[str, Any]], tier: Tier, key: str, value: Any) -> None:
    """Set key at given tier. Does not enforce override rules - caller decides."""
    context.setdefault(tier, {})[key] = value


def promote_to_confirmed(context: dict[str, dict[str, Any]], key: str) -> bool:
    """Promote the highest-priority known value for key into confirmed. Returns True if promoted."""
    value, tier = resolve(key, context)
    if value is None or tier == "confirmed":
        return False
    set_tier(context, "confirmed", key, value)
    # Clear lower tiers for this key so resolve() returns confirmed cleanly
    for t in TIER_ORDER:
        if t == "confirmed":
            continue
        context.get(t, {}).pop(key, None)
    return True


def known_keys(context: dict[str, dict[str, Any]]) -> set[str]:
    """All keys across all tiers."""
    out: set[str] = set()
    for tier in TIER_ORDER:
        out.update(context.get(tier, {}).keys())
    return out


def missing_keys(required: list[str], context: dict[str, dict[str, Any]]) -> list[str]:
    """Return keys from required that have no value at any tier."""
    known = known_keys(context)
    return [k for k in required if k not in known]
