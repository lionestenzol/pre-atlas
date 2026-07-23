"""Tests for cognitive_api.get_closure_backlog() — the unpoisoned closure metrics.

Regression coverage for the 2026-06-21 bulk-triage poisoning (145 ARCHIVE rows
in one night made the 30% closure_quality gate need 63 consecutive CLOSE
decisions — mathematically unreachable). Fixed in commit 4408478 by excluding
that one sweep from the quality/ratio denominators. These tests prove the
threshold is reachable post-fix AND that ordinary archiving still counts
against quality (the fix is an exclusion, not a whitewash).
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cognitive_api
from atlas_config import compute_mode, ROUTING


def make_ledger(tmp_path, monkeypatch, decisions, open_loop_ids):
    """Point cognitive_api at a synthetic loop_decisions table + loops_latest.json."""
    con = sqlite3.connect(str(tmp_path / "test_results.db"))
    cur = con.cursor()
    cur.execute("CREATE TABLE loop_decisions (convo_id TEXT, decision TEXT, date TEXT)")
    cur.executemany("INSERT INTO loop_decisions VALUES (?,?,?)", decisions)
    con.commit()

    loops = [{"convo_id": cid, "title": f"Loop {cid}", "score": 20000} for cid in open_loop_ids]
    (tmp_path / "loops_latest.json").write_text(json.dumps(loops), encoding="utf-8")

    monkeypatch.setattr(cognitive_api, "cur", cur)
    monkeypatch.chdir(tmp_path)


def bulk_triage_night(n=145):
    """The poisoning shape: one night, all ARCHIVE."""
    return [(str(9000 + i), "ARCHIVE", "2026-06-21 23:09") for i in range(n)]


class TestBulkNightExclusion:
    def test_poisoned_night_excluded_from_quality(self, tmp_path, monkeypatch):
        """145 bulk archives + 2 real closes → quality 100, not 2/147."""
        decisions = bulk_triage_night() + [
            ("5272", "CLOSE", "2026-07-07 00:48"),
            ("3411", "CLOSE", "2026-07-07 00:49"),
        ]
        make_ledger(tmp_path, monkeypatch, decisions, open_loop_ids=["1", "2"])
        closure = cognitive_api.get_closure_backlog()
        assert closure["truly_closed"] == 2
        assert closure["archived"] == 0  # bulk night excluded
        assert closure["closure_quality"] == 100.0

    def test_threshold_reachable_with_single_close(self, tmp_path, monkeypatch):
        """Pre-fix: 1 CLOSE against the bulk night = 0.68% (locked forever).
        Post-fix: the same single CLOSE clears the 30% gate."""
        decisions = bulk_triage_night() + [("5272", "CLOSE", "2026-07-07 00:48")]
        make_ledger(tmp_path, monkeypatch, decisions, open_loop_ids=["1"])
        closure = cognitive_api.get_closure_backlog()
        assert closure["closure_quality"] >= ROUTING["closure_quality_critical"]
        mode, _, build_allowed = compute_mode(
            closure["ratio"], closure["open"], closure["closure_quality"]
        )
        assert build_allowed is True

    def test_open_count_still_respects_bulk_archives(self, tmp_path, monkeypatch):
        """Exclusion is denominator-only: bulk-archived loops stay off the open list."""
        decisions = bulk_triage_night(n=3)
        # loop 9000-9002 were bulk-archived; 42 was never decided
        make_ledger(tmp_path, monkeypatch, decisions, open_loop_ids=["9000", "9001", "9002", "42"])
        closure = cognitive_api.get_closure_backlog()
        assert closure["open"] == 1  # only 42


class TestQualityStillHonest:
    def test_ordinary_archiving_still_locks(self, tmp_path, monkeypatch):
        """Archives recorded on any normal day still count: 1 CLOSE + 9 ARCHIVE
        = 10% quality → CLOSURE lock. The fix must not launder avoidance."""
        decisions = [("1", "CLOSE", "2026-07-08 10:00")] + [
            (str(100 + i), "ARCHIVE", "2026-07-08 10:01") for i in range(9)
        ]
        make_ledger(tmp_path, monkeypatch, decisions, open_loop_ids=["50"])
        closure = cognitive_api.get_closure_backlog()
        assert closure["closure_quality"] == 10.0
        mode, risk, build_allowed = compute_mode(
            closure["ratio"], closure["open"], closure["closure_quality"]
        )
        assert mode == "CLOSURE"
        assert build_allowed is False

    def test_quality_gate_boundary(self):
        """compute_mode locks strictly below 30, opens at 30."""
        assert compute_mode(50.0, 5, 29.9) == ("CLOSURE", "HIGH", False)
        mode, _, allowed = compute_mode(50.0, 5, 30.0)
        assert mode != "CLOSURE"
        assert allowed is True
