# search-stack

Unified search router for Pre Atlas. One REST API and one MCP server in front of:

- **External web search** — Exa (semantic), Tavily (real-time/news), Brave (broad index)
- **Page extraction** — Firecrawl (managed)
- **Local code/file** — code-recon ladder (es → fd → rg → sg)
- **GitHub** — gh CLI passthrough
- **Memory** — DropList retrieval + cognitive-sensor embeddings (Phase 3)

Sits at port 3070. Speaks REST for humans/curl and MCP for Claude.

## Why this exists

Three search categories were already working but isolated: code search (`code-recon` skill, formerly `repo-search`), web extract (`sitepull`/`scrapling`/`anatomy-extension`), and capture (`droplist`). Three memory stores held embeddings, graphs, and packets but exposed no REST. There was no external web/agent-search at all.

This service:

1. Adds **4 agent-search APIs** in one place with per-provider budget guards.
2. Provides **one router** that picks the right tool per intent (no tool sprawl).
3. Surfaces a **single MCP** so Claude can call `search_stack_search` from any session.
4. Reuses existing infrastructure — does NOT rewrite sitepull, scrapling, code-recon, or atlas_query.

See [`BIBLE.md`](BIBLE.md) for the contract.

## Quick start

```bash
# 1. Install
cd services/search-stack
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# edit .env, fill in EXA_API_KEY / TAVILY_API_KEY / BRAVE_API_KEY / FIRECRAWL_API_KEY

# 3. Run REST server
.venv/Scripts/python.exe -m search_stack.server
# listens on 127.0.0.1:3070

# 4. Run MCP server (separate terminal, for Claude integration)
.venv/Scripts/python.exe -m search_stack.mcp_server
```

## Endpoints

```text
POST /search           {q, kind?, max_results?, providers?}    → ranked merged results
POST /extract          {url, mode?}                            → cleaned page content
GET  /budget                                                   → per-provider quota usage
POST /memory/save      {result, drop_to?}                      → persist to DropList
GET  /healthz                                                  → liveness
```

## Routing rules

Intent classifier (rule-based first):

| User query shape | kind | Providers tried (in order) |
|---|---|---|
| Plain text question | `web` | exa → tavily → brave |
| Starts with `http(s)://` | `extract` | firecrawl → sitepull fallback |
| Contains `site:github.com` or `repo:` | `github` | gh CLI |
| Contains `path:` or `file:` prefix | `file` | es (machine layer) |
| Contains code-recon operators (`rg:`, `fd:`, `sg:`) | `code` | code-recon ladder |
| Explicit `kind=memory` | `memory` | droplist + cognitive-sensor (Phase 3) |

## Phase scope

This is **Phase 0 + Phase 1** of the plan at [.claude/plans/i-need-you-to-mighty-hanrahan.md](../../../.claude/plans/i-need-you-to-mighty-hanrahan.md).

- **Phase 0:** foundation (.env, .gitignore, deps)
- **Phase 1:** all 4 external providers + router + cache + budget + MCP
- **Phase 2 (next):** wire DropList retrieval.py → /search
- **Phase 3 (next):** memory-hub REST in front of atlas_query + mirofish
- **Phase 4 (later):** GitHub MCP + n8n cron
- **Phase 5 (later):** Claude skill + CLI shim

## Doctrine alignment

- `assemble-first.md` — every provider is a thin wrapper around the vendor API. No hand-rolled search.
- `feedback_no_tool_sprawl` — one router, one MCP, one CLI. Existing tools stay separate, called through the router.
- `feedback_managed_unlock_over_self_hosted_stealth` — Firecrawl is the managed extract layer; sitepull stealth is opt-in fallback.
