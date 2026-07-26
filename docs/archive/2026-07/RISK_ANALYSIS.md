# Pre Atlas — Static Architectural Risk Analysis

Generated: 2026-03-10
Method: Repository inspection of imports, subprocess calls, data flows, and state access patterns.

---

## 1. Cyclic Dependencies

### 1.1 Triple Mode Routing Implementation
Three independent implementations compute operational mode with **different thresholds and signal sets**:

| Implementation | Location | Thresholds | Signal Set |
|---|---|---|---|
| `routing.ts` | `services/delta-kernel/src/core/routing.ts` | sleep<6→RECOVER, loops≥4→CLOSURE, assets≥2→COMPOUND | sleep, open_loops, assets_shipped, deep_work_blocks, money_delta |
| `lut.ts` | `services/delta-kernel/src/core/lut.ts` | sleep≥7=OK, loops≤3=CLEAR, leverage>10=HIGH | sleep, open_loops, leverage_balance, streak_days, pending_actions |
| `route_today.py` / `export_daily_payload.py` | `services/cognitive-sensor/` | ratio<15→CLOSURE, open>20→CLOSURE, open>10→MAINTENANCE | closure.ratio, closure.open |

**Risk**: Mode could diverge depending on which code path is hit. The daemon uses closure_ratio thresholds (0.4/0.6/0.8) which differ from both TypeScript implementations.

### 1.2 Circular Orchestration
```
governance_daemon.ts (every 1hr) → spawns → refresh.py
refresh.py (step 5)             → writes  → daily_payload.json
push_to_delta.py                → POSTs   → server.ts /api/ingest/cognitive
server.ts                       → updates → .delta-fabric/ entities
governance_daemon.ts (every 15min) → reads → .delta-fabric/ + cognitive_state.json
```
The daemon spawns the pipeline that feeds back into the daemon's own state. No explicit cycle guard exists.

---

## 2. Duplicated Responsibilities

### 2.1 Delta Engine Duplication
- `services/delta-kernel/src/core/delta.ts` — Original delta operations
- `services/aegis-fabric/src/core/delta.ts` — Copy with identical API

Both implement: `createEntity()`, `createDelta()`, `applyPatch()`, `hashState()`, `generateUUID()`. No shared package. Changes to one require manual sync to the other.

### 2.2 Mode Routing Duplication (see 1.1)
- `route_today.py` and `export_daily_payload.py` contain identical routing logic (both check ratio<15, open>20, open>10)
- Both files are called in the same refresh.py pipeline (steps 4 and 5)
- One writes `daily_directive.txt`, the other writes `daily_payload.json`

### 2.3 Types Duplication
- `services/delta-kernel/src/core/types.ts` — 1162 lines, defines Mode enum and all entity types
- `services/aegis-fabric/src/core/types.ts` — Separate Mode enum definition, AegisEntityType enum
- No shared types package despite both using the same Mode enum values

### 2.4 Parallel Orchestration Paths
- `refresh.py` — 10-step pipeline (called by daemon and run_all.ps1)
- `run_daily.py` — 8-step pipeline (5 overlap with refresh.py, adds governor_daily.py)
- `atlas_agent.run_daily()` — Calls same scripts via subprocess
- Three entry points for substantially overlapping script sequences

---

## 3. State Coupling

### 3.1 Cross-Language File Coupling (No Locking)
Python (cognitive-sensor) writes → TypeScript (delta-kernel) reads, via plain JSON files:

| File | Writer | Reader | Lock? |
|---|---|---|---|
| `cognitive_state.json` | `export_cognitive_state.py` | `server.ts`, `governance_daemon.ts` | No |
| `loops_latest.json` | `loops.py` | `server.ts` | No |
| `closures.json` | `server.ts` | `governance_daemon.ts` | No |
| `daily_payload.json` | `export_daily_payload.py` | CycleBoard JS | No |

**Risk**: Concurrent daemon cron (every 15min) and refresh.py (hourly) can read/write the same files simultaneously.

### 3.2 Hash Chain Integrity Without Locking
`.delta-fabric/deltas.json` is an append-only hash chain. Both `server.ts` (HTTP request handlers) and `governance_daemon.ts` (cron jobs) can append simultaneously.

**Known Issue**: 10 fork points documented in `HASH_CHAIN_FORKS.md`. Fork detection exists but no automatic resolution.

### 3.3 CycleBoard Brain Directory
`wire_cycleboard.py` copies files to `cycleboard/brain/`. CycleBoard reads from `brain/`. If the copy is interrupted (process killed during copy), brain state is partial.

---

## 4. Hidden Orchestration Points

### 4.1 Daemon Spawning Python
`governance_daemon.ts` spawns `refresh.py` as a child process with 120-second timeout:
```typescript
// Inside runRefresh():
child_process.spawn('python', ['refresh.py'], { timeout: 120000 })
```
If Python fails silently, the daemon logs it but continues. No retry logic.

### 4.2 atlas_agent.py Spawning Everything
`atlas_agent.py._run()` calls `subprocess.check_call()` for every script. It suppresses stdout (`DEVNULL`) and only captures stderr. If a script fails, the entire chain halts with no recovery.

