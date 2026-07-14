"""Brick 2 acceptance: the daemon makes DropList a self-advancing entity.

Clock-driven (DROPLIST_NOW per day) and HTTP-free — imports droplist.daemon /
watcher / graph_engine directly, never uvicorn or requests. Mirrors
test_persist.py:16-23 for the tempdir + DROPLIST_NOW _set_day harness.

Proves, against the real engine:
  - materialization: N days -> N DAG-REC- dags (per-day recurrence)
  - advancement: a materialized recurring node moves OFF 'ready' via a tick,
    with no /api/drop call (the live-entity claim)
  - stale flagging: an aged node surfaces in the tick report's 'stale' list and
    a 'watch_tick' audit record is written
  - escalation: a failed node surfaces in the tick report's 'escalations' list
  - DROPLIST_DAEMON gating: the server startup hook does NOT spawn a thread when
    the env is unset, and DOES when ==1
  - --once CLI: daemon.main(['--once']) returns 0
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import threading

import pytest

# Each test gets its own tempdir DROPLIST_DATA so runs never cross-contaminate.
# DROPLIST_DATA is read at module import in storage.py (storage.py:14), so we
# set it via the fixture and reach DATA_DIR through storage at call time (the
# functions under test re-read storage.DATA_DIR each call).


@pytest.fixture()
def data_dir(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="droplist_daemon_")
    monkeypatch.setenv("DROPLIST_DATA", tmp)
    # storage.DATA_DIR was bound at import; repoint it at the fresh tempdir.
    from droplist import storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp, raising=True)
    yield tmp
    monkeypatch.delenv("DROPLIST_NOW", raising=False)
    shutil.rmtree(tmp, ignore_errors=True)


def _set_day(monkeypatch, d: dt.date, hour: int = 8) -> None:
    """Template from test_persist.py:22-23 — pin the controllable clock."""
    monkeypatch.setenv("DROPLIST_NOW", f"{d.isoformat()}T{hour:02d}:00:00Z")


def _dags_dir(data_dir: str) -> str:
    return os.path.join(data_dir, "dags")


def _rec_dag_ids(data_dir: str) -> list[str]:
    d = _dags_dir(data_dir)
    if not os.path.isdir(d):
        return []
    return [fn[:-5] for fn in os.listdir(d)
            if fn.startswith("DAG-REC-") and fn.endswith(".json")]


def test_materialize_and_advance(data_dir, monkeypatch):
    """N=3 days -> exactly 3 DAG-REC- dags (materialize proof), and the latest
    recurring node has moved OFF 'ready' after the tick (advance proof)."""
    from droplist import daemon, state, storage

    base = dt.date(2026, 6, 1)
    _set_day(monkeypatch, base)
    state.add_recurring(
        "Check rabbit water", "animal_property", "daily", "morning",
        entity_refs=["ANIMAL-RABBITS"],
        done_condition="water logged for each cage")

    for i in range(3):
        _set_day(monkeypatch, base + dt.timedelta(days=i))
        daemon._run_once()

    rec_ids = _rec_dag_ids(data_dir)
    assert len(rec_ids) == 3, f"expected 3 per-day DAG-REC- dags, got {rec_ids}"

    # advance proof: load every recurring dag; its single node must not be a
    # fresh 'ready' stalemate anymore — the tick dispatched it.
    for rid in rec_ids:
        dag = storage.load_dag(rid)
        assert dag is not None
        statuses = [n["status"] for n in dag["nodes"]]
        assert "ready" not in statuses, (
            f"{rid} node still 'ready' — advance_dag did not dispatch it: {statuses}")
        # the recurring node is an ops/field_check reasoning node -> marked done
        assert dag["nodes"][0]["status"] == "done", dag["nodes"][0]["status"]
        assert dag["status"] in ("complete", "stalled", "needs_human", "failed")


def test_stale_flagging(data_dir, monkeypatch):
    """An aged ready/waiting node surfaces in report['stale'] and a 'watch_tick'
    record lands in dag_events.jsonl."""
    from droplist import daemon, graph_engine, storage

    base = dt.date(2026, 6, 1)
    # Build a DAG with a human node (N2) that stays 'blocked' and other nodes;
    # to get a node that stays ready/waiting and ages, use a DAG whose loop
    # leaves a waiting/ready node. The animal_property DAG leaves N2 (human ->
    # blocked) and others done; instead force a stale node directly.
    _set_day(monkeypatch, base, hour=8)
    graph_engine.run_graph(
        "The doe is limping and not eating, hiding in the corner.")

    # find a stored dag and force one node back to 'ready' WITHOUT touching
    # updated_at, then age the clock past its stale_after_hours.
    rid = sorted(os.listdir(_dags_dir(data_dir)))[0][:-5]
    dag = storage.load_dag(rid)
    target = dag["nodes"][0]
    target["status"] = "ready"
    # default stale_after_hours is 24 (graph_engine.py enrich); set explicitly.
    target["stale_after_hours"] = 24
    dag["status"] = "running"
    storage.save_dag(dag)

    # advance the clock well past 24h after updated_at (which is base 08:00).
    _set_day(monkeypatch, base + dt.timedelta(days=3), hour=8)
    report = daemon._run_once()

    stale_node_ids = {s["node"] for s in report["stale"]}
    assert target["id"] in stale_node_ids, (
        f"expected {target['id']} in stale {report['stale']}")

    events = []
    with open(os.path.join(data_dir, "dag_events.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    assert any(e.get("event") == "watch_tick" for e in events), \
        "no 'watch_tick' audit record in dag_events.jsonl"


def test_escalation(data_dir, monkeypatch):
    """A node forced to status 'failed' surfaces in report['escalations']."""
    from droplist import daemon, graph_engine, storage

    base = dt.date(2026, 6, 1)
    _set_day(monkeypatch, base)
    graph_engine.run_graph(
        "The doe is limping and not eating, hiding in the corner.")

    rid = sorted(os.listdir(_dags_dir(data_dir)))[0][:-5]
    dag = storage.load_dag(rid)
    dag["nodes"][0]["status"] = "failed"
    dag["status"] = "failed"
    storage.save_dag(dag)

    report = daemon._run_once()
    assert report["escalations"], f"expected non-empty escalations, got {report}"


def test_once_cli_returns_zero(data_dir, monkeypatch):
    """`daemon.main(['--once'])` runs exactly one tick and exits 0."""
    from droplist import daemon

    _set_day(monkeypatch, dt.date(2026, 6, 1))
    rc = daemon.main(["--once"])
    assert rc == 0


def test_daemon_skips_autopilot_false_plan(data_dir, monkeypatch):
    """Per-plan autopilot (Bruke 2026-06-25): a hand-authored plan with
    `autopilot: false` is NOT advanced by the daemon even though it has a ready
    node — the human marks it off. An identical plan without the flag (default
    True) IS advanced, proving the gate is opt-out, not a behavior change."""
    from droplist import daemon, storage

    def _plan(dag_id, autopilot):
        d = {"dag_id": dag_id, "source_drop": "drop_" + dag_id, "domain": "build_product",
             "type": "task", "goal": "g", "status": "running", "created_at": "2026-06-01T00:00:00Z",
             "nodes": [{"id": "N1", "status": "ready", "type": "field_check", "agent": "ops",
                        "tool_type": "", "title": "step", "done_condition": "", "depends_on": [],
                        "result": None, "evidence": [], "retry_count": 0, "max_retries": 2}],
             "entity_refs": [], "links": []}
        if autopilot is not None:
            d["autopilot"] = autopilot
        storage.save_dag(d)

    _set_day(monkeypatch, dt.date(2026, 6, 25))
    _plan("DAG-MANUAL", autopilot=False)
    _plan("DAG-AUTO", autopilot=None)  # no flag → default True

    daemon._run_once()

    assert storage.load_dag("DAG-MANUAL")["nodes"][0]["status"] == "ready", \
        "daemon auto-ran a plan marked autopilot:false"
    assert storage.load_dag("DAG-AUTO")["nodes"][0]["status"] == "done", \
        "daemon failed to advance a default (autopilot) plan"


def test_daemon_fires_due_schedule_drop_and_dedups(data_dir, monkeypatch):
    """Brick 3 wiring (§D gap #1): a due schedules.json 'drop' entry fires via
    _run_once — creating a packet — and does NOT re-fire within the same cron
    window. Proves scheduler.load_schedules/due_jobs/mark_run now have a live
    consumer (were tested-but-inert)."""
    from droplist import daemon, storage

    schedules = [{
        "id": "weekly_review",
        "cron": "0 8 * * *",
        "action": {"kind": "drop",
                   "raw": "Scheduled reminder: review the backlog and prune stale work"},
    }]
    with open(os.path.join(data_dir, "schedules.json"), "w", encoding="utf-8") as f:
        json.dump(schedules, f)
    _set_day(monkeypatch, dt.date(2026, 6, 25), hour=8)

    before = len(storage.read_all(storage.PACKETS))
    rep1 = daemon._run_once()
    after = len(storage.read_all(storage.PACKETS))

    assert after > before, f"scheduled drop created no packet: {before}->{after}"
    assert any(s["id"] == "weekly_review" for s in rep1["scheduled_fired"]), \
        rep1["scheduled_fired"]
    runs = storage.read_all(storage.SCHEDULE_RUNS)
    assert any(r["schedule_id"] == "weekly_review" for r in runs)

    # same cron window -> no re-fire (dedup via mark_run / schedule_runs.jsonl)
    rep2 = daemon._run_once()
    assert rep2["scheduled_fired"] == [], rep2["scheduled_fired"]
    assert len(storage.read_all(storage.PACKETS)) == after, \
        "schedule re-fired within the same cron window"


def test_daemon_gating_unset(data_dir, monkeypatch):
    """With DROPLIST_DAEMON unset, the startup hook does NOT spawn a thread."""
    monkeypatch.delenv("DROPLIST_DAEMON", raising=False)
    from droplist import server
    server._daemon_thread = None  # reset module sentinel for an isolated check
    server._maybe_start_daemon()
    assert server._daemon_thread is None, "thread spawned despite DROPLIST_DAEMON unset"


def test_daemon_gating_enabled(data_dir, monkeypatch):
    """With DROPLIST_DAEMON=1, the startup hook spawns a live daemon thread.

    The loop body is stubbed with a blocking no-op so this test isolates the
    SERVER's spawn-gating logic (the real _run_once advance/tick behavior is
    proved by the materialize/stale/escalation tests above). Stubbing also
    keeps the spawned thread from racing the tempdir teardown. The thread is a
    daemon so it never blocks interpreter exit.
    """
    monkeypatch.setenv("DROPLIST_DAEMON", "1")
    from droplist import daemon, server

    started = threading.Event()
    release = threading.Event()

    def _stub_loop(interval: float = 0.0) -> None:
        started.set()
        release.wait(timeout=10)  # park here, alive, until the test releases it

    monkeypatch.setattr(daemon, "run_loop", _stub_loop, raising=True)
    server._daemon_thread = None
    try:
        server._maybe_start_daemon()
        assert server._daemon_thread is not None, "thread not spawned with DROPLIST_DAEMON=1"
        assert server._daemon_thread.daemon is True
        assert started.wait(timeout=5), "daemon thread never entered the loop"
        assert server._daemon_thread.is_alive()
    finally:
        release.set()
        if server._daemon_thread is not None:
            server._daemon_thread.join(timeout=5)
        server._daemon_thread = None


# --- DN0001 01_spine/01: schedule dispatch chain_id/dag_id fix -------------
# The bug: a `run_chain` schedule authored with `dag_id` (an older convention)
# was silently swallowed forever, because `_dispatch_schedule` only ever read
# `chain_id`. Fixed 2026-07-07 (droplist/daemon.py:85-98): `chain_id` is
# canonical; `dag_id` is accepted as a deprecated fallback and flagged.


def _write_chain(data_dir: str, chain_id: str = "test_chain") -> str:
    """Minimal valid chain per validate_chain (chain_runner.py); written to its
    own tempdir so DROPLIST_CHAINS_DIR can point at just this fixture."""
    chains_dir = os.path.join(data_dir, "chains")
    os.makedirs(chains_dir, exist_ok=True)
    chain = {
        "id": chain_id,
        "title": "Test chain",
        "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [{
            "prompt": "test prompt",
            "target_query": {"status": "running"},
            "expect": "non_empty",
        }],
        "on_report": {"action": "drop", "params": {"title_prefix": "Test"}},
    }
    with open(os.path.join(chains_dir, f"{chain_id}.json"), "w", encoding="utf-8") as f:
        json.dump(chain, f)
    return chains_dir


def test_dispatch_schedule_legacy_dag_id_key_still_dispatches(data_dir, monkeypatch):
    """A schedule authored with the legacy `dag_id` key still resolves the
    chain (not `chain_not_found`), and the result flags the fallback."""
    from droplist import daemon

    chains_dir = _write_chain(data_dir, "legacy_target")
    monkeypatch.setenv("DROPLIST_CHAINS_DIR", chains_dir)

    job = {"id": "legacy_sched", "action": {"kind": "run_chain", "dag_id": "legacy_target"}}
    result = daemon._dispatch_schedule(job, dt.datetime(2026, 7, 8, 9, 0, 0))

    assert result["chain"] == "legacy_target"
    assert result.get("reason") != "chain_not_found"
    assert result["deprecated_key"] == "dag_id"


def test_dispatch_schedule_chain_id_key_no_deprecation_flag(data_dir, monkeypatch):
    """The canonical `chain_id` key dispatches with no deprecation flag."""
    from droplist import daemon

    chains_dir = _write_chain(data_dir, "canonical_target")
    monkeypatch.setenv("DROPLIST_CHAINS_DIR", chains_dir)

    job = {"id": "canon_sched", "action": {"kind": "run_chain", "chain_id": "canonical_target"}}
    result = daemon._dispatch_schedule(job, dt.datetime(2026, 7, 8, 9, 0, 0))

    assert result["chain"] == "canonical_target"
    assert "deprecated_key" not in result


def test_dispatch_schedule_nonexistent_chain_warns_and_reports_not_found(data_dir, monkeypatch):
    """A `run_chain` schedule naming a chain that doesn't exist returns
    fired:false / reason:chain_not_found (fail-loud, never crash) AND leaves a
    warning trace in run_log.jsonl."""
    from droplist import daemon, storage

    chains_dir = _write_chain(data_dir, "real_chain")  # some chain exists, just not the one asked for
    monkeypatch.setenv("DROPLIST_CHAINS_DIR", chains_dir)

    job = {"id": "typo_sched", "action": {"kind": "run_chain", "chain_id": "does_not_exist"}}
    result = daemon._dispatch_schedule(job, dt.datetime(2026, 7, 8, 9, 0, 0))

    assert result["fired"] is False
    assert result["reason"] == "chain_not_found"

    runs = list(storage.read_all(storage.RUN_LOG))
    warnings = [r for r in runs if r.get("status") == "warning"
                and "chain_not_found" in (r.get("result_summary") or "")]
    assert warnings, "expected a warning run_log entry for the unresolved chain"
