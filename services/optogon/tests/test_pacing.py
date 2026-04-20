"""Tests for pacing constraints in response_composer (Phase 2)."""
from __future__ import annotations

from optogon.response_composer import compose, enforce_pacing


def test_enforce_pacing_substitutes_fallback_when_too_many_questions():
    text = "Which lesson? And where is the draft? Also what's the theme?"
    node = {
        "type": "qualify",
        "qualification": {
            "required": [{"key": "lesson_number"}],
            "question": {"text": "Which lesson?"},
        },
    }
    session_state = {"context": {"confirmed": {}, "user": {}, "inferred": {}, "system": {}}}
    final, q, violations = enforce_pacing(
        text, node=node, session_state=session_state, max_questions=1
    )
    assert violations
    # fallback asks for the single missing key, not the original 3 questions
    assert final.count("?") <= 1


def test_enforce_pacing_preserves_single_question():
    text = "Which lesson are you shipping?"
    final, q, violations = enforce_pacing(text, max_questions=1)
    assert q == 1
    assert not violations
    assert final == text


def test_compose_gate_is_silent():
    node = {"type": "gate", "id": "g"}
    text, tokens, violations = compose(node, {})
    assert text == ""
    assert tokens == 0
    assert violations == []


def test_compose_qualify_with_question():
    node = {
        "type": "qualify",
        "id": "q",
        "qualification": {"question": {"text": "Which lesson?"}},
    }
    text, tokens, violations = compose(node, {})
    assert "Which lesson?" in text
    assert tokens > 0
    assert violations == []