### 4.3 server.ts Auto-Starting Daemon
`governance_daemon.ts` is imported and auto-started when `server.ts` boots. No graceful shutdown or restart mechanism. If the daemon throws, the API server stays up but governance stops.

### 4.4 atlas_boot.html Polling Without Backoff
Browser polls every 30 seconds. If the API is down, it logs a warning and retries 30 seconds later. No exponential backoff. No circuit breaker.

---

## 5. Services That Could Be Merged

### 5.1 delta-kernel + aegis-fabric → Single Service
**Evidence**:
- Both are TypeScript/Express on the same machine
- aegis-fabric duplicates delta.ts from delta-kernel
- Both share the same Mode enum (maintained separately)
- aegis-fabric port 3002 is only called by external AI agents (not by atlas_boot.html or cognitive-sensor)
- No actual multi-tenant usage observed (prototype stage)
- Merging would eliminate delta.ts duplication and Mode enum drift

**Counter-argument**: Separation enforces policy isolation. Merge only if multi-tenancy is not needed.

### 5.2 route_today.py + export_daily_payload.py → Single Script
Both read `cognitive_state.json`, apply identical routing logic, and produce different output files. Could be one script producing both `daily_directive.txt` and `daily_payload.json`.

---

## 6. Services That Should Be Split

### 6.1 server.ts (45 endpoints, mixed concerns)
`services/delta-kernel/src/api/server.ts` handles:
- State CRUD (GET/PUT /api/state, /api/tasks)
- Cognitive ingestion (POST /api/ingest/cognitive)
- Law enforcement (POST /api/law/*)
- Work admission (POST /api/work/*)
- Timeline queries (GET /api/timeline/*)
- Daemon management (GET/POST /api/daemon/*)
- Health checks (GET /api/health)
- Static file serving (GET /control/*)

**Recommendation**: Split into route modules (already partially done in aegis-fabric, which has 7 separate route files).

### 6.2 types.ts (1162 lines)
Contains 45 entity types spanning:
- Core system (Mode, SystemState, Delta)
- Messaging (Message, Thread, Inbox)
- IoT (Actuator, Camera, Audio)
- UI streaming (UISurface, UIComponent)
- Sync protocol (SyncPacket, SyncSession)

The IoT/streaming types are not used in runtime. They could be split into `types-core.ts` and `types-iot.ts`.

---

## 7. Complexity Hotspots

### 7.1 types.ts — 1162 Lines of Type Definitions
- 45 entity types
- Multiple discriminated unions (UIComponentProps, ProposedStructure, DesignStructure, SyncPacket)
- Pre-existing type errors in consuming files (server.ts, renderer.ts, ai-design.ts, camera-extractor.ts)
- Marked as LOCKED but contains types for features not yet wired into runtime

### 7.2 server.ts — 45 Endpoints in Single File
- No route modularization
- Mixed read/write operations
- Inline business logic (mode recalculation in POST /api/law/close_loop)
- Serves static HTML from same process

### 7.3 atlas_config.py — Hardcoded Governance Rules
- North star, lane limits, routing thresholds, agent registry all in one Python dict
- No API to update at runtime
- No TypeScript equivalent (TypeScript services can't read it)
- Changes require code deployment

### 7.4 governance_daemon.ts — 6 Concurrent Cron Jobs
- Mode recalc (every 15min) reads cognitive state that refresh (every 1hr) writes
- Work queue (every 1min) interacts with active jobs that HTTP handlers also modify
- No coordination between overlapping job executions

### 7.5 Idea Pipeline — 5-Agent Sequential Chain
- Each agent reads the output of the previous one
- Full pipeline takes minutes (sentence-transformer inference on 1,397 conversations)
- No incremental processing (re-scans everything every run)
- Validation at each step, but no rollback if step 4 fails after steps 1-3 succeeded

---

## 8. Missing Coordination Mechanisms

| Mechanism | Status | Impact |
|---|---|---|
| File locking | Not implemented | Hash chain forks, potential state corruption |
| Retry logic | Not implemented | Failed daemon jobs are logged but not retried |
| Circuit breaker | Not implemented | Browser polls failing API indefinitely |
| Graceful shutdown | Not implemented | Killing server mid-write can corrupt JSON files |
| Health dependency | Not implemented | Services start without checking dependencies are healthy |
| Schema version negotiation | Not implemented | Schema changes require manual coordination across Python/TypeScript |

---

## 9. Dead Weight

### 9.1 Unintegrated Modules (Types Exist, No Runtime Wiring)
| Module | Location | Lines of Type Defs | Runtime Usage |
|---|---|---|---|
| delta-sync.ts | Module 6 | ~200 | None |
| off-grid-node.ts | Module 7 | ~100 | None |
| ui-stream.ts | Module 8 | ~150 | None |
| camera-stream.ts | Module 9 | ~150 | None |
| actuation.ts | Module 10 | ~200 | None |
| audio-*.ts | Module 11 | ~100 | None |

Combined: ~900 lines of type definitions with no runtime consumers.

### 9.2 Legacy Router
`lut.ts` uses different signals (leverage_balance, streak_days, pending_actions) than `routing.ts`. Only `renderer.ts` imports `lut.ts`. The rest of the system uses `routing.ts`.
