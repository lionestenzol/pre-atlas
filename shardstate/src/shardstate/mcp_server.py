"""MCP server: exposes the store over stdio for Claude Code and other MCP clients.

Run as: `shardstate-mcp --db ./fleet.db`

Optional dependency. Install with: `pip install shardstate[mcp]`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict

from .store import NotFound, Ref, Store, StoreError


def _build_tools() -> list[dict]:
    return [
        {
            "name": "put",
            "description": "Insert or replace an entity. Returns the new state hash and the entity's stable id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "value": {"description": "JSON value to store."},
                    "stable_id": {"type": "string", "description": "Optional stable id; one is generated if omitted."},
                },
                "required": ["value"],
            },
        },
        {
            "name": "get",
            "description": "Read an entity by stable id, optionally pinned to a state hash.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stable_id": {"type": "string"},
                    "state": {"type": "string", "description": "Optional state hash; defaults to current."},
                },
                "required": ["stable_id"],
            },
        },
        {
            "name": "patch",
            "description": "Apply dotted-path changes to an entity. Returns the new state hash.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stable_id": {"type": "string"},
                    "changes": {"type": "object", "description": "Dotted-path → new value."},
                },
                "required": ["stable_id", "changes"],
            },
        },
        {
            "name": "append",
            "description": "Append to a list at a dotted path inside an entity.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stable_id": {"type": "string"},
                    "path": {"type": "string"},
                    "value": {},
                },
                "required": ["stable_id", "path", "value"],
            },
        },
        {
            "name": "diff",
            "description": "Per-entity changes between two state hashes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "state_a": {"type": "string"},
                    "state_b": {"type": "string"},
                },
                "required": ["state_a", "state_b"],
            },
        },
        {
            "name": "resolve",
            "description": "Resolve a Ref (state, node, op) to its node value.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                    "node": {"type": "string"},
                    "op": {"type": "string", "default": "read"},
                },
                "required": ["state", "node"],
            },
        },
        {
            "name": "head",
            "description": "Current state root (hash, parent, seq).",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "conflicts",
            "description": "Inspect logged conflicts. Optional stable_id filter.",
            "inputSchema": {
                "type": "object",
                "properties": {"stable_id": {"type": "string"}},
            },
        },
    ]


def _dispatch(store: Store, name: str, args: Dict[str, Any]) -> Any:
    if name == "put":
        node = store.put(args["value"], stable_id=args.get("stable_id"))
        return {"id": node.id, "hash": node.hash, "state": store.head().hash}  # type: ignore[union-attr]
    if name == "get":
        return store.get(args["stable_id"], state=args.get("state"))
    if name == "patch":
        state = store.patch(args["stable_id"], args["changes"])
        return {"state": state.hash, "seq": state.seq}
    if name == "append":
        state = store.append(args["stable_id"], args["path"], args["value"])
        return {"state": state.hash, "seq": state.seq}
    if name == "diff":
        return store.diff(args["state_a"], args["state_b"])
    if name == "resolve":
        return store.resolve(Ref(state=args["state"], node=args["node"], op=args.get("op", "read")))
    if name == "head":
        h = store.head()
        return None if h is None else {"hash": h.hash, "parent": h.parent, "seq": h.seq}
    if name == "conflicts":
        cs = store.conflicts(args.get("stable_id"))
        return [
            {
                "stable_id": c.stable_id,
                "winning_hash": c.winning_hash,
                "losing_hash": c.losing_hash,
                "winning_agent": c.winning_agent,
                "losing_agent": c.losing_agent,
                "detected_at": c.detected_at,
            }
            for c in cs
        ]
    raise StoreError(f"unknown tool: {name}")


async def _run_stdio(store: Store) -> None:
    # Lazy-import so the package is usable without the optional dep.
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server: Server = Server("shardstate")
    tool_specs = _build_tools()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**spec) for spec in tool_specs]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = _dispatch(store, name, arguments or {})
            payload = json.dumps(result, default=str)
        except (NotFound, StoreError) as e:
            payload = json.dumps({"error": str(e), "type": type(e).__name__})
        return [TextContent(type="text", text=payload)]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="shardstate MCP server")
    parser.add_argument("--db", default=os.environ.get("SHARDSTATE_DB", "./shardstate.db"))
    parser.add_argument("--agent-id", default=os.environ.get("SHARDSTATE_AGENT_ID"))
    args = parser.parse_args()
    store = Store(args.db, agent_id=args.agent_id)
    try:
        asyncio.run(_run_stdio(store))
    finally:
        store.close()


if __name__ == "__main__":
    main()
