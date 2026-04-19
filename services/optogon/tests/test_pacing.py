"""Tests for pacing constraints in response_composer."""
from __future__ import annotations

from optogon.response_composer import enforce_pacing, compose


def test_enforce_pacing_trims_extra_questions():
    text = "Which lesson? And where is the draft? Also what's the theme?"
    final, q = enforce_pacing(text, max_questions=1)
    assert q == 1
    assert final.count("?") == 1


def test_enforce_pacing_preserves_single_question():
    text = "Which lesson are you shipping?"
    final, q = enforce_pacing(text, max_questions=1)
    assert q == 1
    assert final == text


def test_compose_gate_is_silent():
    node = {"type": "gate", "id": "g"}
    text, tokens = compose(node, {})
    assert text == ""
    assert tokens == 0


def test_compose_qualify_with_question():
    node = {
        "type": "qualify",
        "id": "q",
        "qualification": {"question": {"text": "Which lesson?"}},
    }
    text, tokens = compose(node, {})
    assert "Which lesson?" in text
    assert tokens > 0
