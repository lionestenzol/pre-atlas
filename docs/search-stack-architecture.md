# Search Stack — Architecture

Layered search system spanning 16 categories: human answers, agent APIs, deep research, code, files, web crawl, business, products, local, social, multimedia, news, legal, data, memory, automation.

This doc captures the architecture; the implementation plan is at [.claude/plans/i-need-you-to-mighty-hanrahan.md](../.claude/plans/i-need-you-to-mighty-hanrahan.md). For the operational protocol on how agents use the tools, see [search-protocol.md](search-protocol.md). For the inventory of repo-local tools, see [repo-search-stack.md](repo-search-stack.md).

---

## The 16 layers, mapped to what we have

| Layer | Category | Tool today | State |
|---|---|---|---|
| L1 | Human answer search | (Codex delegate) | deferred |
| **L2** | **Agent search APIs** | **Exa + Tavily + Brave (search-stack)** | **Phase 1 — this build** |
| L3 | Deep research | (covered by L2) | deferred — academic Phase 6+ |
| L4 | Code & technical | `repo-search` skill + es/rg/fd/sg/semgrep | working |
| L4b | GitHub | gh CLI + search-stack `kind=github` | Phase 1 |
| L5 | Personal file | `es` (Everything CLI) | working |
| **L6** | **Web crawl & extract** | **Firecrawl (managed) + sitepull + scrapling + anatomy-ext** | **Firecrawl new Phase 1** |
| L7 | Business / competitor | competitor-monitor MCP | working |
| L8-L14 | Product/Local/Social/Multimedia/News/Legal/Data | — | deferred |
| L12-news | News | Tavily `category=news` | covered in Phase 1 |
| L15 | Memory infra | droplist + cognitive-sensor + mirofish | unified in Phase 3 |
| L16 | Automation | n8n (cron + fan-out) | Phase 4 |

---

## Architecture (Phase 1 end state)

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT (Claude session, curl, n8n, DropList, future CLI)   │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP / MCP
                     ▼
        ┌────────────────────────────────────┐
        │  search-stack :3070                │
        │  ┌───────────────────────────────┐ │
        │  │  FastAPI REST + FastMCP       │ │
        │  │  POST /search                 │ │
        │  │  POST /extract                │ │
        │  │  GET  /budget                 │ │
        │  │  POST /memory/save            │ │
        │  └───────────────────────────────┘ │
        │  ┌───────────────────────────────┐ │
        │  │  router.classify(query)       │ │
        │  │  → kind ∈ {web,extract,code,  │ │
        │  │     github,file,memory}       │ │
        │  └─────────────┬─────────────────┘ │
        │  ┌─────────────▼─────────────────┐ │
        │  │  cache.get / cache.put        │ │
        │  │  budget.consume / .snapshot   │ │
        │  └─────────────┬─────────────────┘ │
        │  ┌─────────────▼─────────────────┐ │
        │  │  providers dispatched         │ │
        │  └─────────────┬─────────────────┘ │
        └────────────────┼───────────────────┘
                         │
         ┌───────────────┼───────────────┬─────────────────┬───────────────┐
         ▼               ▼               ▼                 ▼               ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐      ┌──────────┐    ┌──────────┐
   │ EXTERNAL │    │ EXTRACT  │    │  LOCAL   │      │  GITHUB  │    │  MEMORY  │
   │  (web)   │    │          │    │          │      │          │    │ (Phase 3)│
   │ exa      │    │ firecrawl│    │ rg/fd/sg │      │ gh CLI   │    │ atlas_q  │
   │ tavily   │    │  ↓ fallbk│    │  (rg etc)│      │          │    │ mirofish │
   │ brave    │    │ sitepull │    │ es (file)│      │          │    │ droplist │
   └──────────┘    └──────────┘    └──────────┘      └──────────┘    └──────────┘
```

### Why one router on top, not merged tools

Each existing tool owns a distinct seam:

- **sitepull** — whole-site clone (asset capture, generates a runnable local replica)
- **scrapling** — page-level structured extraction (durable selectors, adaptive)
- **anatomy-extension** — live-tab DOM inspection (computed style, paint order)
- **repo-search** — local code (file/AST queries via es/rg/fd/sg)
- **competitor-monitor** — long-running intel snapshots over a known target list

Merging them into one binary would create a lava layer (see `feedback_no_tool_sprawl`). Instead, the router knows the seam each owns and dispatches by intent. Users get a unified surface (one `POST /search`, one `search_stack_search` MCP tool); the tools stay separate and swappable.

### Why these 4 external providers

- **Exa** — neural/semantic; strong for "find me sources that mean X" rather than literal keyword
- **Tavily** — real-time + news; strong for freshness, `category=news/finance` built in
- **Brave** — broad independent index; SEO-resistant; good privacy
- **Firecrawl** — managed extract; complements sitepull (full clone) for one-off page → markdown

The combination covers semantic / fresh / broad / extract — the four bands the assemble-first doctrine recommends for agent-search workflows.

### Why we deliberately skip these (for now)

| Skipped | Why |
|---|---|
| SerpAPI / DataForSEO | Brave + Exa + Tavily cover the bands; SerpAPI = paid Google fallback, add on miss |
| Kagi / Perplexity native | Human-search products — delegate via codex-delegate if needed |
| Apify / Browserless | sitepull + scrapling + brightdata already cover crawl |
| Reddit / X / TikTok | Out of scope for v1; add when a real social-monitor workflow surfaces |
| Crunchbase / PitchBook / Apollo / Clay | Paid SaaS — add only when a real lead-gen workflow is live |
| Scholar / arXiv / PubMed / Consensus / Elicit | Tavily + Exa cover most research queries; add academic when reviews become recurring |

---

## Data flow per request

```
POST /search {q: "react server components"}
        │
        ▼
