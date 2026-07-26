#!/usr/bin/env python3
"""
gen_mcp.py - port one canonical mcp-servers.json to any MCP client.

Usage:
    python gen_mcp.py cursor        > .cursor/mcp.json
    python gen_mcp.py chatgpt       > claude_desktop_config.json   # same schema
    python gen_mcp.py claude-desktop> claude_desktop_config.json
    python gen_mcp.py windsurf      > mcp_config.json
    python gen_mcp.py python        > mcp_client.py                # OpenAI Agents SDK
    python gen_mcp.py langchain     > mcp_langchain.py             # LangChain + LangGraph
    python gen_mcp.py anthropic     > mcp_anthropic.py             # native Anthropic SDK

Canonical file: mcp-servers.json in the same directory (override with --file).
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_SRC = HERE / "mcp-servers.json"

def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    vars_ = {**os.environ, **data.get("vars", {})}
    def sub(s):
        if not isinstance(s, str): return s
        return re.sub(r"\$\{(\w+)\}", lambda m: vars_.get(m.group(1), m.group(0)), s)
    def walk(x):
        if isinstance(x, dict):  return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):  return [walk(v) for v in x]
        return sub(x)
    out = walk(data)
    # Drop disabled entries: any server whose key starts with "_"
    out["servers"] = {k: v for k, v in out.get("servers", {}).items() if not k.startswith("_")}
    return out

def _servers_dict(cfg: dict) -> dict:
    out = {}
    for name, s in cfg["servers"].items():
        if s["transport"] == "http":
            out[name] = {"transport": "http", "url": s["url"]}
        else:
            out[name] = {
                "transport": "stdio",
                "command": s["command"],
                "args": s.get("args", []),
                "env": s.get("env", {}),
            }
    return out

# ---------- Cursor / Windsurf / Claude Desktop / ChatGPT Desktop ----------
def emit_json_client(cfg: dict) -> str:
    out = {"mcpServers": {}}
    for name, s in cfg["servers"].items():
        if s["transport"] == "http":
            out["mcpServers"][name] = {"url": s["url"]}
        else:
            entry = {"command": s["command"], "args": s.get("args", [])}
            if s.get("env"): entry["env"] = s["env"]
            out["mcpServers"][name] = entry
    return json.dumps(out, indent=2)

# ---------- OpenAI Agents SDK ----------
PY_TEMPLATE = '''"""
Auto-generated MCP client for OpenAI Agents SDK.

Install:
    pip install openai-agents mcp

Run:
    python mcp_client.py "your prompt here"
"""
import asyncio, sys
from agents import Agent, Runner
from agents.mcp import MCPServerStdio, MCPServerSse

SERVERS = {servers!r}

async def main(prompt: str):
    ctx_mgrs = []
    for name, cfg in SERVERS.items():
        if cfg["transport"] == "http":
            ctx_mgrs.append(MCPServerSse(name=name, params={{"url": cfg["url"]}}))
        else:
            ctx_mgrs.append(MCPServerStdio(name=name, params={{
                "command": cfg["command"],
                "args": cfg.get("args", []),
                "env": cfg.get("env", {{}}),
            }}))

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
'''

def emit_python(cfg: dict) -> str:
    return PY_TEMPLATE.format(servers=_servers_dict(cfg))

# ---------- LangChain (langchain-mcp-adapters) ----------
LC_TEMPLATE = '''"""
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

SERVERS = {servers!r}

async def main(prompt: str):
    connections = {{}}
    for name, cfg in SERVERS.items():
        if cfg["transport"] == "http":
            connections[name] = {{"url": cfg["url"], "transport": "streamable_http"}}
        else:
            connections[name] = {{
                "command": cfg["command"],
                "args": cfg.get("args", []),
                "env": cfg.get("env", {{}}),
                "transport": "stdio",
            }}

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    agent = create_react_agent(ChatAnthropic(model="claude-sonnet-4-5"), tools)
    result = await agent.ainvoke({{"messages": [{{"role": "user", "content": prompt}}]}})
    print(result["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list your tools"))
'''

def emit_langchain(cfg: dict) -> str:
    return LC_TEMPLATE.format(servers=_servers_dict(cfg))

# ---------- Anthropic SDK (native MCP connector) ----------
AN_TEMPLATE = '''"""
Auto-generated Anthropic SDK MCP client.

Install:
    pip install anthropic mcp

Run:
    python mcp_anthropic.py "your prompt here"

Notes:
    * Remote (http) MCP servers pass straight through via the mcp_servers beta.
    * Local stdio servers are launched here, their tools bridged into the
      Messages API as regular tool definitions named {{server}}__{{tool}}.
"""
import asyncio, json, sys
from contextlib import AsyncExitStack
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS = {servers!r}
MODEL = "claude-sonnet-4-5"

