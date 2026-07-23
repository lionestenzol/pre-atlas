"""Tests for tools/lattice — Skill -> Receipt adapters (LangGraph Skill Lattice, Seq 2).

Two layers, both hermetic (no real claude-agent-sdk call, no network):
  1. Schema validity: every registered output_format schema is well-formed JSON
     Schema, and a realistic example payload validates against it.
  2. invoke_skill's wrapping logic: a fake claude_agent_sdk module (injected via
     sys.modules) stands in for the real SDK, so the Receipt-building branches
     (ok / error / no-result) are provable without spending real API budget.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import pytest


def _load_lattice_module(name: str):
    """Dynamically load a tools/lattice/*.py module (mirrors test_seam.py's
    _load_seam_runner -- these are standalone scripts, not an installed package)."""
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # so the module's own relative imports (schemas) resolve
    spec.loader.exec_module(mod)
    return mod


schemas = _load_lattice_module("schemas")


# ---- schema validity -----------------------------------------------------------
@pytest.mark.parametrize("skill", sorted(schemas.SKILL_SCHEMAS))
def test_schema_is_well_formed_json_schema(skill):
    jsonschema.Draft7Validator.check_schema(schemas.SKILL_SCHEMAS[skill])


def test_only_the_three_genuinely_agentic_skills_are_registered():
    # Regression guard for the scope-narrowing finding (schemas.py docstring):
    # deterministic/already-covered/non-goal skills must NOT sneak back in.
    assert set(schemas.SKILL_SCHEMAS) == {"code-recon", "groundwork", "weapon"}


def test_code_recon_example_payload_validates():
    example = {
        "scope": "locate where run_id is threaded through /seam/call",
        "search_path": ["rg -n run_id services/atlas-map-api/src"],
        "candidate_files": [
            {"path": "services/atlas-map-api/src/atlas_map_api/server.py", "why": "defines seam_call_endpoint"},
        ],
        "evidence": [
            {"claim": "run_id is an optional Body param", "file": "services/atlas-map-api/src/atlas_map_api/server.py", "line": 662},
        ],
        "conclusion": "run_id flows from the request body into receipt_store.append.",
        "confidence": "confirmed",
        "next_action": "stop",
        "proof": "read server.py:656-696",
    }
    jsonschema.validate(example, schemas.CODE_RECON_SCHEMA)


def test_groundwork_example_payload_validates():
    example = {
        "mode": "plan",
        "candidate_regions": ["services/atlas-map-api"],
        "evidence": [{"finding": "no receipt persistence", "file": "server.py", "line": 678}],
        "festival_ref": "AL0003",
        "tasks": [{"title": "Seq 1: receipt store", "dod": "POST twice, both readable by run_id"}],
    }
    jsonschema.validate(example, schemas.GROUNDWORK_SCHEMA)


def test_weapon_example_payload_validates():
    example = {
        "target": "chatpull archive skill",
        "status": "closed",
        "tasks_completed": 4,
        "tasks_total": 4,
        "completion_criteria": [{"name": "index.md updated on every pull", "pass": True}],
        "cuts": ["JSON manifest (markdown table is the single source of truth)"],
    }
    jsonschema.validate(example, schemas.WEAPON_SCHEMA)


def test_incomplete_code_recon_payload_fails_validation():
    # missing required fields (evidence, proof, ...) must be REJECTED, not silently accepted.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"scope": "x"}, schemas.CODE_RECON_SCHEMA)


# ---- invoke_skill: hermetic, fake SDK ------------------------------------------
@dataclass
class _FakeResultMessage:
    subtype: str = "success"
    duration_ms: int = 0
    duration_api_ms: int = 0
    is_error: bool = False
    num_turns: int = 1
    session_id: str = "test-session"
    stop_reason: str | None = None
    total_cost_usd: float | None = 0.01
    usage: dict | None = None
    result: str | None = None
    structured_output: object = None
    model_usage: dict | None = None
    permission_denials: list | None = None
    deferred_tool_use: object = None
    errors: list | None = None
    api_error_status: int | None = None
    uuid: str | None = None


def _install_fake_sdk(monkeypatch, *, messages):
    """Inject a fake claude_agent_sdk module so invoke_skill's `from claude_agent_sdk
    import ...` (deliberately deferred to call time -- see skill_nodes.py) binds to
    fakes instead of requiring the real package to be installed or spending budget."""
    captured: dict = {}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        for m in messages:
            yield m

    fake_mod = types.ModuleType("claude_agent_sdk")
    fake_mod.ClaudeAgentOptions = lambda **kw: types.SimpleNamespace(**kw)
    fake_mod.ResultMessage = _FakeResultMessage
    fake_mod.query = fake_query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_mod)
    return captured


def test_invoke_skill_unknown_skill_raises_before_touching_the_sdk():
    skill_nodes = _load_lattice_module("skill_nodes")
    with pytest.raises(ValueError, match="no output_format schema registered"):
        asyncio.run(skill_nodes.invoke_skill("not-a-real-skill", "do something"))


def test_invoke_skill_wraps_structured_output_into_ok_receipt(monkeypatch):
    skill_nodes = _load_lattice_module("skill_nodes")
    payload = {
        "scope": "x", "search_path": [], "candidate_files": [], "evidence": [],
        "conclusion": "y", "confidence": "confirmed", "next_action": "stop", "proof": "z",
    }
    captured = _install_fake_sdk(monkeypatch, messages=[
        _FakeResultMessage(is_error=False, structured_output=payload),
    ])

    receipt = asyncio.run(skill_nodes.invoke_skill("code-recon", "investigate the seam"))

    assert receipt.status == "ok" and receipt.tool == "code-recon"
    assert receipt.data == payload
    assert receipt.sha256 and len(receipt.sha256) == 64
    assert captured["prompt"] == "investigate the seam"
    assert captured["options"].skills == ["code-recon"]
    assert captured["options"].output_format == {"type": "json_schema", "schema": skill_nodes.SKILL_SCHEMAS["code-recon"]}


def test_invoke_skill_sha256_is_stable_for_identical_content(monkeypatch):
    skill_nodes = _load_lattice_module("skill_nodes")
    payload_a = {"z": 1, "a": 2}
    payload_b = {"a": 2, "z": 1}  # same content, different key insertion order

    _install_fake_sdk(monkeypatch, messages=[_FakeResultMessage(structured_output=payload_a)])
    r1 = asyncio.run(skill_nodes.invoke_skill("groundwork", "p"))
    _install_fake_sdk(monkeypatch, messages=[_FakeResultMessage(structured_output=payload_b)])
    r2 = asyncio.run(skill_nodes.invoke_skill("groundwork", "p"))

    assert r1.sha256 == r2.sha256  # canonical (sorted-key) JSON -> key order doesn't matter


def test_invoke_skill_different_content_yields_different_sha256(monkeypatch):
    skill_nodes = _load_lattice_module("skill_nodes")
    _install_fake_sdk(monkeypatch, messages=[_FakeResultMessage(structured_output={"a": 1})])
    r1 = asyncio.run(skill_nodes.invoke_skill("groundwork", "p"))
    _install_fake_sdk(monkeypatch, messages=[_FakeResultMessage(structured_output={"a": 2})])
    r2 = asyncio.run(skill_nodes.invoke_skill("groundwork", "p"))
    assert r1.sha256 != r2.sha256


def test_invoke_skill_error_result_becomes_error_receipt_with_no_sha(monkeypatch):
    skill_nodes = _load_lattice_module("skill_nodes")
    _install_fake_sdk(monkeypatch, messages=[
        _FakeResultMessage(is_error=True, structured_output=None, errors=["max_turns exceeded"]),
    ])
    receipt = asyncio.run(skill_nodes.invoke_skill("weapon", "close the mission"))
    assert receipt.status == "error" and receipt.sha256 is None
    assert "max_turns exceeded" in receipt.error


def test_invoke_skill_missing_structured_output_is_an_error_even_if_not_flagged(monkeypatch):
    # is_error False but structured_output None -- the model finished without
    # producing the forced schema. Must not be reported as ok with data=None.
    skill_nodes = _load_lattice_module("skill_nodes")
    _install_fake_sdk(monkeypatch, messages=[
        _FakeResultMessage(is_error=False, structured_output=None, result="I couldn't complete this."),
    ])
    receipt = asyncio.run(skill_nodes.invoke_skill("code-recon", "investigate"))
    assert receipt.status == "error" and receipt.sha256 is None
    assert receipt.error == "I couldn't complete this."


def test_invoke_skill_no_result_message_at_all_is_an_error_receipt(monkeypatch):
    skill_nodes = _load_lattice_module("skill_nodes")
    _install_fake_sdk(monkeypatch, messages=[])  # query yields nothing
    receipt = asyncio.run(skill_nodes.invoke_skill("weapon", "close it"))
    assert receipt.status == "error" and "no ResultMessage" in receipt.error
