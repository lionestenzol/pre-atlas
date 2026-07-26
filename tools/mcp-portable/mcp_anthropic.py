"""
Auto-generated Anthropic SDK MCP client.

Install:
    pip install anthropic mcp

Run:
    python mcp_anthropic.py "your prompt here"

Notes:
    * Remote (http) MCP servers pass straight through via the mcp_servers beta.
    * Local stdio servers are launched here, their tools bridged into the
      Messages API as regular tool definitions named {server}__{tool}.
"""
import asyncio, json, sys
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS = {'musescore': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/musescore-mcp/server/musescore_mcp.py'], 'env': {}}, 'everything': {'transport': 'stdio', 'command': 'node', 'args': ['C:/Users/bruke/mcp-servers/everything/dist/index.js'], 'env': {'EVERYTHING_HTTP_PORT': '32233'}}, 'codex': {'transport': 'stdio', 'command': 'codex', 'args': ['mcp-server'], 'env': {}}, 'competitor-monitor': {'transport': 'stdio', 'command': 'C:/Users/bruke/Scrapling/.venv/Scripts/python.exe', 'args': ['C:/Users/bruke/mcp-servers/competitor-monitor/server.py'], 'env': {}}, 'search-stack': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/search-stack/.venv/Scripts/python.exe', 'args': ['-m', 'search_stack.mcp_server'], 'env': {}}, 'atlas-map': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/atlas-map-api/.venv/Scripts/python.exe', 'args': ['-m', 'atlas_map_api.mcp_server'], 'env': {}}, 'repomix': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'repomix', '--mcp'], 'env': {}}, 'deepwiki': {'transport': 'http', 'url': 'https://mcp.deepwiki.com/mcp'}, 'reaper-reapy-mcp': {'transport': 'stdio', 'command': 'python', 'args': ['-m', 'reaper_reapy_mcp'], 'env': {}}, 'atlas-rag': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/atlas-rag/atlas_mcp.py'], 'env': {}}, 'zoekt': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/zoekt-win/zoekt_mcp.py'], 'env': {}}, 'sourcegraph-scip': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/Pre Atlas/services/sourcegraph-scip/sourcegraph_mcp.py'], 'env': {}}, 'touchdesigner': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'touchdesigner-mcp-server@latest', '--stdio'], 'env': {}}}
MODEL = "claude-sonnet-4-5"

async def main(prompt: str):
    client = Anthropic()
    stack = AsyncExitStack()
    sessions: dict[str, ClientSession] = {}
    tool_to_server: dict[str, str] = {}
    anthropic_tools = []
    remote_mcp = []

    async with stack:
        for name, cfg in SERVERS.items():
            if cfg["transport"] == "http":
                remote_mcp.append({"type": "url", "url": cfg["url"], "name": name})
                continue
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env", {}) or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            sessions[name] = session
            listed = await session.list_tools()
            for t in listed.tools:
                qualified = f"{name}__{t.name}"
                tool_to_server[qualified] = name
                anthropic_tools.append({
                    "name": qualified,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {"type": "object"},
                })

        messages = [{"role": "user", "content": prompt}]
        extra = {}
        if remote_mcp:
            extra["mcp_servers"] = remote_mcp
            extra["betas"] = ["mcp-client-2025-04-04"]

        while True:
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=4096,
                tools=anthropic_tools, messages=messages, **extra,
            )
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                for block in resp.content:
                    if getattr(block, "type", None) == "text":
                        print(block.text)
                return

            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use": continue
                server = tool_to_server[block.name]
                real_name = block.name.split("__", 1)[1]
                out = await sessions[server].call_tool(real_name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": [{"type": "text", "text": json.dumps([c.model_dump() for c in out.content])}],
                })
            messages.append({"role": "user", "content": tool_results})

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list your tools"))

