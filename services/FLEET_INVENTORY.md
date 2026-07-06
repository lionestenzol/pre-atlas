# Pre Atlas — Services Fleet Inventory

_Generated 2026-07-05. 20 services · 3,769 files · 253,427 LOC._
_Deterministic counts via repo-inventory; qualitative layer via parallel read-only agents._

## Fleet table (sorted by port)

| Port | Service | What it is | Stack | Status | Runtime deps |
|-----:|---------|------------|-------|--------|--------------|
| 3000 | mosaic-dashboard | Approval/queue frontend for workflow review | React19 + Next16 | ✅ complete | aegis-fabric:3002, Socket.IO |
| 3001 | **delta-kernel** | State-sync + governance engine (behavioral enforcement) | TS + Express | ✅ complete | aegis-fabric, cognitive-sensor, uasc-executor |
| 3002 | **aegis-fabric** | Policy-gated execution + approval queue (human-in-loop gate) | TS + Express | ✅ complete | none (called by many) |
| 3003 | ~~mirofish~~ | Swarm-sim engine, knowledge graph | Python + Neo4j | ⛔ RETIRED → cognitive-sensor | Neo4j, Ollama, cognitive-sensor |
| 3004 | openclaw | Multi-channel messaging gateway (Telegram/Slack/Discord) + Atlas skills | Python + FastAPI | ✅ complete (hollow — backends down) | mosaic-orchestrator☠, cognitive-sensor, mirofish☠ |
| 3005 | ~~mosaic-orchestrator~~ | Platform orchestrator | Python + FastAPI | ⛔ RETIRED → optogon/cortex | delta-kernel, aegis, mirofish, openclaw |
| 3008 | uasc-executor | Execution daemon polling delta-kernel for approved work | Python + FastAPI | 🟡 partial (skeleton, 1 smoke test) | delta-kernel:3001 |
| 3009 | **cortex** | Autonomous execution layer (planner→executor→reviewer, Ghost Executor) | Python + FastAPI | ✅ complete | delta-kernel, aegis, uasc (req); mosaic, optogon, nats (opt) |
| 3010 | optogon | Brain-stem path runtime — directive closure via node graphs | Python + FastAPI | ✅ complete | delta-kernel (opt) |
| 3011 | ws-gateway | NATS event-bus → browser bridge | TS (122 LOC) | 🟡 partial (no tests) | NATS:4222 |
| 3012 | delta-scp | Repo URL → symbolic compression map, job queue | TS + vitest | ✅ complete | Supabase, Postgres |
| 3050 | **canvas-engine** | URL/image → live editable React clone via Claude vision | TS + Express + Anthropic | ✅ complete (84 tests) | web-audit, Anthropic, Vite pool 3060-3069 |
| 3070 | search-stack | Unified search router (Exa/Tavily/Brave/Firecrawl/code-recon/gh) | Python + FastAPI | ✅ complete | external APIs; droplist + cognitive-sensor (memory) |
| 3071 | memory-hub | REST router unifying all memory stores | Python + FastAPI | ✅ complete | droplist, cognitive-sensor, mirofish☠ |
| 3072 | atlas-map-api | Read-only HTTP API over the system map (registry/navigation) | Python + FastAPI | ✅ complete | none (reads snapshots) |
| 3073 | droplist | CLI-first intake engine → normalized Work Packets | Python + FastAPI/CLI | ✅ complete | none (opt litellm) |
| 3074 | triangulation | UI-component verification (spatial/DOM/visual consensus) | Python | 🟡 partial (Phase A only) | numpy; opt torch |
| 3117 | crucix | 27-source OSINT intelligence engine + dashboard | Node + Express | ✅ complete | 27 external APIs, Telegram/Discord |
| 8765 | **cognitive-sensor** | Behavioral intelligence — detects unfinished projects, daily governance | Python + FastAPI + SQLite + ST | ✅ complete | opt droplist, cycleboard, memory_db |
| none | perception | Deterministic webpage perception → Element graph | Python | 🔴 STUB (Step 1/12, all NotImplementedError) | none |

☠ = points at a RETIRED service (stale wiring).

## Status tally

- ✅ **Complete (14):** mosaic-dashboard, delta-kernel, aegis-fabric, openclaw, cortex, optogon, delta-scp, canvas-engine, search-stack, memory-hub, atlas-map-api, droplist, crucix, cognitive-sensor
- 🟡 **Partial (3):** uasc-executor, ws-gateway, triangulation
- 🔴 **Stub (1):** perception
- ⛔ **Retired/superseded (2):** mirofish (→cognitive-sensor), mosaic-orchestrator (→optogon/cortex)

## Dependency map (who calls whom at runtime)

Two load-bearing hubs everything leans on:

```
delta-kernel:3001  ◄── cortex, uasc-executor, optogon, mosaic-orchestrator☠, (mosaic-dashboard via aegis)
cognitive-sensor:8765 ◄── memory-hub, search-stack, openclaw, mirofish☠, delta-kernel
```

Layered view:

```
GOVERNANCE CORE   delta-kernel:3001 ──► aegis-fabric:3002 (approval gate) ──► mosaic-dashboard:3000 (UI)
EXECUTION         cortex:3009 ──► delta-kernel, aegis, uasc-executor:3008 ──► delta-kernel
                  optogon:3010 ──► delta-kernel
INTELLIGENCE      cognitive-sensor:8765 ──► droplist
INTAKE / MEMORY   droplist:3073 · memory-hub:3071 ──► droplist + cognitive-sensor · atlas-map-api:3072 (read-only)
SEARCH            search-stack:3070 ──► droplist + cognitive-sensor + external
MESSAGING / IO    openclaw:3004 (channels) · ws-gateway:3011 (NATS→browser)
PRODUCT / TOOLS   canvas-engine:3050 (THE canvas product) · delta-scp:3012 · crucix:3117 · triangulation:3074 · perception(stub)
RETIRED           mirofish:3003 · mosaic-orchestrator:3005
```

## Stale-wiring cleanup (code-as-furniture)

Live services still pointing at RETIRED ones:
- **openclaw** `config.py` → `orchestrator_url=mosaic-orchestrator:3005` (retired) and channels/scheduler reach `mirofish:3003` (retired). This is why `POST /skills/status` returned `"Could not fetch status: "` — it's calling a dead orchestrator. Should retarget to **cortex:3009** or **optogon:3010**.
- **memory-hub** → health-checks `mirofish` Neo4j (degrades silently, but it's a dead dependency).

## Key facts

- **canvas-engine:3050 is THE product** — the 2026 Wix/Figma canvas play, 90-day commitment (window ends 2026-07-21). Complete, 84 passing tests. It's the one that matters most and it's in good shape.
- **aegis-fabric:3002** is the human-in-loop approval gate (hardened), with a real Next.js UI at mosaic-dashboard:3000.
- Generational churn is the theme: **cortex/optogon replaced mosaic-orchestrator; cognitive-sensor replaced mirofish** — but the retired services still sit on disk and live services still reference them.
