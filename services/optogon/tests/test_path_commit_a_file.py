"""End-to-end test: commit_a_file path runs with real side effects.

Uses a tmp git repo and monkeypatches REPO_ROOT so it doesn't touch
the actual Pre Atlas repo.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optogon.main import app


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    (path / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", ".gitkeep"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(path), check=True)


@pytest.fixture
def tmp_git_repo(tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    from optogon import action_handlers
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def client(tmp_db):
    return TestClient(app)


def _drive_to_close(client: TestClient, session_id: str, max_turns: int = 20) -> dict:
    for _ in range(max_turns):
        state = client.get(f"/session/{session_id}").json()
        current = state["current_node"]
        ns = state["node_states"].get(current, {})
        if state.get("_close_signal"):
            return state
        if current == "done":
            r = client.post(f"/session/{session_id}/turn", json={})
            assert r.status_code == 200
            continue
        message = "approve" if ns.get("status") == "awaiting_approval" else None
        r = client.post(f"/session/{session_id}/turn", json={"message": message})
        assert r.status_code == 200, r.text
    raise AssertionError(f"Did not reach close; last state: {state}")


def test_clean_file_commits(client, tmp_git_repo):
    """Happy path: clean file, approve, real commit lands."""
    (tmp_git_repo / "doc.md").write_text("# Heading\n\nPlain content, no fancy punctuation.\n", encoding="utf-8")

    r = client.post("/session/start", json={
        "path_id": "commit_a_file",
        "initial_context": {"file_path": "doc.md", "commit_message": "test: add doc"},
    })
    assert r.status_code == 200
    s_id = r.json()["session_id"]
    final = _drive_to_close(client, s_id)

    cs = final["_close_signal"]
    assert cs["status"] == "completed"

    # Verify a commit actually landed in the tmp repo
    log_out = subprocess.run(
        ["git", "log", "--oneline", "-2"],
        cwd=str(tmp_git_repo), capture_output=True, text=True, check=True,
    ).stdout
    assert "test: add doc" in log_out


def test_em_dash_file_routes_to_done_without_commit(client, tmp_git_repo):
    """Em-dash violation: gate routes to done without running commit."""
    (tmp_git_repo / "bad.md").write_text("This has an em dash \u2014 right here.\n", encoding="utf-8")

    r = client.post("/session/start", json={
        "path_id": "commit_a_file",
        "initial_context": {"file_path": "bad.md", "commit_message": "test: should not land"},
    })
    assert r.status_code == 200
    s_id = r.json()["session_id"]
    final = _drive_to_close(client, s_id)

    # Closed (path flowed to done) but no commit should have run
    log_out = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        cwd=str(tmp_git_repo), capture_output=True, text=True, check=True,
    ).stdout
    assert "test: should not land" not in log_out


def test_missing_file_short_circuits(client, tmp_git_repo):
    """Missing file: validate_file gate routes to done, no commit."""
    r = client.post("/session/start", json={
        "path_id": "commit_a_file",
        "initial_context": {"file_path": "does_not_exist.md", "commit_message": "test: nope"},
    })
    assert r.status_code == 200
    s_id = r.json()["session_id"]
    final = _drive_to_close(client, s_id)

    # Reaches done cleanly but no actual commit
    log_out = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        cwd=str(tmp_git_repo), capture_output=True, text=True, check=True,
    ).stdout
    assert "test: nope" not in log_out


def test_denied_approval_skips_commit(client, tmp_git_repo):
    """User denies at approve node: routes to done without commit."""
    (tmp_git_repo / "doc2.md").write_text("Clean content here.\n", encoding="utf-8")

    r = client.post("/session/start", json={
        "path_id": "commit_a_file",
        "initial_context": {"file_path": "doc2.md", "commit_message": "test: denied"},
    })
    assert r.status_code == 200
    s_id = r.json()["session_id"]

    # Drive to approval, deny
    for _ in range(15):
        state = client.get(f"/session/{s_id}").json()
        current = state["current_node"]
        ns = state["node_states"].get(current, {})
        if state.get("_close_signal"):
            break
        msg = None
        if ns.get("status") == "awaiting_approval":
            msg = "deny"
        elif current == "done":
            pass
        client.post(f"/session/{s_id}/turn", json={"message": msg})

    log_out = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        cwd=str(tmp_git_repo), capture_output=True, text=True, check=True,
    ).stdout
    assert "test: denied" not in log_out
