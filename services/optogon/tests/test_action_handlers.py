"""Tests for real action handlers (read_content, scan_em_dashes, git_commit)."""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest

from optogon.action_handlers import (
    ActionError,
    read_content,
    scan_em_dashes,
    git_commit,
    get_handler,
)
from optogon.context import empty_context


def _state(file_path: str = "", commit_message: str = "") -> dict:
    ctx = empty_context()
    if file_path:
        ctx["confirmed"]["file_path"] = file_path
    if commit_message:
        ctx["confirmed"]["commit_message"] = commit_message
    return {
        "session_id": "sess_test",
        "context": ctx,
        "node_states": {},
        "action_log": [],
        "metrics": {
            "total_tokens": 0, "total_questions_asked": 0, "total_inferences_made": 0,
            "total_actions_fired": 0, "nodes_closed": 0, "nodes_total": 0,
        },
    }


def test_registry_lookup():
    assert get_handler("read_content") is not None
    assert get_handler("scan_em_dashes") is not None
    assert get_handler("git_commit") is not None
    assert get_handler("nonexistent") is None


def test_read_content_reads_real_file(tmp_path, monkeypatch):
    from optogon import action_handlers
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    f = tmp_path / "greeting.md"
    f.write_text("hello world", encoding="utf-8")

    state = _state(file_path="greeting.md")
    result = read_content(state, {"id": "read_content"})
    assert result["file_exists"] is True
    assert result["content"] == "hello world"
    assert result["file_size_ok"] is True


def test_read_content_missing_file_returns_flag(tmp_path, monkeypatch):
    from optogon import action_handlers
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    state = _state(file_path="nope.md")
    result = read_content(state, {"id": "read_content"})
    assert result["file_exists"] is False
    assert result["content"] == ""


def test_read_content_refuses_outside_repo(tmp_path, monkeypatch):
    from optogon import action_handlers
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    other = tmp_path.parent / "elsewhere.md"
    other.write_text("secrets", encoding="utf-8")

    state = _state(file_path=str(other))
    with pytest.raises(ActionError, match="outside repo"):
        read_content(state, {"id": "read_content"})


def test_scan_em_dashes_clean():
    state = _state()
    state["context"]["system"]["content"] = "This is a clean line with no fancy punctuation."
    result = scan_em_dashes(state, {"id": "scan_em_dashes"})
    assert result["em_dash_count"] == 0
    assert result["em_dash_clean"] is True
    assert result["em_dash_lines"] == []


def test_scan_em_dashes_finds_them():
    state = _state()
    state["context"]["system"]["content"] = "Line 1 is fine.\nLine 2 has an em dash \u2014 right here.\nLine 3 too \u2014 and \u2014."
    result = scan_em_dashes(state, {"id": "scan_em_dashes"})
    assert result["em_dash_count"] == 3
    assert result["em_dash_clean"] is False
    assert result["em_dash_lines"] == [2, 3]


def test_scan_em_dashes_raises_without_content():
    state = _state()
    with pytest.raises(ActionError, match="no content"):
        scan_em_dashes(state, {"id": "scan_em_dashes"})


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    # Initial commit so HEAD exists
    (path / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", ".gitkeep"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(path), check=True)


def test_git_commit_dry_run(tmp_path, monkeypatch):
    from optogon import action_handlers
    _init_git_repo(tmp_path)
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    f = tmp_path / "hello.md"
    f.write_text("hi", encoding="utf-8")

    state = _state(file_path="hello.md", commit_message="test: add hello")
    result = git_commit(state, {"id": "git_commit", "spec": {"dry_run": True}})
    assert result["dry_run"] is True
    assert result["commit_sha"] is None
    assert result["would_commit"] == "hello.md"


def test_git_commit_real(tmp_path, monkeypatch):
    from optogon import action_handlers
    _init_git_repo(tmp_path)
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    f = tmp_path / "real.md"
    f.write_text("content", encoding="utf-8")

    state = _state(file_path="real.md", commit_message="test: add real")
    result = git_commit(state, {"id": "git_commit", "spec": {"dry_run": False}})
    assert result["commit_success"] is True
    assert result["commit_sha"]  # non-empty
    assert result["committed_path"] == "real.md"


def test_git_commit_refuses_with_unexpected_staged(tmp_path, monkeypatch):
    from optogon import action_handlers
    _init_git_repo(tmp_path)
    monkeypatch.setattr(action_handlers, "REPO_ROOT", tmp_path)

    target = tmp_path / "target.md"
    target.write_text("me", encoding="utf-8")
    other = tmp_path / "other.md"
    other.write_text("not me", encoding="utf-8")
    # Pre-stage other.md
    subprocess.run(["git", "add", "other.md"], cwd=str(tmp_path), check=True)

    state = _state(file_path="target.md", commit_message="test: target")
    with pytest.raises(ActionError, match="other files are staged"):
        git_commit(state, {"id": "git_commit"})
