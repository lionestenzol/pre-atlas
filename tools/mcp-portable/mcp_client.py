"""
Auto-generated MCP client for OpenAI Agents SDK.

Install:
    pip install openai-agents mcp

Run:
    python mcp_client.py "your prompt here"
"""
import asyncio, sys
from agents import Agent, Runner
from agents.mcp import MCPServerStdio, MCPServerSse

SERVERS = {'musescore': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/musescore-mcp/server/musescore_mcp.py'], 'env': {}}, 'everything': {'transport': 'stdio', 'command': 'node', 'args': ['C:/Users/bruke/mcp-servers/everything/dist/index.js'], 'env': {'EVERYTHING_HTTP_PORT': '32233'}}, 'codex': {'transport': 'stdio', 'command': 'codex', 'args': ['mcp-server'], 'env': {}}, 'competitor-monitor': {'transport': 'stdio', 'command': 'C:/Users/bruke/Scrapling/.venv/Scripts/python.exe', 'args': ['C:/Users/bruke/mcp-servers/competitor-monitor/server.py'], 'env': {}}, 'search-stack': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/search-stack/.venv/Scripts/python.exe', 'args': ['-m', 'search_stack.mcp_server'], 'env': {}}, 'atlas-map': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/atlas-map-api/.venv/Scripts/python.exe', 'args': ['-m', 'atlas_map_api.mcp_server'], 'env': {}}, 'repomix': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'repomix', '--mcp'], 'env': {}}, 'deepwiki': {'transport': 'http', 'url': 'https://mcp.deepwiki.com/mcp'}, 'reaper-reapy-mcp': {'transport': 'stdio', 'command': 'python', 'args': ['-m', 'reaper_reapy_mcp'], 'env': {}}, 'atlas-rag': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/atlas-rag/atlas_mcp.py'], 'env': {}}, 'zoekt': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/zoekt-win/zoekt_mcp.py'], 'env': {}}, 'sourcegraph-scip': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/Pre Atlas/services/sourcegraph-scip/sourcegraph_mcp.py'], 'env': {}}, 'touchdesigner': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'touchdesigner-mcp-server@latest', '--stdio'], 'env': {}}}

async def main(prompt: str):
    ctx_mgrs = []
    for name, cfg in SERVERS.items():
        if cfg["transport"] == "http":
            ctx_mgrs.append(MCPServerSse(name=name, params={"url": cfg["url"]}))
        else:
            ctx_mgrs.append(MCPServerStdio(name=name, params={
                "command": cfg["command"],
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
            }))

    servers = []
    for cm in ctx_mgrs:
        servers.append(await cm.__aenter__())
    try:
        agent = Agent(
            name="MCP-Agent",
            instructions="You are a general assistant with tool access.",
            mcp_servers=servers,
        )
        result = await Runner.run(agent, prompt)
        print(result.final_output)
    finally:
        for cm in reversed(ctx_mgrs):
            await cm.__aexit__(None, None, None)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list your tools"))

