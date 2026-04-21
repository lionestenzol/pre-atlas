"""Tests for proposal_runner (claude -p based).

Does NOT call the real claude CLI. Monkeypatches `invoke_claude` to return
scripted results so the approve -> branch -> status pipeline is verified
end-to-end without spending money.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import proposal_runner as pr


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point PROPOSALS_PATH + REPO_ROOT into an isolated tmp git repo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(repo), check=True)

    cs_dir = repo / "cs"
    cs_dir.mkdir()
    monkeypatch.setattr(pr, "REPO_ROOT", repo)
    monkeypatch.setattr(pr, "BASE", cs_dir)
    monkeypatch.setattr(pr, "PROPOSALS_PATH", cs_dir / "proposals.json")
    monkeypatch.setattr(pr, "_load_api_key", lambda: None)
    return repo


def _seed(sandbox: Path, **fields) -> dict:
    p = {
        "proposal_id": "test123",
        "dtype": "EXECUTE",
        "domain": "trivial",
        "rationale": "test",
        "suggested_action": "do nothing",
        "status": "approved",
        **fields,
    }
    (sandbox / "cs" / "proposals.json").write_text(
        json.dumps([p]), encoding="utf-8"
    )
    return p


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------
def test_runner_refuses_non_approved(sandbox, monkeypatch):
    _seed(sandbox, status="pending")
    # invoke_claude must NOT be called
    def boom(*a, **kw):
        raise AssertionError("should not invoke claude for non-approved")
    monkeypatch.setattr(pr, "invoke_claude", boom)
    rc = pr.run("test123")
    assert rc == 1


def test_runner_aborts_if_branch_already_exists(sandbox, monkeypatch):
    _seed(sandbox)
    subprocess.run(["git", "branch", "auto/test123"], cwd=str(sandbox), check=True)
    def boom(*a, **kw):
        raise AssertionError("should not invoke claude when branch exists")
    monkeypatch.setattr(pr, "invoke_claude", boom)
    rc = pr.run("test123")
    assert rc == 1


# ---------------------------------------------------------------------------
# Branch created BEFORE claude invocation
# ---------------------------------------------------------------------------
def test_branch_created_before_claude_invocation(sandbox, monkeypatch):
    _seed(sandbox)
    branches_at_invoke_time = []
    def fake_invoke(proposal, branch, api_key_delta):
        # At this point, the branch should exist in the repo
        r = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=str(sandbox), capture_output=True, text=True,
        )
        branches_at_invoke_time.append(r.returncode == 0)
        return {
            "status": "completed",
            "cost_usd": 0.05,
            "duration_seconds": 1.0,
            "final_text": "ok",
            "raw_result": {},
            "stderr_tail": "",
        }
    monkeypatch.setattr(pr, "invoke_claude", fake_invoke)

    rc = pr.run("test123")
    assert rc == 0
    assert branches_at_invoke_time == [True]


# ---------------------------------------------------------------------------
# Status + cost persist on each terminal state
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("claude_status", ["completed", "failed", "timeout", "budget_exceeded"])
def test_final_status_and_cost_persist(sandbox, monkeypatch, claude_status):
    _seed(sandbox)
    monkeypatch.setattr(pr, "invoke_claude", lambda p, b, k: {
        "status": claude_status,
        "cost_usd": 0.42,
        "duration_seconds": 12.3,
        "final_text": "hello",
        "raw_result": {"subtype": "test"},
        "stderr_tail": "",
    })

    rc = pr.run("test123")
    assert rc == (0 if claude_status == "completed" else 2)

    data = json.loads((sandbox / "cs" / "proposals.json").read_text())
    assert data[0]["status"] == claude_status
    assert data[0]["cost_usd"] == 0.42
    assert data[0]["duration_seconds"] == 12.3
    assert data[0]["branch"] == "auto/test123"
    assert data[0]["final_text"] == "hello"


# ---------------------------------------------------------------------------
# _claude_cmd finds the CLI
# ---------------------------------------------------------------------------
def test_claude_cmd_returns_string_or_none(monkeypatch):
    # On this machine it should find claude. On CI it might not — both OK.
    val = pr._claude_cmd()
    assert val is None or isinstance(val, str)


# ---------------------------------------------------------------------------
# invoke_claude: JSON parsing of claude output
# ---------------------------------------------------------------------------
def test_invoke_claude_parses_successful_json(sandbox, monkeypatch):
    _seed(sandbox)
    monkeypatch.setattr(pr, "_claude_cmd", lambda: "/fake/claude")

    class FakeResult:
        stdout = '{"type":"result","subtype":"success","is_error":false,"total_cost_usd":0.25,"num_turns":3,"stop_reason":"end_turn","result":"shipped the thing","session_id":"abc"}\n'
        stderr = ""
        returncode = 0

    monkeypatch.setattr(pr.subprocess, "run", lambda *a, **kw: FakeResult())

    out = pr.invoke_claude({"proposal_id": "p", "dtype": "X", "domain": "y"}, "auto/p", None)
    assert out["status"] == "completed"
    assert out["cost_usd"] == 0.25
    assert out["final_text"] == "shipped the thing"


def test_invoke_claude_detects_budget_exceeded(sandbox, monkeypatch):
    _seed(sandbox)
    monkeypatch.setattr(pr, "_claude_cmd", lambda: "/fake/claude")

    class FakeResult:
        stdout = '{"type":"result","subtype":"error_max_budget_usd","is_error":true,"total_cost_usd":2.10,"errors":["Reached maximum budget ($2)"]}\n'
        stderr = ""
        returncode = 0

    monkeypatch.setattr(pr.subprocess, "run", lambda *a, **kw: FakeResult())

    out = pr.invoke_claude({"proposal_id": "p", "dtype": "X", "domain": "y"}, "auto/p", None)
    assert out["status"] == "budget_exceeded"
    assert out["cost_usd"] == 2.10


def test_invoke_claude_handles_timeout(sandbox, monkeypatch):
    _seed(sandbox)
    monkeypatch.setattr(pr, "_claude_cmd", lambda: "/fake/claude")

    def fake_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(pr.subprocess, "run", fake_run)
    out = pr.invoke_claude({"proposal_id": "p", "dtype": "X", "domain": "y"}, "auto/p", None)
    assert out["status"] == "timeout"


def test_invoke_claude_handles_missing_binary(monkeypatch):
    monkeypatch.setattr(pr, "_claude_cmd", lambda: None)
    out = pr.invoke_claude({"proposal_id": "p", "dtype": "X", "domain": "y"}, "auto/p", None)
    assert out["status"] == "failed"
    assert "claude CLI not found" in out["stderr_tail"]


def test_invoke_claude_handles_non_json_output(sandbox, monkeypatch):
    _seed(sandbox)
    monkeypatch.setattr(pr, "_claude_cmd", lambda: "/fake/claude")

    class FakeResult:
        stdout = "plaintext garbage no json here\n"
        stderr = "some error"
        returncode = 1

    monkeypatch.setattr(pr.subprocess, "run", lambda *a, **kw: FakeResult())
    out = pr.invoke_claude({"proposal_id": "p", "dtype": "X", "domain": "y"}, "auto/p", None)
    assert out["status"] == "failed"
