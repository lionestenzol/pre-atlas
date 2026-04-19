"""Tests for context hierarchy resolver."""
from __future__ import annotations

from optogon.context import empty_context, resolve, set_tier, promote_to_confirmed, missing_keys


def test_confirmed_beats_user_beats_inferred():
    ctx = empty_context()
    set_tier(ctx, "inferred", "lesson_number", 5)
    set_tier(ctx, "user", "lesson_number", 6)
    set_tier(ctx, "confirmed", "lesson_number", 7)
    value, tier = resolve("lesson_number", ctx)
    assert value == 7
    assert tier == "confirmed"


def test_user_wins_over_inferred_when_no_confirmed():
    ctx = empty_context()
    set_tier(ctx, "inferred", "theme", "dark")
    set_tier(ctx, "user", "theme", "light")
    value, tier = resolve("theme", ctx)
    assert value == "light"
    assert tier == "user"


def test_resolve_unknown_returns_none():
    ctx = empty_context()
    value, tier = resolve("missing", ctx)
    assert value is None
    assert tier is None


def test_promote_clears_lower_tiers():
    ctx = empty_context()
    set_tier(ctx, "inferred", "theme", "light")
    set_tier(ctx, "user", "theme", "light")
    assert promote_to_confirmed(ctx, "theme") is True
    assert "theme" not in ctx["inferred"]
    assert "theme" not in ctx["user"]
    assert ctx["confirmed"]["theme"] == "light"


def test_missing_keys():
    ctx = empty_context()
    set_tier(ctx, "confirmed", "a", 1)
    set_tier(ctx, "inferred", "b", 2)
    assert missing_keys(["a", "b", "c"], ctx) == ["c"]
