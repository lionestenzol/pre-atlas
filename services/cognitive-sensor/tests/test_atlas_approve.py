"""Tests for atlas_approve CLI (status transitions, idempotency, listing)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import atlas_approve as aa


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(aa, "PROPOSALS_PATH", tmp_path / "proposals.json")
    return tmp_path


def _seed(sandbox: Path, proposals: list[dict]) -> None:
    (sandbox / "proposals.json").write_text(json.dumps(proposals), encoding="utf-8")


def test_list_empty_returns_zero(sandbox, capsys):
    rc = aa.cmd_list()
    assert rc == 0
    assert "No pending proposals" in capsys.readouterr().out


def test_approve_flips_status_and_records_timestamp(sandbox):
    _seed(sandbox, [
        {"proposal_id": "abc123", "dtype": "EXECUTE", "domain": "ship",
         "rationale": "x", "status": "pending"}
    ])
    rc = aa.cmd_approve("abc123", fire=False)
    assert rc == 0
    data = json.loads((sandbox / "proposals.json").read_text(encoding="utf-8"))
    assert data[0]["status"] == "approved"
    assert "approved_at" in data[0]


def test_approve_fails_for_missing_proposal(sandbox):
    _seed(sandbox, [])
    rc = aa.cmd_approve("nope", fire=False)
    assert rc == 1


def test_approve_fails_if_already_approved(sandbox):
    _seed(sandbox, [
        {"proposal_id": "a", "dtype": "X", "domain": "y", "status": "approved"}
    ])
    rc = aa.cmd_approve("a", fire=False)
    assert rc == 1


def test_deny_flips_status_and_records_reason(sandbox):
    _seed(sandbox, [
        {"proposal_id": "a", "dtype": "X", "domain": "y",
         "rationale": "r", "status": "pending"}
    ])
    rc = aa.cmd_deny("a", reason="not now")
    assert rc == 0
    data = json.loads((sandbox / "proposals.json").read_text(encoding="utf-8"))
    assert data[0]["status"] == "denied"
    assert data[0]["deny_reason"] == "not now"


def test_list_shows_only_pending(sandbox, capsys):
    _seed(sandbox, [
        {"proposal_id": "p1", "dtype": "EXECUTE", "domain": "d1",
         "rationale": "rationale one", "status": "pending", "confidence": 0.4, "risk_level": "high"},
        {"proposal_id": "p2", "dtype": "EXECUTE", "domain": "d2",
         "rationale": "r2", "status": "approved"},
    ])
    rc = aa.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "p1" in out
    assert "p2" not in out
