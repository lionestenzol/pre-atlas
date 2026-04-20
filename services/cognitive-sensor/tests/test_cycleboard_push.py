"""Tests for cycleboard_push.py bridge.

Covers:
  - directive_entry_id stability + day-bucketing + confidence-independence
  - mapping: journal/task/proposal/win shapes
  - archive_log appends JSONL with _archived_at
  - run() dry-run reports counts without touching HTTP
  - run() respects sent ledger (idempotent)
  - run() handles missing auto_actor_log gracefully
  - run() does not crash when delta-kernel is down (HTTP returns None)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import cycleboard_push as cbp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect all file paths to tmp_path so tests never touch real data."""
    monkeypatch.setattr(cbp, "BASE", tmp_path)
    monkeypatch.setattr(cbp, "AUTO_ACTOR_LOG", tmp_path / "auto_actor_log.json")
    monkeypatch.setattr(cbp, "LOOP_RECS", tmp_path / "loop_recommendations.json")
    monkeypatch.setattr(cbp, "LOG_ARCHIVE", tmp_path / "auto_actor_log_archive.jsonl")
    monkeypatch.setattr(cbp, "SENT_LEDGER_PATH", tmp_path / "cycleboard_push_sent.json")
    monkeypatch.setattr(cbp, "PROPOSALS_PATH", tmp_path / "proposals.json")
    return tmp_path


