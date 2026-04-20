"""Tests for llm_parse — spec 03_OPTOGON_SPEC.md Section 14.

Without ANTHROPIC_API_KEY set, llm_parse falls through to the deterministic
heuristic. These tests cover the heuristic path and the pass-through contract.
"""
from __future__ import annotations

from optogon.response_composer import llm_parse


def test_heuristic_positional_split_two_keys():
    required = [
        {"key": "file_path", "description": "target file"},
        {"key": "commit_message", "description": "commit subject"},
    ]
    out = llm_parse("foo.py, fix typo", required)
    assert out.get("file_path") == "foo.py"
    assert out.get("commit_message") == "fix typo"


def test_heuristic_key_value_pairs():
    required = [
        {"key": "file_path", "description": "target file"},
        {"key": "commit_message", "description": "commit subject"},
    ]
    out = llm_parse("file_path=foo.py, commit_message=fix typo", required)
    assert out["file_path"] == "foo.py"
    assert out["commit_message"] == "fix typo"


def test_heuristic_single_key_single_message():
    required = [{"key": "lesson_number", "description": "lesson index"}]
    out = llm_parse("5", required)
    assert out.get("lesson_number") == 5  # coerced to int


def test_heuristic_coerces_scalars():
    required = [
        {"key": "ready", "description": "boolean gate"},
        {"key": "count", "description": "integer count"},
    ]
    out = llm_parse("ready=true, count=7", required)
    assert out["ready"] is True
    assert out["count"] == 7


def test_empty_message_returns_empty_dict():
    assert llm_parse("", [{"key": "a"}]) == {}
    assert llm_parse("anything", []) == {}


def test_unrecognized_keys_dropped():
    required = [{"key": "known"}]
    # "other=bar" is key=value but 'other' is not in required — must be dropped
    out = llm_parse("other=bar, known=val", required)
    assert "other" not in out
    assert out.get("known") == "val"


def test_heuristic_semicolon_split():
    required = [
        {"key": "a", "description": "first"},
        {"key": "b", "description": "second"},
    ]
    out = llm_parse("one; two", required)
    assert out.get("a") == "one"
    assert out.get("b") == "two"
