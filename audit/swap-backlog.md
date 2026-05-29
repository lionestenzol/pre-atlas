# Swap Backlog · Top candidates

**Status:** Complete (Track 2A + 2D verified 2026-05-29).

**Source artifacts:**
- [audit/reinvention-surface.json](reinvention-surface.json) — Track 2A sequential walk, 8 candidates from cognitive-sensor / aegis-fabric / uasc-executor / cortex
- [audit/reinvention-A6.json](reinvention-A6.json) — prior-session crucix + ws-gateway scan, 6 candidates
- [audit/swap-candidates.json](swap-candidates.json) — Track 2D ecosystem verification, 14 candidates total: **7 GO / 4 HOLD / 3 SKIP**

**Ranking:** `priority = (value × confidence) / risk`. Top 3 are NEXT-SHIP.

---

## Tier 1 · NEXT-SHIP (Phase 1 spot-checks, locked-in)

| # | Candidate | Library | Confidence | Risk | Priority |
|---|---|---|---|---|---|
| 1 | `services/delta-kernel/src/core/types.ts` Mode FSM + `routing.ts:103-146` Record<Mode, RoutingRule[]> transition table | **xstate** (engine only — 6-mode semantics stay) | HIGH | low-medium | **NEXT-SHIP** |
| 2 | `apps/inpact/onboarding.html` · `goStep(n)` toggling `.active` on `#step-N` divs | **xstate** for flow + plain FormData for inputs | HIGH | low | **NEXT-SHIP** |
| 3 | `apps/inpact/js/screens.js` · manual `state.screen` + `stateManager.update` | **xstate** (same engine as #2 — consolidates flow logic) | HIGH | medium (more callers than onboarding) | **NEXT-SHIP** |

---

## Tier 2 · Verified GO swaps (Track 2A + 2D)

All entries below: library confirmed, license clean, epoch fits subsystem age, no blockers.

| # | Candidate | Library | Confidence | Lines | Notes |
|---|---|---|---|---|---|
| 4 | `services/aegis-fabric/src/observability/logger.ts` | **pino** v10 | HIGH | 48 | ✅ **SHIPPED 2026-05-29 · `3aa8093`** · 31/31 tests · -21 LOC net |
| 5 | `services/aegis-fabric/src/policies/decision-cache.ts` | **lru-cache** v11 | HIGH | 63 | ✅ **SHIPPED 2026-05-29 · `6680440`** · 31/31 tests · parity-true (ttl + ttlAutopurge, no max bound) |
| 6 | `services/cognitive-sensor/agent_excavator.py` + `agent_book_miner.py` `chunk_text()` | **langchain-text-splitters** | HIGH | ~28 (2×14 duplicate) | ✅ **SHIPPED 2026-05-29 · `2e6ef4a`** · 142/142 tests · consolidated into `text_utils.py` · Python 3.13.2 (>=3.10 ✓) |
| 7 | `services/uasc-executor/server.py` | **fastapi** | HIGH | ~64 (handlers) | 4 endpoints; raw `BaseHTTPRequestHandler` with manual JSON dispatch. HMAC middleware ports cleanly via FastAPI DI. |
| 8 | ~~`services/aegis-fabric/src/gateway/rate-limiter.ts`~~ | ~~rate-limiter-flexible~~ | — | — | **DEMOTED to Tier 3 HOLD 2026-05-29 · Session 1** · variable-per-tenant-quota model mismatch + async API + zero test coverage. See Tier 3 #17 below. |
| 9 | `services/cognitive-sensor/triage_server.py` | **fastapi** | MEDIUM | ~77 (handlers) | ✅ **SHIPPED 2026-05-29 · `6328dc1`** · 142/142 tests + 9/9 endpoint smokes · sync handlers in starlette threadpool (no asyncio refactor) · daemon-thread fan-out unchanged · `StaticFiles(html=True)` mount preserves fall-through serving |

---

## Tier 3 · HOLD (block-and-revisit)

| # | Candidate | Library | Why HOLD | Trigger to revisit |
|---|---|---|---|---|
| 10 | `services/cortex/src/cortex/inpact/scheduler.py` | apscheduler **v3** only | APScheduler v4 still pre-release; v3 asyncio rewrite is non-trivial; LOW confidence-swap-safe per 2A | APScheduler v4 reaches stable |
| 11 | `services/crucix/lib/alerts/telegram.mjs` | **grammY** (NOT telegraf) | telegraf last published 2024-03 — 14mo stale. grammY = actively maintained successor (1.26M wk dl · 2025 releases · TS-native) | Confirm grammY covers polling + middleware + dedup needs |
| 12 | `services/crucix/lib/alerts/discord.mjs` | discord.js | A6 didn't fully audit; discord.js already in optional deps — may already be wired correctly | Read `discord.mjs` to confirm hand-roll exists |
| 13 | `services/crucix/lib/delta/memory.mjs` (MemoryManager) | **better-sqlite3** (NOT bullmq) | bullmq adds Redis infra dep; better-sqlite3 closer fit for persistent delta store; OSINT delta semantics non-trivial | Deeper read of memory.mjs + decision on Redis dependency |
| 17 | `services/aegis-fabric/src/gateway/rate-limiter.ts` | rate-limiter-flexible v11 | Hand-roll's `consume(tenantId, maxPerHour, agentId?)` takes the quota PER CALL (lazy-inits a bucket sized to that tenant's quota). rate-limiter-flexible's `RateLimiterMemory` takes `{ points, duration }` at CONSTRUCTION. Modeling the variable-per-tenant-quota would need a `Map<quota, RateLimiterMemory>` wrapper + async API (breaks "callers don't move") + try/catch for reject-as-control-flow. AND zero existing test coverage on the 429 path — `run-tests.ts` doesn't exercise rate limiting. Per assemble-first "no false symmetry": the swap is *worse* + *later* here, not just *later*. | Either (a) tenants converge on a fixed quota tier set (then one limiter per tier works cleanly), or (b) the middleware is rewritten async-first as part of a larger Express-handler refactor, or (c) rate-limit tests are added that establish a parity baseline first |

