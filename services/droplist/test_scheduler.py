"""Scheduler core acceptance: the testable half of Brick 3.

Proves TEMPORAL SELECTION without touching the real clock — every "now" is an
explicit datetime passed in, so the right jobs fire at the right times and the
result is deterministic and reproducible (mirrors clock.py's DROPLIST_NOW
discipline, clock.py:14).

What is proven (mechanism -> outcome):
  - At a "now" just after a job's cron fire time, that job is due.
  - At a "now" BETWEEN fires, no job is due (the gap is silent).
  - A job whose last_run is already at/after its most recent fire is NOT
    re-fired (last_run dedup) — running it once in a window settles it.
  - The exact id SET is correct at each instant (two jobs on different crons).
  - prev_fire / cron_due helpers agree with due_jobs.
  - Schedules load from a schedules.json registry on disk.

Pytest-collectable. Isolates DROPLIST_DATA to a temp dir BEFORE importing the
package, mirroring test_markoff.py:27-31 / test_graph.py:13-14. No data is read
from the wall clock anywhere in this file.

    python -m pytest test_scheduler.py -q
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile

import pytest

# Stable clock + isolated data dir BEFORE importing the package. The scheduler
# never reads clock.now() — but we set DROPLIST_NOW anyway so an accidental
# real-clock read would fail loudly rather than flake.
os.environ.setdefault("DROPLIST_NOW", "2026-06-25T12:00:00Z")
_TMP = tempfile.mkdtemp(prefix="sched_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import scheduler  # noqa: E402


def _dtime(s: str) -> dt.datetime:
    """ISO -> naive datetime (the project works in naive UTC, clock.py:17)."""
    return dt.datetime.fromisoformat(s)


# A fixed schedules set. Two daily jobs at different times + one hourly:
#   morning_tick  fires 09:00 every day
#   noon_chain    fires 12:00 every day
#   hourly_drop   fires at minute 0 of every hour
SCHEDULES = [
    {"id": "morning_tick", "cron": "0 9 * * *", "action": {"kind": "tick"}},
    {"id": "noon_chain", "cron": "0 12 * * *",
     "action": {"kind": "run_chain", "dag_id": "DAG-NOON"}},
    {"id": "hourly_drop", "cron": "0 * * * *",
     "action": {"kind": "drop", "text": "hourly heartbeat"}},
]


# ---------------------------------------------------------------------------
# cron_due / prev_fire helpers (single-expression window evaluation)
# ---------------------------------------------------------------------------

def test_prev_fire_is_strictly_before_now():
    now = _dtime("2026-06-25T09:30:00")
    assert scheduler.prev_fire("0 9 * * *", now) == _dtime("2026-06-25T09:00:00")
    # at exactly 09:00 the previous fire is the day before, not "now"
    assert scheduler.prev_fire("0 9 * * *", _dtime("2026-06-25T09:00:00")) == \
        _dtime("2026-06-24T09:00:00")


def test_cron_due_window_open_and_closed():
    cron = "0 9 * * *"
    fire = _dtime("2026-06-25T09:00:00")
    after = _dtime("2026-06-25T09:30:00")
    before = _dtime("2026-06-25T08:30:00")
    # never run -> due once now is at/after the fire
    assert scheduler.cron_due(cron, after, last_run=None) is True
    # already ran at the fire instant -> not due again this window
    assert scheduler.cron_due(cron, after, last_run=fire) is False
    # ran AFTER the fire -> still not due
    assert scheduler.cron_due(cron, after,
                              last_run=_dtime("2026-06-25T09:10:00")) is False
    # before the fire, never run -> the prev fire is yesterday's; if last_run is
    # yesterday's fire it's settled
    assert scheduler.cron_due(cron, before,
                              last_run=_dtime("2026-06-24T09:00:00")) is False


# ---------------------------------------------------------------------------
# due_jobs — the temporal-selection contract
# ---------------------------------------------------------------------------

def test_never_run_all_due_as_catchup():
    """Empty last_run = un-provisioned: every job has a fire in the past and no
    record of running it, so all fire once to catch up (this is the correct,
    not-skipped semantics — see test_missed_window_still_fires_once)."""
    now = _dtime("2026-06-25T09:00:30")  # 30s past 09:00
    due = scheduler.due_jobs(SCHEDULES, now, {})
    assert set(due) == {"morning_tick", "noon_chain", "hourly_drop"}


def test_only_fresh_window_due_when_others_serviced():
    """The discriminating case: noon already serviced for today, morning+hourly
    just fired their 09:00 window with last_run BEFORE it -> only those two."""
    now = _dtime("2026-06-25T09:00:30")  # 30s past 09:00
    last_run = {
        # serviced their 08:00 window, not yet 09:00 -> due now
        "morning_tick": _dtime("2026-06-24T09:00:00"),
        "hourly_drop": _dtime("2026-06-25T08:00:00"),
        # already serviced today's noon-? no: noon fires at 12:00, so to keep it
        # OUT we record a last_run at/after its most recent fire (yesterday 12:00)
        "noon_chain": _dtime("2026-06-24T12:00:00"),
    }
    due = scheduler.due_jobs(SCHEDULES, now, last_run)
    # noon's prev fire (yesterday 12:00) == last_run -> not due; the other two
    # have a 09:00 fire later than their last_run -> due
    assert set(due) == {"morning_tick", "hourly_drop"}


def test_nothing_due_between_fires():
    now = _dtime("2026-06-25T09:30:00")  # between 09:00 and 10:00 fires
    last_run = {
        "morning_tick": _dtime("2026-06-25T09:00:00"),
        "hourly_drop": _dtime("2026-06-25T09:00:00"),
        # noon's most recent fire is yesterday 12:00 and it's settled there,
        # so it stays silent until today's 12:00 fire
        "noon_chain": _dtime("2026-06-24T12:00:00"),
    }
    # all serviced for their most recent window; the 09:00-10:00 gap is silent
    assert scheduler.due_jobs(SCHEDULES, now, last_run) == []


def test_noon_chain_becomes_due_at_noon():
    now = _dtime("2026-06-25T12:00:05")
    last_run = {
        "morning_tick": _dtime("2026-06-25T09:00:00"),
        # hourly already ran its 11:00 window but NOT 12:00
        "hourly_drop": _dtime("2026-06-25T11:00:00"),
    }
    due = scheduler.due_jobs(SCHEDULES, now, last_run)
    # noon daily fires, and the hourly :00 fires again at 12:00
    assert set(due) == {"noon_chain", "hourly_drop"}


def test_last_run_dedup_prevents_refire_same_window():
    now = _dtime("2026-06-25T12:30:00")
    # everything serviced for its 12:00 (or last) window
    last_run = {
        "morning_tick": _dtime("2026-06-25T09:00:00"),
        "noon_chain": _dtime("2026-06-25T12:00:00"),
        "hourly_drop": _dtime("2026-06-25T12:00:00"),
    }
    assert scheduler.due_jobs(SCHEDULES, now, last_run) == []
    # advance to 13:00 -> only the hourly should reawaken
    later = _dtime("2026-06-25T13:00:10")
    assert scheduler.due_jobs(SCHEDULES, later, last_run) == ["hourly_drop"]


def test_run_then_record_then_no_refire():
    """End-to-end of the dedup mechanism: fire, record the fire instant via
    mark_run, and the same now no longer re-selects the job."""
    now = _dtime("2026-06-25T09:00:45")
    last_run: dict[str, dt.datetime] = {}
    due = scheduler.due_jobs(SCHEDULES, now, last_run)
    assert "morning_tick" in due
    # caller records the FIRE instant (prev_fire), not `now`
    for jid in due:
        job = next(s for s in SCHEDULES if s["id"] == jid)
        last_run = scheduler.mark_run(last_run, jid, job["cron"], now)
    # same instant, nothing re-fires
    assert scheduler.due_jobs(SCHEDULES, now, last_run) == []
    # the recorded stamp is the fire time, not the (later) now
    assert last_run["morning_tick"] == _dtime("2026-06-25T09:00:00")


def test_missed_window_still_fires_once_when_polled_late():
    """If the poller was down across a fire and runs late, the job is due once
    (catch-up), not skipped — last_run < prev_fire still holds."""
    now = _dtime("2026-06-25T11:45:00")  # poller wakes at 11:45
    last_run = {
        "morning_tick": _dtime("2026-06-25T09:00:00"),
        "noon_chain": _dtime("2026-06-24T12:00:00"),  # yesterday
        "hourly_drop": _dtime("2026-06-25T09:00:00"),  # missed 10:00 & 11:00
    }
    due = scheduler.due_jobs(SCHEDULES, now, last_run)
    # hourly is overdue (last fire was 11:00 > last_run 09:00); noon not yet
    assert set(due) == {"hourly_drop"}
    assert "noon_chain" not in due


# ---------------------------------------------------------------------------
# Registry loading from schedules.json
# ---------------------------------------------------------------------------

def test_load_schedules_from_json(tmp_path):
    p = tmp_path / "schedules.json"
    p.write_text(json.dumps(SCHEDULES), encoding="utf-8")
    loaded = scheduler.load_schedules(str(p))
    assert [s["id"] for s in loaded] == ["morning_tick", "noon_chain", "hourly_drop"]
    # a due query against the loaded set behaves identically to the in-memory set
    now = _dtime("2026-06-25T09:00:30")
    last_run = {"noon_chain": _dtime("2026-06-24T12:00:00")}
    assert set(scheduler.due_jobs(loaded, now, last_run)) == {"morning_tick", "hourly_drop"}


def test_load_schedules_missing_file_returns_empty():
    assert scheduler.load_schedules(os.path.join(_TMP, "nope.json")) == []


def test_invalid_cron_is_rejected_at_load():
    bad = [{"id": "broken", "cron": "not a cron", "action": {"kind": "tick"}}]
    with pytest.raises(ValueError):
        scheduler.validate_schedules(bad)


def test_unknown_action_kind_is_rejected_at_load():
    bad = [{"id": "x", "cron": "0 9 * * *", "action": {"kind": "explode"}}]
    with pytest.raises(ValueError):
        scheduler.validate_schedules(bad)


def teardown_module(module):  # noqa: ARG001
    shutil.rmtree(_TMP, ignore_errors=True)
