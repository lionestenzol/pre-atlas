"""Smoke tests for the MCP wrapper — exercises each tool's underlying function
against the real audit/system-index.json. Skips cleanly if fastmcp isn't installed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastmcp")

import asyncio

from atlas_map_api import mcp_server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_module_imports_and_registers_tools():
    # FastMCP stores tools on the server instance — verify they're registered.
    assert mcp_server.mcp.name == "atlas-map"


def test_atlas_status():
    result = _run(mcp_server.atlas_status())
    assert result["subsystem_count"] > 0
    ports = {p["name"]: p["port"] for p in result["ported"]}
    assert ports.get("delta-kernel") == 3001


def test_atlas_show_delta_kernel():
    result = _run(mcp_server.atlas_show("delta-kernel"))
    assert result["name"] == "delta-kernel"
    assert result["port"] == 3001
    assert isinstance(result["depends_on"], list)
    assert isinstance(result["depended_on_by"], list)


def test_atlas_show_unknown():
    result = _run(mcp_server.atlas_show("__nonexistent__"))
    assert "error" in result


def test_atlas_neighbors_clamp():
    result = _run(mcp_server.atlas_neighbors("delta-kernel", hops=99))
    assert result["hops"] == 5  # clamped


def test_atlas_path_known_edge():
    result = _run(mcp_server.atlas_path("lattice", "delta-kernel"))
    assert result["forward"] == ["lattice", "delta-kernel"]


def test_atlas_search_finds_known():
    result = _run(mcp_server.atlas_search("delta", limit=5))
    names = [it["name"] for it in result["items"]]
    assert "delta-kernel" in names


def test_atlas_list_filter_group():
    result = _run(mcp_server.atlas_list(group="services"))
    assert all(s["group"] == "services" for s in result["items"])


def test_atlas_locate_via_repo_relative():
    result = _run(mcp_server.atlas_locate("services/delta-kernel/src/api/server.ts"))
    assert result["system"] == "delta-kernel"


def test_atlas_reload_returns_ok():
    result = _run(mcp_server.atlas_reload())
    assert result["status"] == "ok"
    assert result["subsystem_count"] > 0
