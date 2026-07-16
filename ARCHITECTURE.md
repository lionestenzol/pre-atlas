# Pre Atlas — Architecture

> Portable architecture reference. No prior context required.
> For onboarding walkthroughs, see [ONBOARDING.md](ONBOARDING.md).
> For the raw inventory (LOC counts, port map, reconciliation), see [REPO_RUNDOWN.md](REPO_RUNDOWN.md).
> For architectural decisions and their rationale, see [DECISIONS.md](DECISIONS.md).

---

## What this system is

Pre Atlas is a **personal behavioral-governance system** built as a federated monorepo. It analyzes a single user's AI conversation history (~94K messages) to determine what they should be doing right now and whether they are allowed to start something new.

A deterministic TypeScript state engine (`delta-kernel`) is the hub. Everything else is a spoke that reads from it or writes signals back to it over one-way HTTP seams. A Python analysis pipeline (`cognitive-sensor`) turns conversation history into state. A set of autonomous executors (`cortex`, `optogon`, `droplist`) can act on that state behind default-off environment gates. UIs (`inpact`, `lattice`, dashboards) project the state for the human.

The architecture is **hub-and-spoke over SQLite + HTTP**, not an event bus. Most "pipelines" are reads. Most automation is dormant or gated off by design.

---

## Core abstraction: the 6-mode FSM

Every decision in the system flows through a deterministic finite state machine with six modes:

```
RECOVER -> CLOSURE -> MAINTENANCE -> BUILD -> COMPOUND -> SCALE
```

| Mode | Meaning | What it gates |
|---|---|---|
| RECOVER | Sleep-deprived. Rest only. | All work blocked. |
| CLOSURE | Too many open loops. | No new projects until loops close. |
| MAINTENANCE | Light admin. | No new builds. |
| BUILD | Earned the right to create. | Ship something. |
| COMPOUND | Extend what's built. | Stack wins on existing work. |
| SCALE | Delegate and automate. | Operating well. |

Mode is computed from 5 signals: `sleep_hours`, `open_loops`, `assets_shipped`, `deep_work_blocks`, `money_delta`. Each signal is bucketed (LOW/OK/HIGH) and fed through a pure lookup table. No randomness. No AI judgment.

Implementation: `services/delta-kernel/src/core/routing.ts` (signals to buckets to LUT to mode). Type definitions for all 6 modes: `services/delta-kernel/src/core/types.ts`. Every `Record<Mode, ...>` in the codebase must include all 6.

---

## Hub-and-spoke topology

```
                         +----------------------------+
   lattice ----------->  |                            |
   inpact ------------>  |                            |  <---- cognitive-sensor
   droplist ---------->  |       delta-kernel         |  <---- canvas-engine <-- crucix
   cortex <-- optogon >  |   (deterministic hub)      |  <---- code-converter
   aegis-fabric ------>  |      state . 6-mode        |  <---- ws-gateway
   uasc-executor ----->  |          FSM               |  <---- cognitive-sensor
                         +----------------------------+
   droplist --> search-stack        perception --> triangulation
   lattice  --> cognitive-sensor    mosaic-dashboard --> mosaic-orchestrator --> optogon
   inpact   --> cortex
```

**All edges are one-way HTTP.** There is no shared database between services, no event bus, no message queue. Services communicate through JSON over HTTP, validated by JSON Schema contracts at every seam.

**delta-kernel (port 3001) is the single source of truth.** When in doubt about where state lives, it's there (SQLite via better-sqlite3, with a libSQL driver shim behind the `DELTA_DB_DRIVER=libsql` flag).

---

## The spine loop

The core data cycle from sensing to action to reflection:

```
cognitive-sensor (analyze conversation history)
       |
       v
optogon / cortex (propose / execute -- GATED, off by default)
       |
       v
droplist (packetize into DAG execution units)
       |
       v
delta-kernel (commit state change as hash-chained delta)
       |
       v
lattice / inpact (project state for the human)
```

---

## Data pipeline

Daily (or on-demand), the cognitive-sensor pipeline runs:

```
results.db (94K messages, 107MB, git-ignored)
    |
    +-- loops.py -----------> Detect open loops (intent vs completion scoring)
    +-- completion_stats.py -> Compute closure ratio
    +-- route_today.py ------> Determine mode (CLOSURE/BUILD/etc)
    |
    v
cognitive_state.json --> export_daily_payload.py --> daily_payload.json
    |
    v
build_projection.py --> data/projections/today.json
    |
    v
push_to_delta.py -----> POST /api/ingest/cognitive --> delta-kernel
    |
    v
routing.ts ------------> Bucket signals -> LUT lookup -> Mode update
    |
    v
.delta-fabric/entities.json (persisted)
.delta-fabric/deltas.json   (append-only audit log)
```

