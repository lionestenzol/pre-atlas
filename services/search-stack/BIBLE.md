# search-stack BIBLE

The contract. Mirrors the `services/droplist/BIBLE.md` style.

## §1 Identity

search-stack is **one router + N providers + one MCP**. It is not a search engine. It does not index the web. It does not maintain a corpus. It dispatches a query to the right provider(s) and merges the results.

## §2 Inputs

- HTTP `POST /search {q, kind?, max_results?, providers?}` from any client (curl, Claude via MCP, n8n)
- HTTP `POST /extract {url, mode?}` for single-page extraction
- All inputs validated by Pydantic at the boundary

## §3 Outputs

- `SearchResult` — `{title, url, snippet, score, source, kind, ts, raw}` (see `providers/base.py`)
- `ExtractResult` — `{url, content, mode, ts, raw}`
- `BudgetSnapshot` — `{provider, used, quota, percent, blocked}`

## §4 Providers

Each provider lives in its own file in `src/search_stack/providers/`. Each provider:

1. Reads its API key from env at instantiation time
2. If key missing → reports `DISABLED` status, never raises
3. Implements `async search(query, max_results) -> list[SearchResult]`
4. Calls `budget.consume(provider_name, count=1)` before the HTTP call
5. Honors a hard timeout (15s default)
6. Maps vendor responses to `SearchResult` — never leaks raw vendor schemas to callers

Adding a new provider is one new file + one entry in `router.PROVIDERS`.

## §5 Router

Intent classification is **rule-based first**. See `router.classify()`:

- URL pattern → `kind=extract`
- `site:github.com` or `repo:` → `kind=github`
- `path:` or `file:` prefix → `kind=file`
- `rg:` / `fd:` / `sg:` operator prefix → `kind=code`
- Default → `kind=web`

Explicit `kind=` from the caller always wins over inferred.

Per kind, providers are tried in declared order. First N successful results are merged and reranked.

## §6 Budget

Per-provider quota tracked in `data/budget.db` (SQLite, one row per provider per month):

```text
provider | month  | count | quota | blocked_at
```

`consume()` increments count atomically. At `count >= quota * (BUDGET_BLOCK_PERCENT/100)` (default 80%), the provider's `enabled` flag flips to false for the rest of the month. `GET /budget` shows live state.

## §7 Cache

`cache.db` (SQLite) keyed by SHA256 of `(provider, kind, query, max_results)`. TTL configurable per kind (default 1h for web, 24h for github, no cache for extract). Cache misses on `force_fresh=true` request flag.

## §8 Storage

- `data/budget.db` — per-provider request counts (monthly)
- `data/cache.db` — query result cache
- `data/audit.jsonl` — every request/response one line (for debugging + future reranker training)

All three are git-ignored.

## §9 Error handling

- Provider HTTP error → that provider returns empty list, log to audit.jsonl, other providers continue
- All providers fail → empty result list with `errors` field populated
- Budget block → that provider skipped silently, others continue
- Network total failure → 503 with `{providers_attempted, providers_failed}` payload

## §10 Security

- Keys read from `.env` only, never logged
- `.env` git-ignored (root `.gitignore` line 102)
- Service binds `127.0.0.1` by default (no LAN exposure)
- No auth on REST surface (localhost-only assumption)
- If exposed beyond localhost, add bearer-token middleware first

## §11 Observability

- `GET /healthz` → `{status, providers: [{name, enabled, last_check}]}`
- `GET /budget` → live quota state
- `data/audit.jsonl` is the source of truth for "what did the service do today"

## §12 MCP surface

Three tools exposed via `mcp_server.py`:

```text
search_stack_search(query: str, kind?: str, max_results?: int = 10) -> list[SearchResult]
search_stack_extract(url: str, mode?: str = "markdown") -> ExtractResult
search_stack_budget() -> list[BudgetSnapshot]
```

Names are deliberately verbose. They will appear in Claude's tool palette across every session and must be unambiguous.

## §13 Integration seams

- **DropList** (Phase 2): `POST /memory/save` accepts a `SearchResult` and the URL of a DropList intake. Persists as `intel_drop` packet.
- **cognitive-sensor** (Phase 3): provider `memory.py` will import `atlas_query` as library and call its embedding search.
- **mirofish** (Phase 3): provider `memory.py` will also query the Neo4j client for 1-hop neighbors.
- **n8n** (Phase 4): `SEARCH_STACK_N8N_URL` env var enables fire-and-forget POST after each `/search`.

## §14 Doctrine alignment

- `assemble-first.md` — every layer assembles maintained libraries / vendor APIs.
- `feedback_no_tool_sprawl` — one router, one MCP. Providers are files, not services.
- `feedback_managed_unlock_over_self_hosted_stealth` — Firecrawl > Scrapling stealth for extraction.
- `code-as-furniture.md` — bugs fixed inline, not documented.

## §15 Open questions

- **OQ-1** — Reranker quality: cross-provider dedup + score merge is naive (highest score wins). When/if quality matters, swap `rerank.py` for an embedding-based reranker. Hook is local to one file.
- **OQ-2** — Audit log retention: `audit.jsonl` grows unbounded. Add weekly rotation when file crosses 100MB.
- **OQ-3** — Phase 3 memory provider — should it be a sub-service (`memory-hub`) or a provider module? Current plan: sub-service for testability.
- **OQ-4** — Free-tier quotas reset monthly per provider but month-boundaries differ. Use UTC first-of-month for everyone. Document if any vendor resets on a different schedule.
