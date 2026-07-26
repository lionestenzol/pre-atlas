"""
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

SERVERS = {'musescore': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/musescore-mcp/server/musescore_mcp.py'], 'env': {}}, 'everything': {'transport': 'stdio', 'command': 'node', 'args': ['C:/Users/bruke/mcp-servers/everything/dist/index.js'], 'env': {'EVERYTHING_HTTP_PORT': '32233'}}, 'codex': {'transport': 'stdio', 'command': 'codex', 'args': ['mcp-server'], 'env': {}}, 'competitor-monitor': {'transport': 'stdio', 'command': 'C:/Users/bruke/Scrapling/.venv/Scripts/python.exe', 'args': ['C:/Users/bruke/mcp-servers/competitor-monitor/server.py'], 'env': {}}, 'search-stack': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/search-stack/.venv/Scripts/python.exe', 'args': ['-m', 'search_stack.mcp_server'], 'env': {}}, 'atlas-map': {'transport': 'stdio', 'command': 'C:/Users/bruke/Pre Atlas/services/atlas-map-api/.venv/Scripts/python.exe', 'args': ['-m', 'atlas_map_api.mcp_server'], 'env': {}}, 'repomix': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'repomix', '--mcp'], 'env': {}}, 'deepwiki': {'transport': 'http', 'url': 'https://mcp.deepwiki.com/mcp'}, 'reaper-reapy-mcp': {'transport': 'stdio', 'command': 'python', 'args': ['-m', 'reaper_reapy_mcp'], 'env': {}}, 'atlas-rag': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/atlas-rag/atlas_mcp.py'], 'env': {}}, 'zoekt': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/zoekt-win/zoekt_mcp.py'], 'env': {}}, 'sourcegraph-scip': {'transport': 'stdio', 'command': 'python', 'args': ['C:/Users/bruke/Pre Atlas/services/sourcegraph-scip/sourcegraph_mcp.py'], 'env': {}}, 'touchdesigner': {'transport': 'stdio', 'command': 'npx', 'args': ['-y', 'touchdesigner-mcp-server@latest', '--stdio'], 'env': {}}}
TIMEOUT_S = 60  # generous for npx cold-start

async def probe_stdio(name, cfg):
    t0 = time.time()
    async with AsyncExitStack() as stack:
        params = StdioServerParameters(
            command=cfg["command"], args=cfg.get("args", []),
            env=cfg.get("env", {}) or None,
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
    body = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2025-06-18","capabilities":{},
        "clientInfo":{"name":"mcp-smoke","version":"0"}}}
    headers = {"Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        r = await c.post(cfg["url"], json=body, headers=headers)
        r.raise_for_status()
        if '"result"' not in r.text:
            raise RuntimeError(f"no JSON-RPC result in response: {r.text[:120]}")
    return "handshake-ok", time.time() - t0

async def probe(name, cfg):
    try:
        fn = probe_http if cfg["transport"] == "http" else probe_stdio
        result, dt = await asyncio.wait_for(fn(name, cfg), TIMEOUT_S)
        print(f"  [OK]   {name:24s} {cfg['transport']:6s} {result} tools  ({dt:.1f}s)")
        return True
    except asyncio.TimeoutError:
        print(f"  [FAIL] {name:24s} timeout after {TIMEOUT_S}s")
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        print(f"  [FAIL] {name:24s} {type(e).__name__}: {msg}")
    return False

async def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    targets = {k: v for k, v in SERVERS.items() if not only or k == only}
    if not targets:
        print(f"no server named {only!r}. known: {list(SERVERS)}")
        sys.exit(2)
    print(f"probing {len(targets)} servers...")
    results = await asyncio.gather(*[probe(n, c) for n, c in targets.items()])
    ok, fail = sum(results), sum(1 for r in results if not r)
    print(f"\n{ok} ok, {fail} failed")
    sys.exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())

