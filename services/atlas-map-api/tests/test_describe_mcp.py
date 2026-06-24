"""Tests for the agent-facing MCP self-description tools (atlas_describe*)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastmcp")

from atlas_map_api import mcp_server


def _run(coro):
    return asyncio.run(coro)


def test_atlas_describe_returns_caller_scoped_form():
    form = _run(mcp_server.atlas_describe("droplist", "agent"))
    assert form["form_id"] == "droplist@agent"
    assert form["caller"]["role"] == "agent"
    assert isinstance(form["fields"], list) and form["fields"]


def test_atlas_describe_default_role_is_agent():
    form = _run(mcp_server.atlas_describe("droplist"))
    assert form["form_id"] == "droplist@agent"


def test_atlas_describe_unknown_surface():
    out = _run(mcp_server.atlas_describe("__nope__"))
    assert "error" in out


def test_atlas_describe_respects_role_scoping():
    # an agent never sees internal/criticality>=2 on delta-kernel
    form = _run(mcp_server.atlas_describe("delta-kernel", "agent"))
    ids = {f["id"] for f in form["fields"]}
    assert "override_law" not in ids and "set_state" not in ids


def test_atlas_describe_list_lists_surfaces_and_roles():
    out = _run(mcp_server.atlas_describe_list())
    assert "droplist" in out["surfaces"]
    assert {"anon", "agent", "operator", "root"} <= {r["role"] for r in out["roles"]}


def test_atlas_call_read_returns_envelope():
    # health is a public read; the MCP 'agent' role sees it -> reaches invocation.
    out = _run(mcp_server.atlas_call("delta-kernel", "health"))
    assert out.get("kind") == "http" and out.get("surface") == "delta-kernel"


def test_atlas_call_refuses_capability_agent_cannot_see():
    # set_state is internal — the 'agent' role can't see it -> gateway refusal.
    out = _run(mcp_server.atlas_call("delta-kernel", "set_state", {"x": "1"}))
    assert "error" in out


def test_atlas_describe_role_cannot_escalate_past_agent():
    # an MCP agent asking for the 'root' form is clamped to 'agent' (no preview of internals).
    out = _run(mcp_server.atlas_describe("delta-kernel", "root"))
    assert out["form_id"] == "delta-kernel@agent"
    ids = {f["id"] for f in out["fields"]}
    assert "override_law" not in ids and "set_state" not in ids
