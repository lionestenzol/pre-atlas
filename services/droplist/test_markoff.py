"""PKT-011 acceptance: Mark-off + Checklist (Brick 1 of the lifecycle spine).

Proves the write side of "plan -> advance by hand":

  - GET  /api/dag/{id}/checklist           : the plan as a flat, ordered list
  - POST /api/dag/{id}/node/{nid}/complete : check a task off, wake its deps
  - POST /api/dag/{id}/node/{nid}/reopen   : (stretch) put a done node back

The completion path reuses dag_update.apply_review (dag_update.py:20) — these
tests assert the OBSERVABLE contract (status flips, dependents wake, dag goes
complete, idempotency, 404/409 guards), not the internals.

Pytest-collectable. Isolates DROPLIST_DATA to a temp dir before importing the
package, mirroring test_atlas_retry.py / test_server.py. Run from project root:

    python -m pytest test_markoff.py -q
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

# Stable clock + isolated data dir BEFORE importing the package.
os.environ.setdefault("DROPLIST_NOW", "2026-06-25T12:00:00Z")
os.environ.pop("DROPLIST_ATLAS_SIGNALS_URL", None)  # never POST anywhere
_TMP = tempfile.mkdtemp(prefix="pkt11_markoff_")
os.environ["DROPLIST_DATA"] = _TMP

from fastapi.testclient import TestClient  # noqa: E402

from droplist import storage  # noqa: E402
from droplist.server import app  # noqa: E402

client = TestClient(app)


def _node(nid: str, status: str, depends_on: list[str] | None = None,
          title: str = "node", done_condition: str = "") -> dict:
    return {
        "id": nid, "status": status, "agent": "ops", "tool_type": "",
        "title": title, "done_condition": done_condition,
        "depends_on": depends_on or [], "result": None, "evidence": [],
        "retry_count": 0, "max_retries": 2,
    }


def _chain_dag(dag_id: str) -> dict:
    """A 3-step chain: N1 (ready) -> N2 (waiting on N1) -> N3 (waiting on N2).

    Mirrors the shape graph_engine produces for a multi-step plan: the head is
    ready, the rest wait on their predecessor.
    """
    dag = {
        "dag_id": dag_id,
        "source_drop": "drop_markoff",
        "domain": "build_product",
        "type": "task",
        "goal": "Wire the mark-off endpoint end to end",
        "status": "running",
        "nodes": [
            _node("N1", "ready", title="scope the change",
                  done_condition="endpoints listed"),
            _node("N2", "waiting", depends_on=["N1"], title="implement it",
                  done_condition="endpoints respond"),
            _node("N3", "waiting", depends_on=["N2"], title="prove it",
                  done_condition="tests green"),
        ],
        "entity_refs": [],
        "links": [],
    }
    storage.save_dag(dag)
    return dag


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

def test_checklist_shape_and_blocked_by():
    _chain_dag("DAG-CHK01")
    r = client.get("/api/dag/DAG-CHK01/checklist")
    assert r.status_code == 200
    body = r.json()
    assert body["dag_id"] == "DAG-CHK01"
    assert body["goal"] == "Wire the mark-off endpoint end to end"
    tasks = body["tasks"]
    assert len(tasks) == 3
    # first is ready and unblocked; later ones wait, blocked_by populated
    assert tasks[0]["status"] == "ready"
    assert tasks[0]["blocked_by"] == []
    assert tasks[0]["done_condition"] == "endpoints listed"
    assert tasks[1]["status"] == "waiting"
    assert tasks[1]["blocked_by"] == ["N1"]
    assert tasks[2]["status"] == "waiting"
    assert tasks[2]["blocked_by"] == ["N2"]


def test_checklist_missing_dag_404():
    r = client.get("/api/dag/DAG-NOPE/checklist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Complete — guards
# ---------------------------------------------------------------------------

def test_complete_missing_dag_404():
    r = client.post("/api/dag/DAG-NOPE/node/N1/complete", json={})
    assert r.status_code == 404


def test_complete_missing_node_404():
    _chain_dag("DAG-CMP404")
    r = client.post("/api/dag/DAG-CMP404/node/NOPE/complete", json={})
    assert r.status_code == 404


def test_complete_with_open_deps_409():
    _chain_dag("DAG-CMP409")
    # N2 depends on N1, which is still open
    r = client.post("/api/dag/DAG-CMP409/node/N2/complete", json={})
    assert r.status_code == 409
    assert "N1" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Complete — the happy path: advance in dependency order, deps wake up
# ---------------------------------------------------------------------------

def test_complete_in_order_wakes_dependents_and_finishes():
    _chain_dag("DAG-FLOW")

    # complete N1 -> N2 wakes to ready, dag still running
    r1 = client.post("/api/dag/DAG-FLOW/node/N1/complete",
                     json={"note": "scoped", "evidence": ["server.py:148"]})
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["dag_status"] == "running"
    assert "N2" in b1["ready_now"]
    assert "N3" not in b1["ready_now"]

    # complete N2 -> N3 wakes
    r2 = client.post("/api/dag/DAG-FLOW/node/N2/complete", json={})
    assert r2.status_code == 200
    b2 = r2.json()
    assert "N3" in b2["ready_now"]
    assert b2["dag_status"] == "running"

    # complete N3 -> dag complete, nothing ready
    r3 = client.post("/api/dag/DAG-FLOW/node/N3/complete", json={})
    assert r3.status_code == 200
    b3 = r3.json()
    assert b3["dag_status"] == "complete"
    assert b3["ready_now"] == []

    # the result/evidence we sent landed on the node
    dag = storage.load_dag("DAG-FLOW")
    n1 = next(n for n in dag["nodes"] if n["id"] == "N1")
    assert n1["status"] == "done"
    assert n1["result"]["by"] == "human"
    assert n1["result"]["evidence"] == ["server.py:148"]

    # and the audit event was appended
    events = storage.read_all(storage.DAG_EVENTS)
    completed = [e for e in events
                 if e.get("event") == "node_completed" and e.get("dag_id") == "DAG-FLOW"]
    assert len(completed) == 3


def test_complete_is_idempotent():
    _chain_dag("DAG-IDEMP")
    first = client.post("/api/dag/DAG-IDEMP/node/N1/complete", json={})
    assert first.status_code == 200
    assert first.json().get("already_done") in (None, False)

    again = client.post("/api/dag/DAG-IDEMP/node/N1/complete", json={})
    assert again.status_code == 200
    body = again.json()
    assert body["already_done"] is True
    assert body["updates"] == []


def test_brief_shows_no_ready_after_completion():
    _chain_dag("DAG-BRIEF")
    for nid in ("N1", "N2", "N3"):
        assert client.post(f"/api/dag/DAG-BRIEF/node/{nid}/complete",
                           json={}).status_code == 200
    # /brief's ready list must not surface any node from a now-complete dag
    brief = client.get("/api/brief").json()
    ready_dags = {r.get("dag") for r in brief.get("ready", [])}
    assert "DAG-BRIEF" not in ready_dags


def test_complete_empty_body_ok():
    """A bare check-off with no JSON body still completes the node."""
    _chain_dag("DAG-NOBODY")
    r = client.post("/api/dag/DAG-NOBODY/node/N1/complete")
    assert r.status_code == 200
    assert r.json()["dag_status"] in ("running", "complete")


# ---------------------------------------------------------------------------
# Reopen (stretch)
# ---------------------------------------------------------------------------

def test_reopen_done_node_rewaits_dependents():
    _chain_dag("DAG-REOPEN")
    client.post("/api/dag/DAG-REOPEN/node/N1/complete", json={})  # N2 -> ready

    r = client.post("/api/dag/DAG-REOPEN/node/N1/reopen")
    assert r.status_code == 200
    assert r.json()["reopened"] is True

    dag = storage.load_dag("DAG-REOPEN")
    by_id = {n["id"]: n["status"] for n in dag["nodes"]}
    assert by_id["N1"] == "ready"
    assert by_id["N2"] == "waiting"  # dependent put back to sleep


def test_reopen_non_done_is_noop():
    _chain_dag("DAG-REOPEN-NOOP")
    r = client.post("/api/dag/DAG-REOPEN-NOOP/node/N1/reopen")  # N1 is ready, not done
    assert r.status_code == 200
    assert r.json()["reopened"] is False


def test_reopen_under_do_not_reopen_lock_is_409():
    """B6 (was untested per SMOKE_AND_DOD.md §D): a done node whose
    do_not_reopen_refs intersect the state lock cannot be reopened — 409, and
    the node stays done. Locks shipped/closed work against accidental reopen."""
    from droplist import state

    node = _node("N1", "done", title="shipped step")
    node["do_not_reopen_refs"] = ["ship-2026-lock"]
    dag = {
        "dag_id": "DAG-LOCK", "source_drop": "drop_lock", "domain": "build_product",
        "type": "task", "goal": "locked plan", "status": "complete",
        "nodes": [node], "entity_refs": [], "links": [],
    }
    storage.save_dag(dag)
    state.lock_ref("ship-2026-lock", reason="shipped — do not reopen")

    r = client.post("/api/dag/DAG-LOCK/node/N1/reopen")
    assert r.status_code == 409, r.text
    assert "ship-2026-lock" in r.text
    assert storage.load_dag("DAG-LOCK")["nodes"][0]["status"] == "done"


def teardown_module(module):  # noqa: ARG001
    shutil.rmtree(_TMP, ignore_errors=True)
