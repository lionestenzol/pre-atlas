# MCP Portable Registry

One canonical file (`mcp-servers.json`) + one generator (`gen_mcp.py`) that emits configs for every major MCP-capable client.

## Files

| File | Purpose |
|---|---|
| `mcp-servers.json` | Source of truth. Server list with `${VAR}` substitution for portability. |
| `gen_mcp.py` | Reads the canonical file, emits a config for the target you pick. |
| `README.md` | This file. |

## Quick start

```bash
python gen_mcp.py <target> > <output-file>
```

| Target | Output goes to | Client |
|---|---|---|
| `cursor` | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) | Cursor |
| `chatgpt` | ChatGPT Desktop MCP config path | ChatGPT Desktop (Pro, stdio only) |
| `claude-desktop` | `%APPDATA%/Claude/claude_desktop_config.json` (Win) or `~/Library/Application Support/Claude/…` (mac) | Claude Desktop |
| `windsurf` | `~/.codeium/windsurf/mcp_config.json` | Windsurf |
| `python` | `mcp_client.py` — runnable | OpenAI Agents SDK |
| `langchain` | `mcp_langchain.py` — runnable | LangChain + LangGraph |
| `anthropic` | `mcp_anthropic.py` — runnable | Anthropic SDK (native) |
| `smoke` | `mcp_smoke.py` — runnable, **no API key** | Verifies every server spawns + lists tools |

The four JSON clients share one schema (`{"mcpServers": {name: {command, args, env}}}`) — same output, different destination.

## Editing the canonical file

Add or change a server in `mcp-servers.json`, then regenerate. Use `${HOME}`, `${PRE_ATLAS}`, or `${LOCALAPPDATA}` in paths — the generator substitutes them from the `vars` block (or env vars).

```jsonc
"server-name": {
  "transport": "stdio",          // or "http"
  "command": "python",           // stdio only
  "args": ["-m", "some.module"], // stdio only
  "env": { "FOO": "bar" },       // stdio only, optional
  "url": "https://…/mcp",        // http only
  "tags": ["code-search"]        // free-form, not emitted
}
```

## Per-client steps

### Cursor
```bash
python gen_mcp.py cursor > .cursor/mcp.json
```
Restart Cursor. Servers show up under **Settings → MCP**.

### Claude Desktop
```bash
# Windows
python gen_mcp.py claude-desktop > "$APPDATA/Claude/claude_desktop_config.json"
# macOS
python gen_mcp.py claude-desktop > "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
```
Fully quit and relaunch (menu-bar quit, not window close).

### ChatGPT Desktop
Same schema as Claude Desktop. Pro tier, stdio only — no remote MCP. Bridge remote servers via `mcp-proxy` (see below).

### Windsurf
```bash
python gen_mcp.py windsurf > ~/.codeium/windsurf/mcp_config.json
```

### OpenAI Agents SDK
```bash
pip install openai-agents mcp
python gen_mcp.py python > mcp_client.py
python mcp_client.py "list your tools"
```

### LangChain / LangGraph
```bash
pip install langchain-mcp-adapters langgraph langchain-anthropic
export ANTHROPIC_API_KEY=…
python gen_mcp.py langchain > mcp_langchain.py
python mcp_langchain.py "your prompt"
```
Swap the model: change `ChatAnthropic(model=…)` or import `langchain-openai` / `langchain-google-genai` — tool-calling contract is the same.

### Anthropic SDK (native)
```bash
pip install anthropic mcp
export ANTHROPIC_API_KEY=…
python gen_mcp.py anthropic > mcp_anthropic.py
python mcp_anthropic.py "your prompt"
```
- **Remote (http)** servers pass through the `mcp_servers` beta (`mcp-client-2025-04-04`).
- **Local (stdio)** servers are spawned and bridged in as `{server}__{tool}`.

## Bridging transports

**Remote → stdio** (for ChatGPT Desktop and other stdio-only clients):
```bash
pipx install mcp-proxy
```
Add a stdio entry that shells out to the proxy:
```jsonc
"deepwiki-local": {
  "transport": "stdio",
  "command": "mcp-proxy",
  "args": ["https://mcp.deepwiki.com/mcp"]
}
```

**Stdio → remote** (for web-hosted UIs like ChatGPT web / Claude.ai connectors):
```bash
mcp-proxy --sse-port 8080 -- python -m your.stdio.server
# point the connector at http://your-host:8080/sse
```

Either bridge is the only code change; the canonical registry stays the same.

## What does NOT port

Skills, slash commands, hooks, `CLAUDE.md`, session memory — these are Claude Code harness features, not MCP. Distill each skill to its trigger + instruction + tool list, then bake into the target's system prompt or wrap as a native agent.

## Disabling a server temporarily

Prefix the key with `_` in `mcp-servers.json` — the generator drops any entry whose key starts with underscore, so it disappears from every emitted config. Restore by removing the prefix. Example:

```jsonc
"_jbcontext_DISABLED": { "_reason": "waiting on AI access", "command": …, "args": … }
```

## Troubleshooting

- **Server appears but no tools:** process crashed on startup. Run its `command args` in a shell to see stderr.
- **Windows paths with spaces:** the generator writes forward slashes — every MCP client on Windows handles them correctly.
- **Moved a venv:** update the entry in `mcp-servers.json` once, regenerate everywhere.
- **`npx` cold-start slowness:** first run downloads the package. Pre-warm with `npx -y repomix --mcp --help` once.