---

## Tier 4 · SKIP (verified NOT a swap)

- **`services/crucix/lib/llm/index.mjs`** (9-provider LLM factory) — No Node.js library covers all 9 providers including local Ollama at the maturity of litellm (Python-only). Factory is thin (9 lines of provider-select); real cost is per-provider glue which is domain-appropriate. **Promoted to [moat-map.md](moat-map.md).**
- **`services/crucix/dashboard/inject.mjs`** — A6 speculative; proposed libs (recharts, grafana) address visualization, not SSE data injection. Category mismatch until file is fully audited.
- **`services/crucix/server.mjs` SSE broadcast** — A6 LOW severity. Current `Set<Response>` impl is simple, correct, and small. Socket.io migration overhead exceeds value for a broadcast-to-Set pattern.

---

## Tier 5 · Pattern-derived (not in 2A scope, still likely)

These are display-layer concerns 2A explicitly didn't cover (lattice frontend) or weren't found in the Python service scans. Keep open until inspected.

| # | Candidate | Library | Notes |
|---|---|---|---|
| 14 | `apps/lattice/index.html` tree view rendering (graph already uses Cytoscape) | **d3-hierarchy** OR consolidate into Cytoscape's `breadthfirst` layout | Phase 1 didn't reach tree section |
| 15 | `apps/lattice/index.html` timeline view rendering | **vis-timeline** | Phase 1 didn't reach timeline section |
| 16 | Search across inPACT/lattice (memory suggests substring-only) | **fuse.js** or **minisearch** | Not Phase-checked |

---

## What was already correctly assembled (no swap needed)

- `apps/lattice/index.html` **graph view → Cytoscape.js** (vendored line 7, init lines 1672-1694). The audit's founding premise was wrong on this point.
- `services/canvas-engine` validation → **zod + ajv** (no candidates in 2A — confirmed clean)
- `services/cognitive-sensor` embeddings/clustering → **sentence-transformers + hdbscan + umap-learn**
- `services/ws-gateway` → **nats + socket.io** (confirmed clean in A6 — minimal, well-executed)
- `services/cortex` core, `services/optogon`, `apps/code-converter`, `services/perception`, `services/triangulation` — clean in 2A (no solved-category hand-rolls found)
- 15 / 29 indexed subsystems declare a real framework dep (express / fastapi / next / flask / react)

---

## Excluded from backlog

**Retired subsystems** (from [lava-layers.json](lava-layers.json) · cleanup candidates, not swaps):
mirofish · openclaw · mosaic-orchestrator · blueprint-generator · mosaic-dashboard · ai-exec-pipeline

**Moat subsystems** (see [moat-map.md](moat-map.md) — hand-rolls that earn their place):
delta-kernel mode SEMANTICS · PNG-substrate routing · signal→atlas mapping · hash-chain audit · Optogon 5-layer stack · crucix LLM factory (added 2026-05-29)
