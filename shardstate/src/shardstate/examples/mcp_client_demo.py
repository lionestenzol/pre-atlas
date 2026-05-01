"""Minimal MCP client demo against the shardstate MCP server.

Spawns `shardstate-mcp` over stdio, calls put/get/patch/resolve, prints results.

Run: python -m shardstate.examples.mcp_client_demo
Requires: pip install 'shardstate[mcp]'
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile


def _check_mcp() -> bool:
    try:
        import mcp  # noqa: F401
        return True
    except ImportError:
        print(
            "mcp library not installed. Install with:\n"
            "    pip install 'shardstate[mcp]'\n"
            "Skipping MCP client demo."
        )
        return False


async def _run(db_path: str) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "shardstate.mcp_server", "--db", db_path],
        env=os.environ.copy(),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"server exposes {len(tools.tools)} tools: "
                  f"{[t.name for t in tools.tools]}")

            put_res = await session.call_tool(
                "put", {"value": {"type": "client", "name": "Marcus"}}
            )
            put_data = json.loads(put_res.content[0].text)
            print(f"put -> {put_data}")
            sid = put_data["id"]
            state = put_data["state"]

            get_res = await session.call_tool("get", {"stable_id": sid})
            print(f"get -> {get_res.content[0].text}")

            patch_res = await session.call_tool(
                "patch", {"stable_id": sid, "changes": {"name": "Marcus Aurelius"}}
            )
            print(f"patch -> {patch_res.content[0].text}")

            resolve_res = await session.call_tool(
                "resolve", {"state": state, "node": sid}
            )
            print(f"resolve@original_state -> {resolve_res.content[0].text}")


def main() -> int:
    if not _check_mcp():
        return 0
    with tempfile.TemporaryDirectory(prefix="shardstate_mcp_demo_") as d:
        db_path = os.path.join(d, "mcp_demo.db")
        asyncio.run(_run(db_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