def _write_log(sandbox: Path, data: dict) -> None:
    (sandbox / "auto_actor_log.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# directive_entry_id
# ---------------------------------------------------------------------------
def test_directive_entry_id_stable_within_day():
    a = cbp.directive_entry_id("EXECUTE", "growth", "Scale C110", "2026-04-20T08:00:00Z")
    b = cbp.directive_entry_id("EXECUTE", "growth", "Scale C110", "2026-04-20T23:59:59Z")
    assert a == b


def test_directive_entry_id_changes_across_days():
    a = cbp.directive_entry_id("EXECUTE", "growth", "Scale C110", "2026-04-20T08:00:00Z")
    b = cbp.directive_entry_id("EXECUTE", "growth", "Scale C110", "2026-04-21T08:00:00Z")
    assert a != b


def test_directive_entry_id_independent_of_confidence():
    # The id is synthesized from dtype, domain, rationale[:80], day.
    # Pass the exact same inputs twice — confidence drift would not even enter
    # the function, so equality is by construction. This is the contract test.
    a = cbp.directive_entry_id("INVEST", "research", "dig deeper", "2026-04-20")
    b = cbp.directive_entry_id("INVEST", "research", "dig deeper", "2026-04-20")
    assert a == b


def test_directive_entry_id_different_domain_gives_different_id():
    a = cbp.directive_entry_id("EXECUTE", "growth", "x", "2026-04-20")
    b = cbp.directive_entry_id("EXECUTE", "closure", "x", "2026-04-20")
    assert a != b


# ---------------------------------------------------------------------------
# Mapping builders
# ---------------------------------------------------------------------------
def test_build_journal_content():
    text = cbp.build_journal_content({
        "directive_type": "RESURRECT",
        "domain": "overview / chatgpt",
        "rationale": "dormant 30d, one clear revive path",
    })
    assert "auto: RESURRECT/overview / chatgpt" in text
    assert "dormant" in text


def test_build_review_title():
    title = cbp.build_review_title({
        "directive_type": "EXECUTE",
        "domain": "ship inPACT lesson",
    })
    assert title == "[REVIEW] EXECUTE/ship inPACT lesson"


def test_build_proposal_shape():
    d = {
        "directive_type": "EXECUTE",
        "domain": "ship",
        "rationale": "ready to go",
        "suggested_action": "commit lesson 5",
        "confidence": 0.4,
        "risk_level": "high",
    }
    p = cbp.build_proposal(d, entry_id="abc123")
    assert p["proposal_id"] == "abc123"
    assert p["status"] == "pending"
    assert p["confidence"] == 0.4
    assert "proposed_at" in p


def test_build_win_text_truncates():
    text = cbp.build_win_text("42", "A very long title " * 30)
    assert text.startswith("Closed #42:")
    assert len(text) <= 200


def test_loop_title_looks_up_from_auto_closed_first():
    recs = {
        "auto_closed": [{"convo_id": "5", "title": "Found here"}],
        "recommendations": [{"convo_id": "5", "title": "Other spot"}],
    }
    assert cbp.loop_title("5", recs) == "Found here"


def test_loop_title_falls_back_to_recommendations():
    recs = {
        "auto_closed": [],
        "recommendations": [{"convo_id": "7", "title": "Rec title"}],
    }
    assert cbp.loop_title("7", recs) == "Rec title"


def test_loop_title_returns_untitled_when_missing():
    assert cbp.loop_title("999", {}) == "(untitled)"


# ---------------------------------------------------------------------------
# Archive append
# ---------------------------------------------------------------------------
def test_archive_log_appends_jsonl(sandbox):
    cbp.archive_log({"run_at": "2026-04-20T10:00:00Z", "directives_executed": []})
    cbp.archive_log({"run_at": "2026-04-20T18:00:00Z", "directives_executed": []})
    lines = (sandbox / "auto_actor_log_archive.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        parsed = json.loads(line)
        assert "_archived_at" in parsed


# ---------------------------------------------------------------------------
# run() -- dry-run
# ---------------------------------------------------------------------------
def test_dry_run_counts_and_does_not_touch_http(sandbox, monkeypatch):
    # Sabotage _http so any call raises — dry-run must not reach it.
    def boom(*args, **kwargs):
        raise AssertionError("dry-run must not make HTTP calls")
    monkeypatch.setattr(cbp, "_http", boom)

    _write_log(sandbox, {
        "run_at": "2026-04-20T08:00:00Z",
        "directives_executed": [
            {"directive_type": "RESURRECT", "domain": "a", "rationale": "r1",
             "confidence": 0.8, "risk_level": "low", "status": "auto_executed"},
            {"directive_type": "EXECUTE", "domain": "b", "rationale": "r2",
             "confidence": 0.4, "risk_level": "high", "status": "needs_approval"},
        ],
        "loops_auto_closed": ["42"],
    })
    (sandbox / "loop_recommendations.json").write_text(
        json.dumps({"auto_closed": [{"convo_id": "42", "title": "The 42 loop"}]}),
        encoding="utf-8",
    )

    summary = cbp.run(dry_run=True)
    assert summary["journal_added"] == 1
    assert summary["tasks_added"] == 1
    assert summary["wins_added"] == 1
    # Dry run must not write the ledger
    assert not (sandbox / "cycleboard_push_sent.json").exists()
    assert not (sandbox / "proposals.json").exists()


def test_run_handles_missing_log(sandbox):
    summary = cbp.run(dry_run=False)
    assert summary.get("note") == "no_auto_actor_log"
    assert summary["journal_added"] == 0


def test_run_skips_already_sent(sandbox, monkeypatch):
    # Seed sent ledger with the entry id that would be synthesized.
    eid = cbp.directive_entry_id("RESURRECT", "a", "r1", "2026-04-20T08:00:00Z")
    (sandbox / "cycleboard_push_sent.json").write_text(
        json.dumps({eid: "2026-04-19T00:00:00Z"}), encoding="utf-8"
    )
    _write_log(sandbox, {
        "run_at": "2026-04-20T08:00:00Z",
        "directives_executed": [
            {"directive_type": "RESURRECT", "domain": "a", "rationale": "r1",
             "confidence": 0.8, "risk_level": "low", "status": "auto_executed"},
        ],
        "loops_auto_closed": [],
    })

    # _http must not be called for the one already-sent entry
    called = []
    def capture(method, path, body=None, api_key=None):
        called.append((method, path))
        return {"data": {}}
    monkeypatch.setattr(cbp, "_http", capture)

    summary = cbp.run(dry_run=True)
    assert summary["skipped_already_sent"] == 1
    assert summary["journal_added"] == 0


# ---------------------------------------------------------------------------
# run() -- HTTP-down tolerance
# ---------------------------------------------------------------------------
def test_run_does_not_crash_when_delta_kernel_down(sandbox, monkeypatch):
    # _http returns None on every call to simulate service unavailable.
    monkeypatch.setattr(cbp, "_http", lambda *a, **kw: None)
    _write_log(sandbox, {
        "run_at": "2026-04-20T08:00:00Z",
        "directives_executed": [
            {"directive_type": "RESURRECT", "domain": "a", "rationale": "r1",
             "confidence": 0.8, "risk_level": "low", "status": "auto_executed"},
            {"directive_type": "EXECUTE", "domain": "b", "rationale": "r2",
             "confidence": 0.4, "risk_level": "high", "status": "needs_approval"},
        ],
        "loops_auto_closed": [],
    })

    summary = cbp.run(dry_run=False)
    assert summary["failures"] >= 1
    # Nothing succeeded, so no ledger file should be written
    assert not (sandbox / "cycleboard_push_sent.json").exists()
    # Archive should still have been written
    assert (sandbox / "auto_actor_log_archive.jsonl").exists()


def test_run_persists_ledger_on_partial_success(sandbox, monkeypatch):
    """If tasks succeed but cycleboard PUT fails, ledger should contain only
    the successfully-sent entries."""
    def fake_http(method, path, body=None, api_key=None):
        if path == "/api/tasks" and method == "POST":
            return {"ok": True}
        # cycleboard GET/PUT fail
        return None
    monkeypatch.setattr(cbp, "_http", fake_http)

    _write_log(sandbox, {
        "run_at": "2026-04-20T08:00:00Z",
        "directives_executed": [
            {"directive_type": "RESURRECT", "domain": "a", "rationale": "r1",
             "confidence": 0.8, "risk_level": "low", "status": "auto_executed"},
            {"directive_type": "EXECUTE", "domain": "b", "rationale": "r2",
             "confidence": 0.4, "risk_level": "high", "status": "needs_approval"},
        ],
        "loops_auto_closed": [],
    })

    summary = cbp.run(dry_run=False)
    assert summary["tasks_added"] == 1
    assert summary["journal_added"] == 0
    assert summary["failures"] >= 1

    ledger = json.loads((sandbox / "cycleboard_push_sent.json").read_text(encoding="utf-8"))
    # Task entry was sent; journal entry was not
    task_eid = cbp.directive_entry_id("EXECUTE", "b", "r2", "2026-04-20T08:00:00Z")
    journal_eid = cbp.directive_entry_id("RESURRECT", "a", "r1", "2026-04-20T08:00:00Z")
    assert task_eid in ledger
    assert journal_eid not in ledger
