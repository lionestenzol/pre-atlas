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
