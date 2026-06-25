"""Brick 4 acceptance: the DAISY-CHAIN staged-prompt protocol.

Proves the headline capability: a chain whose trigger fires runs its prompt
steps (through the heuristic LLM fallback, NO api key), assembles a report,
appends it to the audit log, AND THEN executes a real on_report action that
CHANGES STATE.

The load-bearing assertion is report -> ACTION: it is NOT enough that a report
record was written. Each happy-path test asserts a real state change that did
NOT exist before run_chain:

  - action 'drop':          a follow-up packet now exists in the dropstore.
  - action 'complete_node': a target DAG node flipped ready -> done.
  - action 'emit_signal':   a Signal.v1 dict was produced and POSTed (the POST
                            is captured via a monkeypatched emitter; the proof
                            is the captured signal, not a network hit).

Clock-driven (DROPLIST_NOW) and HTTP-free. Mirrors the tempdir + controllable
clock harness of test_daemon.py:36-50 and the node/DAG fixtures of
test_markoff.py:41-76.

Run from project root:

    python -m pytest test_chains.py -q
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Harness: isolated DROPLIST_DATA + controllable clock, per test.
# Mirrors test_daemon.py:36-50 exactly (storage.DATA_DIR is bound at import,
# so we repoint it through monkeypatch each test).
# ---------------------------------------------------------------------------


@pytest.fixture()
def data_dir(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="droplist_chains_")
    monkeypatch.setenv("DROPLIST_DATA", tmp)
    from droplist import storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp, raising=True)
    yield tmp
    monkeypatch.delenv("DROPLIST_NOW", raising=False)
    shutil.rmtree(tmp, ignore_errors=True)


def _set_now(monkeypatch, when: dt.datetime) -> None:
    monkeypatch.setenv("DROPLIST_NOW", when.strftime("%Y-%m-%dT%H:%M:%SZ"))


# A Saturday 08:00 — the daily 0 8 * * * cron's most-recent fire is exactly here,
# so a never-run chain is due. Picked once so every test shares one firing time.
FIRE_AT = dt.datetime(2026, 6, 13, 8, 0, 0)


def _node(nid: str, status: str, depends_on: list[str] | None = None,
          title: str = "node", done_condition: str = "") -> dict:
    """Node fixture, shape per test_markoff.py:41-48 / dag_builder.py:48."""
    return {
        "id": nid, "status": status, "agent": "ops", "tool_type": "",
        "title": title, "done_condition": done_condition, "type": "field_check",
        "depends_on": depends_on or [], "result": None, "evidence": [],
        "result_refs": [], "inputs_required": [], "tool_action": "",
        "retry_count": 0, "max_retries": 2,
    }


def _seed_dag(dag_id: str, created_at: str, *, ready: bool = True) -> dict:
    """A running DAG with a head node, stamped with an explicit created_at so the
    'older_than_days' predicate is deterministic. Saved via storage.save_dag
    (storage.py:134)."""
    from droplist import storage
    head_status = "ready" if ready else "done"
    dag = {
        "dag_id": dag_id,
        "source_drop": "drop_seed_" + dag_id,
        "domain": "build_product",
        "type": "task",
        "goal": "Wire the chain runner end to end",
        "status": "running",
        "created_at": created_at,
        "updated_at": created_at,
        "nodes": [
            _node("N1", head_status, title="scope the change",
                  done_condition="endpoints listed"),
            _node("N2", "waiting", depends_on=["N1"], title="implement it"),
        ],
        "entity_refs": [],
        "links": [],
    }
    storage.save_dag(dag)
    return dag


# ---------------------------------------------------------------------------
# Trigger evaluation (cron via scheduler) — selection, not action.
# ---------------------------------------------------------------------------


def test_cron_chain_fires_when_due(data_dir, monkeypatch):
    from droplist import chain_runner

    chain = {
        "id": "c_due", "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [], "on_report": {"action": "emit_signal", "params": {}},
    }
    # 08:00 on the dot -> due (never ran).
    assert chain_runner.is_due(chain, FIRE_AT, last_run=None) is True
    # 07:59 -> the most-recent fire (yesterday 08:00) already <= last_run -> not due.
    yesterday_fire = dt.datetime(2026, 6, 12, 8, 0, 0)
    assert chain_runner.is_due(
        chain, dt.datetime(2026, 6, 13, 7, 59, 0), last_run=yesterday_fire
    ) is False


# ---------------------------------------------------------------------------
# Target selection — reuses the /api/dags filter logic (server.py:143-146)
# plus the chain-specific older_than_days / has_ready_node predicates.
# ---------------------------------------------------------------------------


def test_select_targets_matches_stale_ready_dag(data_dir, monkeypatch):
    from droplist import chain_runner

    _set_now(monkeypatch, FIRE_AT)
    # one stale ready DAG (created 5 days ago) and one fresh (created today).
    _seed_dag("DAG-STALE", (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _seed_dag("DAG-FRESH", FIRE_AT.strftime("%Y-%m-%dT%H:%M:%SZ"))

    q = {"status": "running", "older_than_days": 2, "has_ready_node": True}
    hits = chain_runner.select_targets(q, now=FIRE_AT)
    ids = {d["dag_id"] for d in hits}
    assert "DAG-STALE" in ids
    assert "DAG-FRESH" not in ids


# ---------------------------------------------------------------------------
# THE PROOF: report -> ACTION (action='drop').
# A follow-up packet that did NOT exist before run_chain now exists.
# ---------------------------------------------------------------------------


def test_run_chain_drop_action_creates_followup_drop(data_dir, monkeypatch):
    from droplist import chain_runner, dropstore, storage

    _set_now(monkeypatch, FIRE_AT)
    _seed_dag("DAG-STALE",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # BEFORE: count packets in the store (the dropstore is the drop authority,
    # dropstore.get_store / insert_if_new — intake.py:59-61).
    store = dropstore.get_store()
    packets_before = len(store.read_all())

    chain = {
        "id": "nudge", "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [{
            "prompt": "Draft a one-line nudge for this stale work.",
            "target_query": {"status": "running", "older_than_days": 2,
                             "has_ready_node": True},
            "expect": "non_empty",
        }],
        "on_report": {"action": "drop", "params": {"title_prefix": "Nudge"}},
    }

    result = chain_runner.run_chain(chain, FIRE_AT)

    # (a) a report record was written to chain_reports.jsonl
    reports = storage.read_all(chain_runner.CHAIN_REPORTS)
    assert len(reports) == 1
    rep = reports[0]
    assert rep["chain_id"] == "nudge"
    assert rep["fired"] is True
    assert rep["steps"], "report has no step records"
    assert rep["steps"][0]["targets"], "step matched no targets"

    # (b) THE LOAD-BEARING PROOF: a real action changed state — a follow-up drop
    # that did not exist before now exists in the store.
    packets_after = len(store.read_all())
    assert packets_after > packets_before, (
        f"no follow-up drop was created: before={packets_before} "
        f"after={packets_after}")
    assert result["actions_taken"], "run_chain reported no actions"
    assert result["actions_taken"][0]["action"] == "drop"
    assert result["actions_taken"][0]["status"] == "secured"


# ---------------------------------------------------------------------------
# report -> ACTION (action='complete_node'): a target node flips ready -> done.
# ---------------------------------------------------------------------------


def test_run_chain_complete_node_action_flips_node_done(data_dir, monkeypatch):
    from droplist import chain_runner, storage

    _set_now(monkeypatch, FIRE_AT)
    _seed_dag("DAG-DONE",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # BEFORE: N1 is ready, not done.
    before = storage.load_dag("DAG-DONE")
    n1_before = next(n for n in before["nodes"] if n["id"] == "N1")
    assert n1_before["status"] == "ready"

    chain = {
        "id": "auto_close", "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [{
            "prompt": "Verify the head node's done_condition is satisfied.",
            "target_query": {"status": "running", "older_than_days": 2,
                             "has_ready_node": True},
            "expect": "non_empty",
        }],
        "on_report": {"action": "complete_node", "params": {"node_id": "N1"}},
    }

    result = chain_runner.run_chain(chain, FIRE_AT)

    # report written
    reports = storage.read_all(chain_runner.CHAIN_REPORTS)
    assert len(reports) == 1

    # THE PROOF: N1 flipped ready -> done via dag_update.apply_review (dag_update.py:20),
    # AND its dependent N2 woke ready (the recursive wake).
    after = storage.load_dag("DAG-DONE")
    by_id = {n["id"]: n["status"] for n in after["nodes"]}
    assert by_id["N1"] == "done", f"N1 did not flip done: {by_id}"
    assert by_id["N2"] == "ready", f"dependent N2 did not wake: {by_id}"
    assert result["actions_taken"][0]["action"] == "complete_node"


# ---------------------------------------------------------------------------
# report -> ACTION (action='emit_signal'): a Signal.v1 is produced + emitted.
# The emit is captured (monkeypatched) so no network is touched; the proof is
# the captured, schema-valid signal.
# ---------------------------------------------------------------------------


def test_run_chain_emit_signal_action_emits_valid_signal(data_dir, monkeypatch):
    from droplist import atlas_signal, chain_runner, storage

    _set_now(monkeypatch, FIRE_AT)
    monkeypatch.setenv("DROPLIST_ATLAS_SIGNALS_URL", "http://127.0.0.1:3001/api/signals/ingest")
    _seed_dag("DAG-SIG",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    captured: list[dict] = []

    def _fake_emit(signal, url, timeout=10.0):
        captured.append({"signal": signal, "url": url})
        return {"ok": True}

    monkeypatch.setattr(atlas_signal, "emit_signal", _fake_emit, raising=True)

    chain = {
        "id": "signal_it", "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [{
            "prompt": "Summarize the stale DAG for downstream.",
            "target_query": {"status": "running", "older_than_days": 2,
                             "has_ready_node": True},
            "expect": "non_empty",
        }],
        "on_report": {"action": "emit_signal", "params": {}},
    }

    result = chain_runner.run_chain(chain, FIRE_AT)

    reports = storage.read_all(chain_runner.CHAIN_REPORTS)
    assert len(reports) == 1

    # THE PROOF: a real Signal.v1 was produced and handed to the emitter.
    assert captured, "emit_signal was never called"
    sig = captured[0]["signal"]
    assert atlas_signal.validate_signal(sig) == [], "emitted signal is not Signal.v1-valid"
    assert sig["source_layer"] == "droplist"
    assert result["actions_taken"][0]["action"] == "emit_signal"


# ---------------------------------------------------------------------------
# Not due: no report, no action (the negative — a chain that does not fire must
# change nothing).
# ---------------------------------------------------------------------------


def test_run_chain_not_due_is_noop(data_dir, monkeypatch):
    from droplist import chain_runner, storage

    _set_now(monkeypatch, dt.datetime(2026, 6, 13, 7, 0, 0))  # 07:00, before 08:00 cron
    _seed_dag("DAG-X",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    chain = {
        "id": "c_noop", "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [], "on_report": {"action": "emit_signal", "params": {}},
    }
    # last_run = today 08:00 is impossible (it's 07:00), so the most-recent fire
    # is yesterday 08:00; pass last_run=yesterday so it is NOT due.
    last = dt.datetime(2026, 6, 12, 8, 0, 0)
    result = chain_runner.run_chain(
        chain, dt.datetime(2026, 6, 13, 7, 0, 0), last_run=last)
    assert result["fired"] is False
    assert storage.read_all(chain_runner.CHAIN_REPORTS) == []


# ---------------------------------------------------------------------------
# condition trigger: a predicate over current DAG state (no cron).
# ---------------------------------------------------------------------------


def test_condition_trigger_fires_on_matching_state(data_dir, monkeypatch):
    from droplist import chain_runner

    _set_now(monkeypatch, FIRE_AT)
    _seed_dag("DAG-COND",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # 'condition' trigger: fire iff select_targets(expr) is non-empty.
    chain = {
        "id": "c_cond",
        "trigger": {"on": "condition",
                    "expr": {"status": "running", "older_than_days": 2,
                             "has_ready_node": True}},
        "steps": [{"prompt": "x",
                   "target_query": {"status": "running", "older_than_days": 2,
                                    "has_ready_node": True},
                   "expect": "non_empty"}],
        "on_report": {"action": "emit_signal", "params": {}},
    }
    assert chain_runner.is_due(chain, FIRE_AT, last_run=None) is True

    # and with no matching DAGs, the condition is false.
    _set_now(monkeypatch, FIRE_AT)
    chain_fresh = dict(chain)
    chain_fresh["trigger"] = {
        "on": "condition",
        "expr": {"status": "running", "older_than_days": 999, "has_ready_node": True},
    }
    assert chain_runner.is_due(chain_fresh, FIRE_AT, last_run=None) is False


# ---------------------------------------------------------------------------
# The shipped example chain loads and validates.
# ---------------------------------------------------------------------------


def test_example_chain_loads_and_validates(data_dir, monkeypatch):
    from droplist import chain_runner

    chains = chain_runner.load_chains()
    by_id = {c["id"]: c for c in chains}
    assert "daily_ready_nudge" in by_id, f"example chain missing; got {list(by_id)}"
    chain_runner.validate_chain(by_id["daily_ready_nudge"])  # raises on malformed


# ---------------------------------------------------------------------------
# Daemon wire: daemon._run_once runs due chains and their action lands.
# This proves the tick hook (daemon.py:_run_once) actually drives chains, not
# just that chain_runner does in isolation.
# ---------------------------------------------------------------------------


def test_daemon_tick_runs_chain_and_creates_drop(data_dir, monkeypatch):
    import json as _json

    from droplist import daemon, dropstore, storage

    # Isolated chains dir with one cron chain due at FIRE_AT.
    cdir = tempfile.mkdtemp(prefix="droplist_chains_dir_")
    monkeypatch.setenv("DROPLIST_CHAINS_DIR", cdir)
    chain = {
        "id": "daemon_nudge",
        "trigger": {"on": "cron", "expr": "0 8 * * *"},
        "steps": [{
            "prompt": "Draft a nudge for stale ready work.",
            "target_query": {"status": "running", "older_than_days": 2,
                             "has_ready_node": True},
            "expect": "non_empty",
        }],
        "on_report": {"action": "drop", "params": {"title_prefix": "Nudge"}},
    }
    with open(os.path.join(cdir, "daemon_nudge.json"), "w", encoding="utf-8") as f:
        _json.dump(chain, f)

    _set_now(monkeypatch, FIRE_AT)
    _seed_dag("DAG-STALE",
              (FIRE_AT - dt.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    store = dropstore.get_store()
    before = len(store.read_all())

    report = daemon._run_once()

    # the daemon report surfaces the chain firing
    assert report["chains_fired"], f"daemon did not fire any chain: {report}"
    # AND the chain's drop action landed a new packet (report -> action via daemon).
    after = len(store.read_all())
    assert after > before, f"daemon tick did not create the follow-up drop: {before}->{after}"

    shutil.rmtree(cdir, ignore_errors=True)
