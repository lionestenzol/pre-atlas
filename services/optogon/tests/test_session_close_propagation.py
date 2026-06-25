"""Regression: a closed path propagates 'closed' to BOTH sinks.

Guards the latent bug (fixed 2026-06-25) where _handle_close set node-scoped
ns["closed_at"] + state["_close_signal"] but never the session-level
state["closed_at"], and store.close() was never called — so /session/run
relied on a _close_signal workaround and store.list_active() returned closed
sessions as active forever.

Runs keyless (no ANTHROPIC_API_KEY) per the composer's deterministic fallback.
"""
from __future__ import annotations
from datetime import datetime

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from optogon.main import app
from optogon.session_store import get_store


@pytest.fixture
def client(tmp_db):
    # tmp_db redirects DB_PATH and resets the store singleton.
    return TestClient(app)


def _drive_to_close(client) -> str:
    """Start ship_inpact_lesson and drive it turn-by-turn through its close node.

    /session/run intentionally halts at the approval node, so we drive manually
    and approve, mirroring tests/test_path_ship_inpact_lesson.py.
    """
    r = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 5,
            "content_source": "drafts/lesson_5.md",
            "ui_theme": "light",
        },
    })
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    guard = 0
    state = client.get(f"/session/{session_id}").json()
    while guard < 30 and state["current_node"] != "done":
        current = state["current_node"]
        ns = state["node_states"].get(current, {})
        message = "approve" if ns.get("status") == "awaiting_approval" else None
        r = client.post(f"/session/{session_id}/turn", json={"message": message})
        assert r.status_code == 200, r.text
        state = client.get(f"/session/{session_id}").json()
        guard += 1

    assert state["current_node"] == "done", f"never reached close node: {state['current_node']}"
    # One more turn executes the close node (_handle_close).
    r = client.post(f"/session/{session_id}/turn", json={})
    assert r.status_code == 200, r.text
    return session_id


def test_close_sets_session_level_closed_at(client):
    """Sink 1 (in-memory): top-level state['closed_at'] is set, not just ns['closed_at']."""
    session_id = _drive_to_close(client)
    final = client.get(f"/session/{session_id}").json()
    assert final.get("closed_at"), "session-level state['closed_at'] not set after close"
    # Must be ISO-8601 parseable.
    datetime.fromisoformat(final["closed_at"].replace("Z", "+00:00"))


def test_close_persists_to_sqlite_and_drops_from_active(client):
    """Sink 2 (persistent): SQLite closed_at column written; session leaves list_active()."""
    session_id = _drive_to_close(client)
    store = get_store()

    active_ids = [s["session_id"] for s in store.list_active()]
    assert session_id not in active_ids, "closed session still returned by list_active()"

    row = store._conn.execute(
        "SELECT closed_at FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    assert row is not None and row["closed_at"], "SQLite closed_at column not persisted on close"
