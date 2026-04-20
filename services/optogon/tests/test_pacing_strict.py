"""Strict pacing enforcement tests (audit Fix 1).

Spec 03_OPTOGON_SPEC.md Section 10 treats pacing as a hard constraint. The
composer must:
  - count sentences, not '?' characters
  - substitute a safe fallback when output exceeds max_questions
  - block node_id leaks with word-boundary matching
  - block session_id leaks
  - block option overflow past node.pacing.max_options_shown
  - surface each violation to the caller for metric tracking
"""
from __future__ import annotations

from optogon.response_composer import (
    _count_options,
    _count_questions,
    _scan_leaks,
    compose,
    enforce_pacing,
)


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def test_question_counter_is_sentence_aware():
    assert _count_questions("Is it A? Sure.") == 1
    assert _count_questions("Is it A? Is it B?") == 2
    # '?' inside a fenced code block is ignored
    assert _count_questions("Which one? ```if (x == 1)? return;```") == 1


def test_question_counter_handles_empty():
    assert _count_questions("") == 0
    assert _count_questions(None) == 0  # type: ignore[arg-type]


def test_option_counter_tallies_lists():
    text = "Pick one:\n1. foo\n2. bar\n3. baz"
    assert _count_options(text) == 3
    text_bullets = "- alpha\n- beta\n- gamma"
    assert _count_options(text_bullets) == 3


def test_leak_scan_catches_node_id_on_word_boundary():
    text = "Almost done with the entry node before merge."
    leaks = _scan_leaks(text, session_id=None, node_ids=["entry", "merge"])
    assert "entry" in leaks
    assert "merge" in leaks


def test_leak_scan_ignores_substring_match():
    # 'entry' appears inside 'reentry' — should not be flagged
    text = "Reentry into the flow is fine."
    leaks = _scan_leaks(text, session_id=None, node_ids=["entry"])
    assert "entry" not in leaks


def test_leak_scan_catches_session_id():
    text = "Debug info: sess_abc123 closed."
    leaks = _scan_leaks(text, session_id="sess_abc123", node_ids=[])
    assert "sess_abc123" in leaks


# ---------------------------------------------------------------------------
# enforce_pacing
# ---------------------------------------------------------------------------
def test_enforce_pacing_returns_three_tuple():
    text = "Single clean question?"
    result = enforce_pacing(text)
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_enforce_pacing_blocks_option_overflow():
    text = "Choose:\n1. foo\n2. bar\n3. baz\n4. qux\n5. extra"
    node = {
        "type": "qualify",
        "pacing": {"max_options_shown": 3},
        "qualification": {
            "required": [{"key": "pick"}],
            "question": {"text": "Pick one?"},
        },
    }
    state = {"context": {"confirmed": {}, "user": {}, "inferred": {}, "system": {}}}
    final, _q, violations = enforce_pacing(text, node=node, session_state=state)
    assert violations
    assert any("options" in v for v in violations)


def test_enforce_pacing_blocks_leaked_node_id():
    text = "Advancing to entry next."
    path = {"nodes": {"entry": {}, "merge": {}}}
    state = {"context": {"confirmed": {}, "user": {}, "inferred": {}, "system": {}}}
    node = {
        "type": "qualify",
        "qualification": {
            "required": [{"key": "x"}],
            "question": {"text": "What is x?"},
        },
    }
    _final, _q, violations = enforce_pacing(
        text, node=node, session_state=state, path=path
    )
    assert any("leak" in v for v in violations)


# ---------------------------------------------------------------------------
# compose wiring
# ---------------------------------------------------------------------------
def test_compose_returns_violations_list():
    node = {"type": "approval", "id": "a", "label": "commit file"}
    state = {"context": {"confirmed": {}, "user": {}, "inferred": {}, "system": {}}}
    text, tokens, violations = compose(node, state)
    assert isinstance(violations, list)
    assert tokens >= 0


def test_process_turn_increments_pacing_violations_metric():
    """End-to-end: a qualify node whose drafted question leaks a node_id
    should drive the pacing_violations counter up when process_turn runs."""
    from optogon.node_processor import process_turn

    path = {
        "schema_version": "1.0",
        "id": "p",
        "nodes": {
            "entry": {
                "id": "entry",
                "type": "qualify",
                "qualification": {
                    "required": [{"key": "thing"}],
                    # The drafted question leaks the node id "entry".
                    "question": {"text": "Which entry do you want?"},
                },
            },
        },
        "edges": [],
    }
    state = {
        "schema_version": "1.0",
        "session_id": "sess_test",
        "path_id": "p",
        "current_node": "entry",
        "started_at": "2026-04-20T00:00:00Z",
        "node_states": {},
        "context": {"confirmed": {}, "user": {}, "inferred": {}, "system": {}},
        "fork_stack": [],
        "action_log": [],
        "metrics": {
            "total_tokens": 0,
            "total_questions_asked": 0,
            "total_inferences_made": 0,
            "total_inferences_contradicted": 0,
            "total_actions_fired": 0,
            "pacing_violations": 0,
            "nodes_closed": 0,
            "nodes_total": 1,
        },
    }
    state, _text, _signals = process_turn(state, path, None)
    assert state["metrics"]["pacing_violations"] >= 1
