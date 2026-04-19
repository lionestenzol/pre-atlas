"""Tests for contract_validator module."""
from __future__ import annotations
import pytest

from optogon.contract_validator import ContractError, validate, is_valid


def test_validate_close_signal_minimal():
    payload = {
        "schema_version": "1.0",
        "id": "close_test",
        "session_id": "sess_test",
        "path_id": "ship_inpact_lesson",
        "closed_at": "2026-04-19T00:00:00Z",
        "status": "completed",
        "deliverables": [{"type": "confirmation", "label": "done"}],
        "session_summary": {
            "total_tokens": 100,
            "total_questions_asked": 1,
            "total_inferences_made": 2,
            "inference_accuracy": 0.9,
            "nodes_closed": 5,
            "nodes_total": 5,
            "time_to_close_seconds": 60.0,
            "path_completion_rate": 1.0,
        },
    }
    assert validate(payload, "CloseSignal") is True


def test_validate_close_signal_bad_status_raises():
    payload = {
        "schema_version": "1.0",
        "id": "close_test",
        "session_id": "sess_test",
        "path_id": "ship_inpact_lesson",
        "closed_at": "2026-04-19T00:00:00Z",
        "status": "bogus",
        "deliverables": [],
        "session_summary": {
            "total_tokens": 0, "total_questions_asked": 0, "total_inferences_made": 0,
            "inference_accuracy": 0.0, "nodes_closed": 0, "nodes_total": 0,
            "time_to_close_seconds": 0.0, "path_completion_rate": 0.0,
        },
    }
    with pytest.raises(ContractError):
        validate(payload, "CloseSignal")


def test_is_valid_returns_false_without_raising():
    assert is_valid({"not_a_signal": True}, "Signal") is False


def test_validate_unknown_contract_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        validate({}, "NopeNotReal")