router.classify(q) → kind=web (no URL, no prefix)
        │
        ▼
registry.providers_for("web") → [exa, tavily, brave]
        │
        ▼
for each provider:
    cache.get(provider, "web", q, 10)? → hit: append cached
                                       → miss: budget.consume(provider, quota)
                                              → blocked? → skip
                                              → else: provider.search(q, 10)
                                                       → cache.put(...)
                                                       → audit.log(...)
        │
        ▼
dedup_by_url → sort by score → top 10
        │
        ▼
{kind, results, providers_used, providers_failed, n}
```

---

## File map

```
services/search-stack/
├── .env.example              # required keys
├── README.md                 # quick start
├── BIBLE.md                  # contract
├── pyproject.toml            # FastAPI + FastMCP + httpx + pydantic
├── data/                     # gitignored — runtime SQLite + audit log
│   ├── budget.db
│   ├── cache.db
│   └── audit.jsonl
├── src/search_stack/
│   ├── settings.py           # env config (pydantic-settings)
│   ├── audit.py              # append-only JSONL log
│   ├── budget.py             # per-provider quota SQLite
│   ├── cache.py              # SHA256-keyed TTL SQLite
│   ├── router.py             # intent classifier + dispatch
│   ├── registry.py           # singleton providers, kind→providers map
│   ├── server.py             # FastAPI REST surface :3070
│   ├── mcp_server.py         # FastMCP wrapper
│   └── providers/
│       ├── base.py           # SearchResult / ExtractResult / SearchProvider ABC
│       ├── exa.py
│       ├── tavily.py
│       ├── brave.py
│       ├── firecrawl.py
│       ├── repo_search.py    # shells out to rg/fd/sg
│       ├── local_file.py     # shells out to es
│       └── github.py         # shells out to gh CLI
└── tests/
    ├── test_router.py        # classifier rules
    ├── test_cache.py         # TTL roundtrip
    ├── test_budget.py        # consume + block
    └── test_providers_smoke.py  # gated on env, live API hits
```

---

## Adding a new provider

1. Create `src/search_stack/providers/<name>.py` subclassing `SearchProvider` or `ExtractProvider`
2. Implement `_check_enabled()` (env-key presence) and `async search(...)` / `extract(...)`
3. Add singleton to `registry._search_singletons`
4. Add to `KIND_TO_PROVIDERS` for the kind(s) it serves
5. If metered, add `consume()` call + quota to settings + `PROVIDER_QUOTAS`

No router changes, no MCP changes. The provider appears in `/healthz` and `/budget` automatically.

---

## Phases beyond this build

- **Phase 2** — Wire `services/droplist/retrieval.py` to call `localhost:3070/search` before its token-overlap fallback. Persist external hits as `intel_drop` packets. Closes BIBLE §15 OQ-10.
- **Phase 3** — Build `services/memory-hub/` (thin FastAPI in front of atlas_query + mirofish + idea_registry + droplist). Register as `kind=memory` provider in the router.
- **Phase 4** — GitHub GraphQL provider (faster than gh CLI for bulk). n8n cron workflow that runs daily searches against a tracked-topic list → saves to DropList.
- **Phase 5** — Claude skill `~/.claude/skills/search-stack/` with decision tree. `pre-atlas search "..."` CLI shim.

---

## Doctrine alignment

- ✅ `assemble-first.md` — every provider is a thin wrapper around a vendor API; cache and budget use SQLite (stdlib); FastAPI / FastMCP / httpx / Pydantic are mature defaults.
- ✅ `code-as-furniture.md` — Phase 0 left a task chip for fixing web-audit dev/global drift rather than silently shipping on top of it.
- ✅ `feedback_no_tool_sprawl` — one router, one MCP, one CLI surface. Each provider is one file.
- ✅ `feedback_managed_unlock_over_self_hosted_stealth` — Firecrawl is the managed extract layer; scrapling stealth only on explicit opt-in.
- ✅ TGT Law — droplist + cognitive-sensor + mirofish (TREE+GRAPH+TIME) all stay load-bearing; UI is Phase 5.
- ✅ Context cadence — Phase 1 ships in one session well under the 25% ceiling.
