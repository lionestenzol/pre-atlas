"""Tests for tools/lattice/ledger_feed.py -- the Seq 5 ledger feed.

Mirrors test_seam.py's ledger-feed tests exactly (same SEAM_LEDGER /
SEAM_LEDGER_PATH env-var gating pattern, same "gated off by default" +
"objective reward" + "monotonic invocation_index" shape) since ledger_feed.py
deliberately reuses that mechanism rather than reinventing it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_lattice_module(name: str):
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lf = _load_lattice_module("ledger_feed")


def _receipt(tool: str, *, ok: bool = True, sha: str | None = "abc123") -> dict:
    return {
        "seam_version": "v1",
        "tool": tool,
        "sha256": sha if ok else None,
        "produced_at": "2026-07-16T00:00:00+00:00",
        "status": "ok" if ok else "error",
        "data": {} if ok else None,
        "error": None if ok else "boom",
    }


def test_gated_off_by_default_never_touches_the_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.delenv("SEAM_LEDGER", raising=False)
    assert lf.append_ledger([_receipt("code-recon")], "t1") == 0
    assert not ledger.exists()


def test_writes_one_objective_row_per_receipt(tmp_path, monkeypatch):
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    receipts = [_receipt("code-recon"), _receipt("groundwork")]
    n = lf.append_ledger(receipts, "thread-a")

    assert n == 2
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["skill"] for r in rows] == ["code-recon", "groundwork"]
    assert all(r["source"] == "lattice" for r in rows)
    assert all(r["session"] == "lattice:thread-a" for r in rows)
    assert all(r["reward_score"] == 1.0 for r in rows)  # router._row_reward reads this first


def test_error_receipt_scores_objective_error_not_ok(tmp_path, monkeypatch):
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    lf.append_ledger([_receipt("code-recon", ok=False)], "thread-b")
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows[0]["reward"] == "objective_error"
    assert rows[0]["reward_score"] == -1.0


def test_ok_status_with_no_sha256_is_penalized_not_credited(tmp_path, monkeypatch):
    """Same bar as seam's _receipt_ok: status=ok alone isn't enough -- no join
    key means the tool didn't deliver a content-addressed artifact."""
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    receipt = _receipt("code-recon")
    receipt["sha256"] = None  # status ok, but nothing content-addressed
    lf.append_ledger([receipt], "thread-c")
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows[0]["reward_score"] == -1.0


def test_bandit_receipt_is_excluded_from_the_ledger_feed(tmp_path, monkeypatch):
    """The bandit's own routing receipt must not become a fake skill firing --
    it always immediately precedes whatever it routed to, by construction, so
    it isn't a learnable transition."""
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    receipts = [_receipt("bandit"), _receipt("code-recon"), _receipt("groundwork")]
    n = lf.append_ledger(receipts, "thread-d")
    assert n == 2
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert "bandit" not in [r["skill"] for r in rows]


def test_each_row_gets_a_distinct_request_key_so_combo_reads_it_as_seq_not_cofire():
    """Unlike seam (one shared request per manifest -> cofire pairs), lattice
    chain nodes execute in a determined order -- giving each row a distinct
    `request` keeps them as separate turns so build_combos derives a>b
    transitions (seq), not order-free pairs (cofire), matching what actually
    happened in the graph."""
    receipts = [_receipt("code-recon"), _receipt("groundwork")]
    rows = lf.ledger_rows(receipts, "thread-e", base_index=0)
    assert rows[0]["request"] != rows[1]["request"]
    assert rows[0]["invocation_index"] < rows[1]["invocation_index"]


def test_invocation_index_is_monotonic_across_repeated_appends(tmp_path, monkeypatch):
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    lf.append_ledger([_receipt("code-recon")], "thread-f")
    lf.append_ledger([_receipt("groundwork")], "thread-f")  # same thread_id -> same session
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["invocation_index"] for r in rows] == [0, 1]


def test_combo_py_actually_reads_lattice_rows_and_still_beats_random(tmp_path, monkeypatch):
    """The Seq 5 DoD, literally: ledger grows on a real graph run; combo.py
    --evaluate still beats random with the new rows. Builds a small synthetic
    lattice-shaped ledger (mirrors real chain shape: many code-recon>groundwork
    sequences that succeed, a losing one-off combo) and proves combo.py's own
    evaluate() reads it and prefers the winning combo over random."""
    # combo.evaluate()'s holdout split hashes session id -> Python's hash() is
    # salted per PROCESS (PYTHONHASHSEED), not per test, so a small fixture is
    # genuinely flaky: confirmed empirically (2/5 seeds failed at 12-vs-3
    # sessions, still 2/15 at 60-vs-15). Root cause diagnosed directly (not
    # guessed): at a failing seed, the 70/30 split drew ZERO losing-arm
    # sessions into holdout (only 15 existed), so random_expected_reward
    # accidentally equalled combo_expected_reward -- a genuine tie, which
    # evaluate()'s own docstring calls honest reporting, not a bug. The fix
    # is enough losing-arm sessions that a holdout draw of zero becomes
    # vanishingly improbable (P(all n land in train) = 0.7^n), not a smaller
    # or re-seeded fixture.
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    n_win, n_lose = 200, 60
    for i in range(n_win):
        receipts = [_receipt("code-recon"), _receipt("groundwork")]
        lf.append_ledger(receipts, f"thread-g{i}")
    for i in range(n_lose):
        receipts = [_receipt("code-recon"), _receipt("weapon", ok=False)]
        lf.append_ledger(receipts, f"thread-h{i}")

    sys.path.insert(0, r"C:\Users\bruke\.claude\scripts\ledger")
    import combo
    rows = combo.router.load_rows(ledger)
    assert len(rows) == n_win * 2 + n_lose * 2
    result = combo.evaluate(rows)
    assert result["ok"] is True
    assert result["beats_random"] is True
