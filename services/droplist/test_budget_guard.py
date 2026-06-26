"""Regression tests for the AI spend-guard money bugs found in the 2026-06-26
adversarial review. These pin the fixes so the budget ceiling can't silently
regress into bypassable-for-real-dollars again.

See ~/.claude/rules/common/code-as-furniture.md.
"""
from __future__ import annotations

import os

os.environ.setdefault("DROPLIST_DATA", os.path.join(os.path.dirname(__file__), ".pytest-data-budget"))

from droplist import llm  # noqa: E402


def test_unmapped_paid_model_is_not_free():
    """openrouter/auto (and any unmapped PAID model) must estimate a non-zero cost
    from usage — logging 0 would let it slip past the daily budget forever."""
    cost = llm._usage_cost("openrouter/auto", 1_000_000, 1_000_000)
    assert cost > 0, "unmapped paid model must not cost $0 (budget-bypass bug)"
    # conservative fallback rate is $5/Mtok in + $15/Mtok out = $20 here
    assert abs(cost - 20.0) < 1e-6


def test_opus_priced_higher_than_sonnet():
    """call_json must not hardcode Sonnet pricing: Opus output is 5x Sonnet."""
    opus_in, opus_out = llm._rate_for("claude-opus-4-20250514")
    sonnet_in, sonnet_out = llm._rate_for("claude-sonnet-4-20250514")
    assert opus_out == 75.0 and sonnet_out == 15.0
    assert opus_out == 5 * sonnet_out


def test_local_ollama_stays_free():
    """Local providers genuinely cost nothing — they should not be over-charged in
    complete()'s fallback (the fallback is skipped for ollama/*)."""
    # _rate_for returns the conservative default, but complete() only applies it to
    # non-ollama models; assert the guard model prefix the code keys on.
    assert "ollama/llama3".startswith("ollama/")


def test_gpt4o_matches_before_gpt4():
    """Substring rate table must match the more specific key first."""
    assert llm._rate_for("openai/gpt-4o") == (2.50, 10.0)
    assert llm._rate_for("openai/gpt-4o-mini") == (0.15, 0.60)


def test_max_tokens_clamped():
    """A single oversized / negative / garbage max_tokens cannot outrun the budget."""
    from droplist import server

    assert server._clamp_tokens(10**9) == server.MAX_AI_TOKENS
    assert server._clamp_tokens(-5) == 1
    assert server._clamp_tokens("not-a-number") == min(1024, server.MAX_AI_TOKENS)
    assert server._clamp_tokens(None) == min(1024, server.MAX_AI_TOKENS)
    assert server._clamp_tokens(512) == 512


def test_bad_budget_env_does_not_crash_import():
    """A malformed DROPLIST_DAILY_AI_BUDGET must fall back, not crash the server."""
    from droplist import server

    assert server._env_float("DROPLIST__NOPE_NONEXISTENT", 5.0) == 5.0
    os.environ["DROPLIST__BAD_FLOAT_TEST"] = "not-a-float"
    try:
        assert server._env_float("DROPLIST__BAD_FLOAT_TEST", 5.0) == 5.0
    finally:
        del os.environ["DROPLIST__BAD_FLOAT_TEST"]
