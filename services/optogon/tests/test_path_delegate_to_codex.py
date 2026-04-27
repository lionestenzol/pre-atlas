"""Tests for the delegate_to_codex Optogon path.

Coverage:
- classify_codex_intent: regex matching against Bruke-shaped phrasings
- raw vs normalized intent: original casing preserved for prompt payload
- run_codex_exec: subprocess invocation safety + schema parsing (mocked)
- E2E via TestClient: full path through /session/run with subprocess mocked
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from optogon import action_handlers
from optogon.action_handlers import classify_codex_intent
from optogon.main import app


# ---------------------------------------------------------------------------
# classify_codex_intent · pure unit tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("intent,expected_skill", [
    # Bruke-shaped triggers (informal phrasing must work)
    ("yeet this with description fix sandbox config", "yeet"),
    ("tat ci is broke", "gh-fix-ci"),
    ("ci is broken", "gh-fix-ci"),
    ("the ci is hosed", "gh-fix-ci"),
    ("tests red on the pr", "gh-fix-ci"),
    ("throw this up on vercel", "vercel-deploy"),
    ("ship it to vercel rq", "vercel-deploy"),
    ("go live with this", "vercel-deploy"),
    ("any vulns in cognitive-sensor", "security-threat-model"),
    ("threat model the daemon", "security-threat-model"),
    ("who owns the routing code", "security-ownership-map"),
    ("transcribe meeting.mp3 with diarization", "transcribe"),
    ("make a sora clip about closure mode", "sora"),
    ("build a cli from this openapi spec", "cli-creator"),
    ("second opinion on this design", "__review__"),
    ("sanity check the migration", "__review__"),
])
def test_classify_intent_matches(intent: str, expected_skill: str) -> None:
    state = {"context": {"confirmed": {"user_intent": intent}, "user": {}, "system": {}}}
    r = classify_codex_intent(state, {})
    assert r["target_skill"] == expected_skill, f"intent={intent!r}: got {r['target_skill']!r}"
    assert r["should_delegate"] is True
    assert r["delegate_reason"] == "matched_intent"


@pytest.mark.parametrize("intent,expected_reason", [
    # Anthropic-skills overlap → route back to Claude
    ("make a 3-page pdf report", "anthropic_overlap"),
    ("export this to pdf", "anthropic_overlap"),
    ("build me a deck for tuesday", "anthropic_overlap"),
    ("touchdesigner network", "anthropic_overlap"),
    ("build an mcp server for stripe", "anthropic_overlap"),
    # No match → also route back
    ("refactor types-core.ts", "no_match"),
    ("explain why the daemon is in CLOSURE mode", "no_match"),
])
def test_classify_intent_no_delegate(intent: str, expected_reason: str) -> None:
    state = {"context": {"confirmed": {"user_intent": intent}, "user": {}, "system": {}}}
    r = classify_codex_intent(state, {})
    assert r["should_delegate"] is False
    assert r["target_skill"] is None
    assert r["delegate_reason"] == expected_reason


def test_classify_preserves_original_casing() -> None:
    """Bug fix: case-sensitive details (paths, identifiers, URLs) must not be mangled."""
    intent = "second opinion on services/Optogon/Main.py at https://Example.COM/Path"
    state = {"context": {"confirmed": {"user_intent": intent}, "user": {}, "system": {}}}
    r = classify_codex_intent(state, {})
    assert r["user_intent_raw"] == intent  # original casing preserved
    assert r["user_intent_normalized"] == intent.lower()  # lowercased for matching only
    assert r["target_skill"] == "__review__"


def test_classify_empty_intent_raises() -> None:
    state = {"context": {"confirmed": {"user_intent": ""}, "user": {}, "system": {}}}
    with pytest.raises(action_handlers.ActionError):
        classify_codex_intent(state, {})


# ---------------------------------------------------------------------------
# run_codex_exec · subprocess mocked
# ---------------------------------------------------------------------------
class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_codex_exec_uses_raw_intent_for_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bug fix: prompt to Codex must use raw casing, not lowercased."""
    captured: dict[str, Any] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return _FakeProc(0, stdout="ok", stderr="")

    monkeypatch.setattr("optogon.action_handlers.subprocess.run", fake_run)
    monkeypatch.setattr("optogon.action_handlers._resolve_codex_executable", lambda: "codex")

    state = {
        "context": {
            "confirmed": {},
            "user": {},
            "system": {
                "framing": "Provide a fresh-frame second opinion.",
                "sandbox": "read-only",
                "target_skill": "__review__",
                "user_intent_normalized": "review services/optogon/main.py",
                "user_intent_raw": "Review services/Optogon/Main.py",
            },
        }
    }
    result = action_handlers.run_codex_exec(state, {})
    prompt = captured["cmd"][-1]
    assert "Review services/Optogon/Main.py" in prompt  # raw casing in prompt
    assert result["codex_success"] is True