---

## Governance daemon

Runs inside the delta-kernel process. Schedules autonomous governance jobs:

| Schedule | Job | Purpose |
|---|---|---|
| Every 5 min | heartbeat | Health check |
| Every 15 min | mode_recalc | Re-evaluate mode from current signals |
| Every 1 hour | refresh | Re-run cognitive-sensor pipeline |
| Every 1 min | work_queue | Process work admission requests |
| 06:00 | day_start | Reset daily counters |
| 22:00 | day_end | Reset streaks |

Implementation: `services/delta-kernel/src/governance/governance_daemon.ts`.

---

## State model

All state mutations are **append-only, hash-chained JSON Patches (RFC 6902)**. You can reconstruct any entity's state by replaying its deltas from the beginning.

- Current state: `.delta-fabric/entities.json` (24 entity types)
- Audit log: `.delta-fabric/deltas.json` (append-only, hash-chained)
- Type definitions: `services/delta-kernel/src/core/types.ts` (1,162 lines, 24 entity types)
- Delta creation and application: `services/delta-kernel/src/core/delta.ts`

Design choices inherited from the ATM (Asynchronous Temporal Mesh) target architecture: hash-chained deltas correspond to the ATM's "Sundial" timestamping; `DEFAULT_MAX_PACKET_BYTES = 220` in `delta-sync.ts` reflects LoRa-safe packet sizing; no blobs and deterministic conflict resolution are ATM transport constraints. See [DECISIONS.md](DECISIONS.md) ADR-010.

---

## Contracts

`contracts/schemas/` holds **50 JSON Schema (draft-07) data contracts** that validate data at every service seam:

- `Signal.v1`, `Directive.v1`, `TaskPrompt.v1`, `BuildOutput.v1`, `CloseSignal.v1`, `AtlasArtifact.v1`
- 7 `Aegis*` contracts (Agent, Policy, Tenant, Approval, Action, Decision, Webhook)
- State-store schemas (`CognitiveMetricsComputed`, `DailyPayload.v1`, `DailyProjection.v1`, `Closures.v1`)

These are the typed wire format. Services do not share databases or in-process types -- they share schemas.

---

## Trust boundary

**Capability and trust change only by source-diff + redeploy. Never by a runtime request.**

The action surface is closed by source: delta-kernel's `ActionType` is 7 fixed strings (`types-core.ts:263-270`), enforced at execution. UASC executor has 10 tokens seeded once in `schema.sql`. No runtime path can register, approve, or unlock a new action, token, or capability. See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for the full rule and verification table.

---

## Automation state

Most automation is off by design:

| System | State | Detail |
|---|---|---|
| delta-kernel | active | Governance daemon, 9 cron jobs, */5 heartbeat |
| droplist | on-demand | Drop-to-packet-to-DAG, not auto-scheduled |
| cortex | gated | Acts only if `CORTEX_BRIDGE_APPLY=1` (default off) |
| optogon | gated | Writes back only if `AUTO_TRIAGE_APPLY=1` (default off) |
| cognitive-sensor | dormant | Triage arm unscheduled; hand-cranked |

12 of 35 systems are flagged for autostart. The rest are manual.

---

## System catalog

### Services (19 systems)