async def main(prompt: str):
    client = Anthropic()
    stack = AsyncExitStack()
    sessions: dict[str, ClientSession] = {{}}
    tool_to_server: dict[str, str] = {{}}
    anthropic_tools = []
    remote_mcp = []

    async with stack:
        for name, cfg in SERVERS.items():
            if cfg["transport"] == "http":
                remote_mcp.append({{"type": "url", "url": cfg["url"], "name": name}})
                continue
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env", {{}}) or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            sessions[name] = session
            listed = await session.list_tools()
            for t in listed.tools:
                qualified = f"{{name}}__{{t.name}}"
                tool_to_server[qualified] = name
                anthropic_tools.append({{
                    "name": qualified,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {{"type": "object"}},
                }})

        messages = [{{"role": "user", "content": prompt}}]
        extra = {{}}
        if remote_mcp:
            extra["mcp_servers"] = remote_mcp
            extra["betas"] = ["mcp-client-2025-04-04"]

        while True:
            resp = client.beta.messages.create(
                model=MODEL, max_tokens=4096,
                tools=anthropic_tools, messages=messages, **extra,
            )
            messages.append({{"role": "assistant", "content": resp.content}})
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
                tool_results.append({{
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": [{{"type": "text", "text": json.dumps([c.model_dump() for c in out.content])}}],
                }})
            messages.append({{"role": "user", "content": tool_results}})

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "list your tools"))
'''

def emit_anthropic(cfg: dict) -> str:
    return AN_TEMPLATE.format(servers=_servers_dict(cfg))

# ---------- Smoke test (no LLM key required) ----------
SMOKE_TEMPLATE = '''"""
Auto-generated MCP smoke test. Spawns every server, initializes, lists tools.
No LLM call, no API key required.

Install:
    pip install mcp httpx

Run:
    python mcp_smoke.py                # all servers
    python mcp_smoke.py atlas-map      # one server by name
"""
import asyncio, sys, time
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS = {servers!r}
TIMEOUT_S = 60  # generous for npx cold-start

async def probe_stdio(name, cfg):
    t0 = time.time()
    async with AsyncExitStack() as stack:
        params = StdioServerParameters(
            command=cfg["command"], args=cfg.get("args", []),
            env=cfg.get("env", {{}}) or None,
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        listed = await session.list_tools()
        return len(listed.tools), time.time() - t0

async def probe_http(name, cfg):
    # Real MCP HTTP handshake: POST initialize, expect JSON-RPC result
    import httpx
    t0 = time.time()
    body = {{"jsonrpc":"2.0","id":1,"method":"initialize","params":{{
        "protocolVersion":"2025-06-18","capabilities":{{}},
        "clientInfo":{{"name":"mcp-smoke","version":"0"}}}}}}
    headers = {{"Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.post(cfg["url"], json=body, headers=headers)
        r.raise_for_status()
        if '"result"' not in r.text:
            raise RuntimeError(f"no JSON-RPC result in response: {{r.text[:120]}}")
    return "handshake-ok", time.time() - t0

async def probe(name, cfg):
    try:
        fn = probe_http if cfg["transport"] == "http" else probe_stdio
        result, dt = await asyncio.wait_for(fn(name, cfg), TIMEOUT_S)
        print(f"  [OK]   {{name:24s}} {{cfg['transport']:6s}} {{result}} tools  ({{dt:.1f}}s)")
        return True
    except asyncio.TimeoutError:
        print(f"  [FAIL] {{name:24s}} timeout after {{TIMEOUT_S}}s")
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        print(f"  [FAIL] {{name:24s}} {{type(e).__name__}}: {{msg}}")
    return False

async def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    targets = {{k: v for k, v in SERVERS.items() if not only or k == only}}
    if not targets:
        print(f"no server named {{only!r}}. known: {{list(SERVERS)}}")
        sys.exit(2)
    print(f"probing {{len(targets)}} servers...")
    results = await asyncio.gather(*[probe(n, c) for n, c in targets.items()])
    ok, fail = sum(results), sum(1 for r in results if not r)
    print(f"\\n{{ok}} ok, {{fail}} failed")
    sys.exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
'''

def emit_smoke(cfg: dict) -> str:
    return SMOKE_TEMPLATE.format(servers=_servers_dict(cfg))

TARGETS = {
    "cursor":  emit_json_client,
    "chatgpt": emit_json_client,
    "claude-desktop": emit_json_client,
    "windsurf": emit_json_client,
    "python":  emit_python,
    "langchain": emit_langchain,
    "anthropic": emit_anthropic,
    "smoke":   emit_smoke,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=sorted(TARGETS))
    ap.add_argument("--file", type=Path, default=DEFAULT_SRC)
    a = ap.parse_args()
    cfg = load(a.file)
    print(TARGETS[a.target](cfg))

if __name__ == "__main__":
    main()
