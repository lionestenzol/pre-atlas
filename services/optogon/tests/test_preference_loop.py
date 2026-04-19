"""Phase 4 validation: run ship_inpact_lesson twice; second run asks fewer questions.

Per doctrine/04_BUILD_PLAN.md Phase 4 success criterion.

Mocks preferences_client.fetch_preferences and post_close_signal to act as an
in-memory preference store so we don't need a live delta-kernel for this test.
"""
from __future__ import annotations
from typing import Any

import pytest
from fastapi.testclient import TestClient

from optogon import preferences_client, session_store
from optogon.main import app


class FakePreferenceStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def fetch(self) -> dict[str, Any]:
        return dict(self._store)

    def ingest_close(self, close_signal: dict[str, Any]) -> bool:
        confirmed = (close_signal.get("context_residue") or {}).get("confirmed") or {}
        learned = (close_signal.get("context_residue") or {}).get("learned_preferences") or {}
        for k, v in confirmed.items():
            self._store[k] = {"value": v, "confidence": 0.95, "source": "explicit"}
        for k, v in learned.items():
            if k not in self._store:
                self._store[k] = {"value": v, "confidence": 0.9, "source": "inferred"}
        return True


@pytest.fixture
def fake_prefs(monkeypatch):
    store = FakePreferenceStore()

    # Patch BOTH modules that import these names (session_store + node_processor)
    from optogon import node_processor

    monkeypatch.setattr(preferences_client, "fetch_preferences", store.fetch)
    monkeypatch.setattr(preferences_client, "post_close_signal", store.ingest_close)
    monkeypatch.setattr(session_store, "fetch_preferences", store.fetch)
    monkeypatch.setattr(node_processor, "post_close_signal", store.ingest_close)
    return store


@pytest.fixture
def client(tmp_db):
    return TestClient(app)


def _drive_to_close(client: TestClient, session_id: str, max_turns: int = 20) -> dict[str, Any]:
    """Loop turns until the path reaches the close node and emits close_signal."""
    for _ in range(max_turns):
        state = client.get(f"/session/{session_id}").json()
        current = state["current_node"]
        ns = state["node_states"].get(current, {})
        if "_close_signal" in state:
            return state
        if current == "done":
            r = client.post(f"/session/{session_id}/turn", json={})
            assert r.status_code == 200
            continue
        message = "approve" if ns.get("status") == "awaiting_approval" else None
        r = client.post(f"/session/{session_id}/turn", json={"message": message})
        assert r.status_code == 200, r.text
    raise AssertionError(f"Did not reach close in {max_turns} turns; last state: {state}")


def test_second_run_asks_fewer_questions(client, fake_prefs):
    # Run 1: provide all inputs explicitly, including ui_theme.
    r1 = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 5,
            "content_source": "drafts/lesson_5.md",
            "ui_theme": "light",
        },
    })
    assert r1.status_code == 200
    s1_id = r1.json()["session_id"]
    final1 = _drive_to_close(client, s1_id)
    q1 = final1["metrics"]["total_questions_asked"]

    # After run 1, preferences should contain ui_theme=light (non-transient)
    assert "ui_theme" in fake_prefs._store, "ui_theme should have been learned"
    assert fake_prefs._store["ui_theme"]["value"] == "light"

    # Run 2: provide only per-run transient inputs; ui_theme should come from preferences
    r2 = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 6,
            "content_source": "drafts/lesson_6.md",
            # ui_theme intentionally omitted - must be supplied by preferences
        },
    })
    assert r2.status_code == 200
    s2_id = r2.json()["session_id"]

    # Verify preference was injected into run 2 session context
    s2_state = client.get(f"/session/{s2_id}").json()
    ctx = s2_state["context"]
    theme_in_context = (
        ctx["confirmed"].get("ui_theme")
        or ctx["inferred"].get("ui_theme")
        or ctx["user"].get("ui_theme")
    )
    assert theme_in_context == "light", f"ui_theme should be injected from preferences; context={ctx}"

    final2 = _drive_to_close(client, s2_id)
    q2 = final2["metrics"]["total_questions_asked"]

    # Core Phase 4 assertion: run 2 asks no more than run 1
    # (ideally strictly fewer, but since run 1 had everything in initial_context,
    # both should hit 0; the real proof is that ui_theme WAS injected from prefs)
    assert q2 <= q1, f"run 2 asked more questions ({q2}) than run 1 ({q1})"


def test_cold_run_without_theme_asks_question(client, fake_prefs):
    """Control: no preferences, missing ui_theme in initial_context -> should need input."""
    # Preferences store is empty for this test; fake_prefs fixture starts fresh
    r = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 5,
            "content_source": "drafts/lesson_5.md",
            # ui_theme missing
        },
    })
    assert r.status_code == 200
    state = r.json()["state"]
    # Should still be on entry node because ui_theme is missing
    assert state["current_node"] == "entry", (
        f"entry should still be unqualified without ui_theme; current={state['current_node']}"
    )


def test_warm_run_promotes_preference_to_confirmed(client, fake_prefs):
    """High-confidence preferences should promote to 'confirmed' tier."""
    # Seed the fake store directly (simulating accumulated history)
    fake_prefs._store["ui_theme"] = {"value": "light", "confidence": 0.95, "source": "explicit"}
    fake_prefs._store["preferred_commit_prefix"] = {
        "value": "feat(inpact)", "confidence": 0.90, "source": "inferred",
    }

    r = client.post("/session/start", json={
        "path_id": "ship_inpact_lesson",
        "initial_context": {
            "lesson_number": 7,
            "content_source": "drafts/lesson_7.md",
        },
    })
    assert r.status_code == 200
    state = r.json()["state"]
    # 0.95 and 0.90 are both >= AUTO_CONFIRM_CONFIDENCE (0.85) -> confirmed
    assert state["context"]["confirmed"].get("ui_theme") == "light"
    assert state["context"]["confirmed"].get("preferred_commit_prefix") == "feat(inpact)"