| System | Purpose | Lang | Port | LOC |
|---|---|---|---:|---:|
| **delta-kernel** | Deterministic state engine, 6-mode FSM, the API hub | TS/Express | 3001 | 35,043 |
| **cognitive-sensor** | Conversation-analysis pipeline, idea registry, state store | Py/FastAPI | -- | ~116K* |
| **aegis-fabric** | Admin gateway, API middleware, policy/approval | TS/Express | 3002 | 12,378 |
| **droplist** | Capture to packet to DAG execution engine | Py/FastAPI | 3073 | 9,151 |
| **mosaic-orchestrator** | FastAPI orchestrator (legacy) | Py/FastAPI | -- | 7,578 |
| **canvas-engine** | URL to live React clone via in-process Vite pool | TS/Express | 3060 | 7,001 |
| **cortex** | Autonomous execution layer (gated) | Py/FastAPI | -- | 3,952 |
| **optogon** | Autonomous executor, preference seeding, signal emission | Py/FastAPI | 3010 | 3,949 |
| **search-stack** | Router over 28 search providers | Py/FastAPI | 3070 | 3,376 |
| **mirofish** | Prediction engine, neo4j-dep (legacy) | Py/FastAPI | -- | 2,933 |
| **uasc-executor** | UASC command executor, HMAC auth | Py | 3008 | 2,248 |
| **mosaic-dashboard** | Next.js dashboard (legacy) | TS/Next | 3000 | 2,137 |
| **atlas-map-api** | GPS substrate API (the map behind the describe/call gateway) | Py/FastAPI | 3072 | 2,085 |
| **crucix** | Dashboard server | HTML/Express | -- | 1,951 |
| **triangulation** | Phase B stub (never launched) | Py/FastAPI | -- | 1,294 |
| **openclaw** | FastAPI service (legacy) | Py/FastAPI | -- | 918 |
| **perception** | Phase A stub | Py | -- | 832 |
| **memory-hub** | Memory aggregation | Py/FastAPI | 3071 | 558 |
| **ws-gateway** | WebSocket gateway (NATS to socket.io) | TS | 3006 | 122 |

\* cognitive-sensor LOC is data-inflated (~half JSON state dumps). Actual Python source is a fraction.

### Apps (7 UIs)

| App | Purpose | Lang | LOC |
|---|---|---|---:|
| **lattice** | Viewmodel projection: tree/graph/timeline (vendors Cytoscape) | JS | 12,506 |
| **inpact** | Daily-flow UI, onboarding, cycleboard | JS | 11,066 |
| **webos-333** | Experimental | HTML | 3,442 |
| **code-converter** | Python to C++ converter, AST engine | Py/FastAPI | 1,254 |
| **blueprint-generator** | Next.js blueprint UI (legacy) | JS/Next | 979 |
| **ai-exec-pipeline** | AI execution pipeline (legacy) | Py/Flask | 455 |
| **canvas-demo** | Programmatic Remotion vs dummy site | TS/React | 254 |

### Tools (5 owned)

| Tool | Purpose | LOC |
|---|---|---:|
| **anatomy-extension** | Chrome MV3 anatomy-capture extension | 5,293 |
| **fest-reconcile** | Festival manifest reconciler | 3,169 |
| **atlas-cli** | `atlas where/locate/path/...` CLI over the map | 627 |
| **atlas-audit** | Audit pipeline and system-index generator | 236 |
| **codex-partner** | Codex companion tooling | 211 |

### Lifecycle

- **New:** droplist, memory-hub, search-stack, atlas-audit, reminders
- **Retired** (candidates for removal): mirofish, openclaw, mosaic-dashboard, mosaic-orchestrator, blueprint-generator, ai-exec-pipeline

---

## Formal vocabulary mapping

Pre Atlas maps to four established patterns from autonomic computing, AI agent theory, behavior-based robotics, and physiological regulation:

### MAPE-K (Kephart and Chess, 2003)

| MAPE-K phase | Pre Atlas component |
|---|---|
| Monitor | cognitive-sensor (conversation analysis) |
| Analyze | cognitive-sensor (scoring, loop detection) |
| Plan | delta-kernel `directive.ts` (strategic directives) |
| Execute | cortex Ghost Executor (gated) |
| Knowledge | `state.json` + `preferences` + `contracts/schemas/` |

### BDI (Rao and Georgeff, 1995)

| BDI concept | Pre Atlas mapping |
|---|---|
| Beliefs | `state.context` (current world model) |
| Desires | Goal entities in state |
| Intentions | Atlas Directives, routed to cortex for execution |

### Subsumption (Brooks, 1986)

Optogon's signal paths act as a reflex layer (fast, reactive). Delta-kernel's mode FSM and governance daemon are the deliberative layer (slow, principled). The reflex layer is gated behind `AUTO_TRIAGE_APPLY=1` -- it cannot override the deliberative layer without explicit activation.

### Homeostatic regulation

The 6-mode FSM represents homeostatic setpoint regimes. Each mode defines what the system considers "normal" for that operating condition. Mode transitions are triggered by signal deviations (open loops too high, sleep too low), exactly as a thermostat switches regimes based on temperature deviation from setpoint.

---

## Key API endpoints