def test_run_codex_exec_handles_filenotfound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bug fix: codex.cmd not found should return clean error, not crash."""
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        raise FileNotFoundError(2, "The system cannot find the file specified")

    monkeypatch.setattr("optogon.action_handlers.subprocess.run", fake_run)

    state = {
        "context": {
            "confirmed": {},
            "user": {},
            "system": {
                "framing": "x",
                "sandbox": "read-only",
                "target_skill": "yeet",
                "user_intent_raw": "yeet this",
                "user_intent_normalized": "yeet this",
            },
        }
    }
    result = action_handlers.run_codex_exec(state, {})
    assert result["codex_success"] is False
    assert "not found" in result["codex_stderr"]


def test_run_codex_exec_with_schema_parses_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When schema supplied, handler reads -o file and validates the JSON."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict"],
        "properties": {"verdict": {"type": "string", "enum": ["pass", "fail"]}},
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    output_blob = {"verdict": "pass"}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        # Simulate Codex writing to -o <file>
        # cmd has ... --output-schema <path> -o <outfile> <prompt>
        try:
            o_idx = cmd.index("-o")
            outfile = Path(cmd[o_idx + 1])
            outfile.write_text(json.dumps(output_blob))
        except (ValueError, IndexError):
            pass
        return _FakeProc(0, stdout=json.dumps(output_blob), stderr="")

    monkeypatch.setattr("optogon.action_handlers.subprocess.run", fake_run)
    monkeypatch.setattr("optogon.action_handlers._resolve_codex_executable", lambda: "codex")

    state = {
        "context": {
            "confirmed": {},
            "user": {},
            "system": {
                "framing": "Review.",
                "sandbox": "read-only",
                "target_skill": "__review__",
                "user_intent_raw": "review",
                "user_intent_normalized": "review",
                "output_schema_path": str(schema_path),
            },
        }
    }
    result = action_handlers.run_codex_exec(state, {})
    assert result["codex_success"] is True
    assert result["parsed_output"] == output_blob
    assert result["schema_valid"] is True


# ---------------------------------------------------------------------------
# E2E · /session/run with subprocess mocked (no real Codex call)
# ---------------------------------------------------------------------------
def test_session_run_anthropic_overlap_routes_back(_clear_signals) -> None:  # noqa: ARG001
    """Anthropic-skills overlap MUST close without invoking Codex."""
    client = TestClient(app)
    response = client.post("/session/run", json={
        "path_id": "delegate_to_codex",
        "initial_context": {
            "user_intent": "make a 3-page pdf report",
            "cwd": ".",
        },
    })
    assert response.status_code == 200
    data = response.json()
    assert data["closed"] is True
    sysctx = data["state"]["context"]["system"]
    assert sysctx["should_delegate"] is False
    assert sysctx["delegate_reason"] == "anthropic_overlap"
    # Codex must NOT have been called
    assert "codex_success" not in sysctx


def test_session_run_full_loop_with_codex_mocked(
    monkeypatch: pytest.MonkeyPatch, _clear_signals  # noqa: ARG001
) -> None:
    """Full path runs entry → classify → route_gate → run → output_gate → done."""
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return _FakeProc(0, stdout="(mocked codex output)", stderr="")
    monkeypatch.setattr("optogon.action_handlers.subprocess.run", fake_run)
    monkeypatch.setattr("optogon.action_handlers._resolve_codex_executable", lambda: "codex")

    client = TestClient(app)
    response = client.post("/session/run", json={
        "path_id": "delegate_to_codex",
        "initial_context": {
            "user_intent": "yeet this with description test fix",
            "cwd": ".",
        },
    })
    assert response.status_code == 200
    data = response.json()
    assert data["closed"] is True
    outputs = data["outputs"]
    assert outputs["codex_success"] is True
    assert outputs["skill"] == "yeet"
    assert outputs["sandbox"] == "workspace-write"
    assert "(mocked codex output)" in outputs["codex_output"]
    assert data["turns_walked"] >= 1


def test_session_run_caps_at_max_turns(
    monkeypatch: pytest.MonkeyPatch, _clear_signals  # noqa: ARG001
) -> None:
    """Even if subprocess somehow stalls a node, run loop must not infinite-loop."""
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return _FakeProc(0, stdout="ok", stderr="")
    monkeypatch.setattr("optogon.action_handlers.subprocess.run", fake_run)
    monkeypatch.setattr("optogon.action_handlers._resolve_codex_executable", lambda: "codex")

    client = TestClient(app)
    response = client.post("/session/run", json={
        "path_id": "delegate_to_codex",
        "initial_context": {"user_intent": "second opinion x", "cwd": "."},
    })
    # Either closed or turns_walked < 30 (the cap)
    data = response.json()
    assert data["turns_walked"] <= 30
