"""Tests for ghost_executor.consume_directive."""
from __future__ import annotations
import pytest

from cortex.ghost_executor import consume_directive, DirectiveInvalidError


def _valid_directive() -> dict:
    return {
        "schema_version": "1.0",
        "id": "dir_test_01",
        "issued_at": "2026-04-19T00:00:00Z",
        "priority_tier": "high",
        "leverage_score": 0.8,
        "task": {
            "id": "task_01",
            "label": "Ship lesson 5",
            "type": "build",
            "success_criteria": ["lesson renders", "no em dashes"],
        },
        "context_bundle": {
            "project_id": "pre-atlas",
            "relevant_files": ["apps/inpact/content/lessons/5.md"],
        },
        "execution": {
            "target_agent": "optogon",
            "autonomy_level": "supervised",
            "timeout_seconds": 1800,
        },
        "interrupt_policy": {"interruptible": True},
    }


def test_consume_valid_directive_returns_task_prompt():
    tp = consume_directive(_valid_directive(), working_directory="/repo")
    assert tp["schema_version"] == "1.0"
    assert tp["directive_id"] == "dir_test_01"
    assert tp["instruction"]["objective"] == "Ship lesson 5"
    assert tp["environment"]["working_directory"] == "/repo"
    assert tp["instruction"]["success_criteria"] == ["lesson renders", "no em dashes"]
    assert tp["instruction"]["failure_criteria"], "failure_criteria must be non-empty"


def test_consume_invalid_directive_raises():
    bad = _valid_directive()
    bad["task"]["success_criteria"] = []  # minItems: 1 on Directive schema
    with pytest.raises(DirectiveInvalidError) as exc:
        consume_directive(bad)
    assert any("success_criteria" in d for d in exc.value.details)


def test_consume_prior_attempts_mapped():
    d = _valid_directive()
    d["context_bundle"]["prior_attempts"] = [
        {"attempt_id": "a1", "outcome": "failed preview render", "lessons": ["check shared.css path"]}
    ]
    tp = consume_directive(d)
    assert len(tp["prior_attempts"]) == 1
    assert "preview" in tp["prior_attempts"][0]["summary"]