### delta-kernel (port 3001)

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/state` | Current system state |
| PUT | `/api/state` | Update system state |
| GET | `/api/state/unified` | Merged delta + cognitive state |
| POST | `/api/ingest/cognitive` | Ingest cognitive metrics |
| GET/POST | `/api/tasks` | List / create tasks |
| POST | `/api/law/close_loop` | Record a closure event |
| GET | `/api/daemon/status` | Daemon state + job history |
| POST | `/api/daemon/run` | Manually trigger a daemon job |
| GET | `/api/actions/pending` | Pending governance actions |
| POST | `/api/actions/confirm/:id` | Confirm a pending action |
| POST | `/api/actions/cancel/:id` | Cancel a pending action |

Auth: `Authorization: Bearer <token>` (fetched from `POST /api/auth/token`) when `.aegis-tenant-key` exists. Dev mode with no key file skips auth.

### aegis-fabric (port 3002)

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/agent/action` | Submit agent action for policy evaluation |
| GET | `/api/v1/policies` | Get policy rules |
| POST | `/api/v1/policies/simulate` | Test a policy without side effects |
| GET/POST | `/api/v1/approvals` | List / approve pending human approvals |
| GET | `/api/v1/state/entities` | List entities by type |
| GET | `/health` | Health check |

---

## Repo layout

```
Pre Atlas/
+-- services/           # 19 systems (the engine room)
|   +-- delta-kernel/   # TS state engine (port 3001) -- THE HUB
|   +-- cognitive-sensor/  # Py analysis pipeline
|   +-- aegis-fabric/   # TS policy gate (port 3002)
|   +-- droplist/       # Py capture-to-DAG
|   +-- cortex/         # Py autonomous executor (gated)
|   +-- optogon/        # Py signal executor (gated)
|   +-- search-stack/   # Py search router
|   +-- atlas-map-api/  # Py GPS substrate
|   +-- canvas-engine/  # TS URL-to-React cloner
|   +-- memory-hub/     # Py memory aggregation
|   +-- uasc-executor/  # Py UASC command executor
|   +-- ws-gateway/     # TS WebSocket gateway
|   +-- (+ 7 legacy/stub services)
+-- apps/               # 7 UIs (the human surface)
|   +-- inpact/         # Daily-flow UI (port 3006)
|   +-- lattice/        # Tree/graph/timeline projection
|   +-- (+ 5 others)
+-- contracts/schemas/  # 50 JSON Schema (draft-07) data contracts
+-- tools/              # 5 owned tools + vendored anatomy-research
+-- scripts/            # PowerShell launchers
+-- data/               # Runtime artifacts (projections)
+-- .delta-fabric/      # Shared state (entities + deltas)
+-- research/           # UASC-M2M symbolic encoding
+-- doctrine/           # Governance doctrine documents
+-- audit/              # System index + audit artifacts
```

Numbers: ~3,400 files, ~302,000 LOC owned (excluding 574K vendored and ~28K build output).

---

## Known caveats

1. **`tsc` will fail.** Pre-existing type errors in several files. Runtime works via `tsx` which bypasses strict type checking.
2. **Hash chain forks exist.** 10 documented fork points in `.delta-fabric/deltas.json` from concurrent writes without file locking. See `HASH_CHAIN_FORKS.md`.
3. **Modules 6-11 are stubs.** Delta Sync, Off-Grid, UI Streaming, Camera, Audio, and Actuation are deterministic simulations only. No real hardware.
4. **`results.db` is 107MB and git-ignored.** Contains all conversation data. Required for cognitive pipeline. Won't exist on fresh clone.
5. **Windows-only automation.** All scripts are `.ps1`/`.bat`. No Unix equivalents.

---

## Related documents

| Document | What it covers |
|---|---|
| [DECISIONS.md](DECISIONS.md) | Architectural decision log (ADR format) |
| [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) | Capability/trust closure rule and verification |
| [REPO_RUNDOWN.md](REPO_RUNDOWN.md) | Raw inventory with LOC counts, port reconciliation |
| [ONBOARDING.md](ONBOARDING.md) | Step-by-step setup and walkthrough |
| [CLAUDE.md](CLAUDE.md) | Agent front-door (atlas-map MCP, atlas-ai CLI, REST) |
| `services/delta-kernel/ARCHITECTURE_MAP.md` | Delta lifecycle, routing lifecycle, sync lifecycle |
| `services/delta-kernel/specs/` | 19 module specifications |
| `services/cognitive-sensor/SYSTEM_MAP.md` | Cognitive sensor data flow and layers |
| `contracts/schemas/` | All 50 JSON Schema data contracts |
