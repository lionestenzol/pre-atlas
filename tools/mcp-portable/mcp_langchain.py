"""
Auto-generated LangChain MCP client.

Install:
    pip install langchain-mcp-adapters langgraph langchain-anthropic

Run:
    python mcp_langchain.py "your prompt here"
"""
import asyncio, sys
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

SERVERS = {'musescore': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/musescore-mcp/server/musescore_mcp.py'], 'env': {}}, 'everything': {'transport': 'stdio', 'command': 'node', 'args': ['C:/Users/bruke/mcp-servers/everything/dist/index.js'], 'env': {'EVERYTHING_HTTP_PORT': '32233'}}, 'codex': {'transport': 'stdio', 'command': 'codex', 'args': ['mcp-server'], 'env': {}}, 'competitor-monitor': {'transport': 'stdio', 'command': 'C:/Users/bruke/Scrapling/.venv/Scripts/python.exe', 'args': ['C:/Users/bruke/mcp-servers/competitor-monitor/server.py'], 'env': {}}, 'search-stack': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/search-stack/.venv/Scripts/python.exe', 'args': ['-m', 'search_stack.mcp_server'], 'env': {}}, 'atlas-map': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/atlas-map-api/.venv/Scripts/python.exe', 'args': ['-m', 'atlas_map_api.mcp_server'], 'env': {}}, 'repomix': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'repomix', '--mcp'], 'env': {}}, 'deepwiki': {'transport': 'http', 'url': 'https://mcp.deepwiki.com/mcp'}, 'reaper-reapy-mcp': {'transport': 'stdio', 'command': 'python', 'args': ['-m', 'reaper_reapy_mcp'], 'env': {}}, 'atlas-rag': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/atlas-rag/atlas_mcp.py'], 'env': {}}, 'zoekt': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/zoekt-win/zoekt_mcp.py'], 'env': {}}, 'sourcegraph-scip': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/Pre Atlas/services/sourcegraph-scip/sourcegraph_mcp.py'], 'env': {}}, 'touchdesigner': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'touchdesigner-mcp-server@latest', '--stdio'], 'env': {}}}

async def main(prompt: str):
    connections = {}
    for name, cfg in SERVERS.items():
        if cfg["transport"] == "http":
            connections[name] = {"url": cfg["url"], "transport": "streamable_http"}
        else:
            connections[name] = {
                "command": cfg["command"],
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
                "transport": "stdio",
            }

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    agent = create_react_agent(ChatAnthropic(model="claude-sonnet-4-5"), tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    print(result["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list your tools"))

