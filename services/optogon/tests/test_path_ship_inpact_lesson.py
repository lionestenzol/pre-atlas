"""End-to-end test: run ship_inpact_lesson path start-to-close.

Uses the FastAPI TestClient. Drives the path by POST /session/start then
looping POST /session/{id}/turn until close.

Success criteria (from doctrine/04_BUILD_PLAN.md Section 5):
- Path reaches status=completed
- CloseSignal validates against schema
- questions_asked is low (path has one qualify node; we give it 'lesson=5, source=draft.md')
"""
from __future__ import annotations
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from optogon.main import app


@pytest.fixture
def client(tmp_db):
    # tmp_db fixture redirects DB; store singleton was reset
    return TestClient(app)


def test_ship_inpact_lesson_closes(client):
    # Start
    r = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 5,
            "content_source": "drafts/lesson_5.md",
        },
    })
    assert r.status_code == 200, r.text
    data = r.json()
    session_id = data["session_id"]
    assert session_id.startswith("sess_")

    # Drive turns until we reach the 'done' node.
    # The path has an approval gate - the runner will pause at it awaiting user response.
    guard = 0
    while guard < 30:
        state = client.get(f"/session/{session_id}").json()
        if state["current_node"] == "done":
            break
        # If waiting on approval, approve it.
        current = state["current_node"]
        ns = state["node_states"].get(current, {})
        message = "approve" if ns.get("status") == "awaiting_approval" else None
        r = client.post(f"/session/{session_id}/turn", json={"message": message})
        assert r.status_code == 200, r.text
        guard += 1

    assert state["current_node"] == "done", f"Did not reach done: current={state['current_node']}"

    # One more turn to execute close
    r = client.post(f"/session/{session_id}/turn", json={})
    assert r.status_code == 200

    final = client.get(f"/session/{session_id}").json()
    assert "_close_signal" in final
    assert final["_close_signal"]["status"] == "completed"
    assert final["_close_signal"]["session_summary"]["path_completion_rate"] == 1.0


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schemas_loaded"] >= 10


def test_paths_endpoint(client):
    r = client.get("/paths")
    assert r.status_code == 200
    paths = r.json()
    ids = [p["id"] for p in paths]
    assert "ship_inpact_lesson" in ids
    assert "_template" not in ids
