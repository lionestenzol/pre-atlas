# Pre Atlas — Complete Codebase Analysis

**Generated:** 2026-01-14
**Analyst:** Claude Code (Opus 4.5)
**Branch:** `claude/analyze-codebase-vwqSm`

---

## A. Languages & Frameworks Present

| Language | Usage | Framework/Runtime |
|----------|-------|-------------------|
| **TypeScript** | Delta Kernel (core engine) | Node.js 20+, Express 5, tsx |
| **Python 3** | Cognitive Sensor (analysis) | sentence-transformers, scikit-learn, numpy |
| **React 19** | Web dashboard | Vite 7, ESLint |
| **HTML/CSS/JS** | Web OS simulator, dashboards | Vanilla (standalone) |
| **PowerShell** | Launcher scripts | Windows automation |
| **JSON Schema** | Data contracts | RFC 6902 (JSON Patch) |

---

## B. Top 5 Modules & Responsibilities

| Module | Location | Responsibility |
|--------|----------|----------------|
| **1. Delta Kernel** | `services/delta-kernel/` | Deterministic state engine with hash-chain verification. Owns all state transitions via JSON Patch deltas. Runs API on `:3001`. |
| **2. Cognitive Sensor** | `services/cognitive-sensor/` | Analyzes 93k+ conversation messages, detects open loops, computes mode/routing decisions. Outputs `cognitive_state.json`. |
| **3. Governance Daemon** | `src/governance/governance_daemon.ts` | Autonomous cron-based mode recalculation every 15 minutes. Manages day_start/day_end events and streak compounding. |
| **4. Work Controller** | `src/core/work-controller.ts` | Phase 6A work admission control. Gates human/AI/system jobs based on current mode. Maintains work ledger. |
| **5. UASC-M2M** | `research/uasc-m2m/` | Research framework for extreme symbolic compression. Encodes workflows into single glyphs. |

---

## C. Blockers to Full Understanding

| Blocker | Impact | Resolution |
|---------|--------|------------|
| **results.db** (SQLite) | Contains 93k messages but not readable without Python tooling | Use `loops.py` or custom query |
| **Missing node_modules** | Need `npm install` in delta-kernel | Quick fix: one command |
| **Compiled .js missing** | TypeScript needs `npm run build` or use `tsx` directly | Already configured in package.json |
| **No CI/CD config** | No automated tests or deployment pipeline visible | Manual testing required |

---

# 1. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                              PRE ATLAS STACK                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         LAYER 6: INTERFACES                              │  │
│  │  CycleBoard (HTML)  │  Dashboard (HTML)  │  React Web  │  CLI Terminal   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                      ▲                                         │
│                                      │ reads                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         LAYER 5: LAW GENERATION                          │  │
│  │                   daily_directive.txt  │  daily_payload.json              │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                      ▲                                         │
│                                      │ writes                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                       LAYER 4: NERVOUS SYSTEM                            │  │
│  │        cognitive_state.json  │  closures.json  │  loops_latest.json       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                      ▲                                         │
│         ┌────────────────────────────┴────────────────────────────┐           │
│         │                                                          │           │
│  ┌──────┴──────────────────────┐    ┌─────────────────────────────┴──────┐   │
│  │     LAYER 3: INTELLIGENCE    │    │    LAYER 3: STATE ENGINE          │   │
│  │  Cognitive Sensor (Python)   │◄───│    Delta Kernel (TypeScript)      │   │
│  │  loops.py, radar.py,         │    │    delta.ts, routing.ts,          │   │
│  │  completion_stats.py         │    │    governance_daemon.ts           │   │
│  └──────────────────────────────┘    └────────────────────────────────────┘   │
│               │                                      ▲                         │
│               │ SQL queries                          │ JSON Patch deltas       │
│               ▼                                      │                         │
│  ┌──────────────────────────────┐    ┌────────────────────────────────────┐   │
│  │     LAYER 1-2: MEMORY        │    │       STATE PERSISTENCE            │   │
│  │  results.db (93k messages)   │    │  .delta-fabric/entities.json       │   │
│  │  loop_decisions table        │    │  .delta-fabric/deltas.json         │   │
│  └──────────────────────────────┘    └────────────────────────────────────┘   │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow — Daily Cycle

```
[User Conversations]
        │
        ▼
┌──────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│   results.db     │────▶│  loops.py           │────▶│ loops_latest.json  │
│  (93k messages)  │     │  (detect open loops)│     │                    │
└──────────────────┘     └─────────────────────┘     └────────────────────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │ completion_stats.py │
                         │ (closure ratio)     │
                         └─────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────┴────────────────────────────────────┐
│                        route_today.py                                  │
│  if closure_ratio < 15% OR open_loops > 20 → CLOSURE (RED)            │
│  if open_loops > 10 AND closure_ratio >= 15% → MAINTENANCE (YELLOW)   │
│  if open_loops <= 10 AND closure_ratio >= 15% → BUILD (GREEN)         │
└───────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌───────────────────────────┐
                    │  cognitive_state.json     │
                    │  daily_directive.txt      │
                    └───────────────────────────┘
                                   │
                                   ▼ POST /api/ingest/cognitive
                    ┌───────────────────────────┐
                    │  Delta Kernel API (:3001) │
                    │  Updates system_state     │
                    └───────────────────────────┘
                                   │
                                   ▼
                    ┌───────────────────────────┐
                    │  Governance Daemon        │
                    │  (cron: */15 * * * *)     │
                    │  Autonomous mode recalc   │
                    └───────────────────────────┘
```

---

# 2. Directory & File Index

```
Pre Atlas/                          # Root
├── README.md                       # Quick start guide
├── PRE_ATLAS_MAP.md                # Full architecture (this analysis source)
├── CONTEXT_PACKET.md               # LLM handoff context
├── FILE_MAP.md                     # File interconnections
├── PHASE_ROADMAP.md                # Implementation history (Phase 1-5B)
│
├── services/
│   ├── delta-kernel/               # TypeScript state engine
│   │   ├── package.json            # deps: express, cors, node-cron
│   │   ├── tsconfig.json           # ES2022, strict mode
│   │   ├── src/
│   │   │   ├── api/server.ts       # REST API (:3001), 1300 lines
│   │   │   ├── cli/                # Interactive terminal
│   │   │   │   ├── index.ts        # Entry point
│   │   │   │   ├── app.ts          # Application logic
│   │   │   │   ├── input.ts        # Keyboard handling
│   │   │   │   ├── renderer.ts     # Terminal rendering
│   │   │   │   └── storage.ts      # JSON file persistence
│   │   │   ├── core/               # 35+ modules
│   │   │   │   ├── types.ts        # 1161 lines — ALL type definitions
│   │   │   │   ├── delta.ts        # Delta operations, Law Genesis Layer
│   │   │   │   ├── routing.ts      # Mode computation (Markov LUT)
│   │   │   │   ├── templates.ts    # Mode behavior contracts
│   │   │   │   ├── tasks.ts        # Task lifecycle
│   │   │   │   ├── work-controller.ts  # Phase 6A admission control
│   │   │   │   ├── timeline-logger.ts  # Event logging
│   │   │   │   ├── ui-surface.ts   # Module 8: UI streaming
│   │   │   │   ├── camera-surface.ts   # Module 9: Camera streaming
│   │   │   │   ├── actuation.ts    # Module 10: Remote control
│   │   │   │   └── ...
│   │   │   ├── governance/
│   │   │   │   └── governance_daemon.ts  # Autonomous mode daemon
│   │   │   └── tools/
│   │   │       ├── gate.ts         # Gate operations
│   │   │       └── gate_client.ts  # Gate client
│   │   ├── specs/                  # 18 specification documents
│   │   └── web/                    # React frontend (Vite)
│   │
│   └── cognitive-sensor/           # Python analysis engine
│       ├── refresh.py              # Master pipeline runner
│       ├── loops.py                # Open loop detection
│       ├── completion_stats.py     # Closure tracking
│       ├── route_today.py          # Daily mode routing
│       ├── decision_engine.py      # Decision logic
│       ├── brain.py                # Core cognitive processing
│       ├── vectorization.py        # Sentence embeddings
│       ├── validate.py             # Contract validation
│       ├── export_*.py             # JSON export scripts
│       ├── results.db              # SQLite (93k messages)
│       ├── cognitive_state.json    # Current state snapshot
│       ├── closures.json           # Closure registry (Phase 5B)
│       ├── loops_latest.json       # Current open loops
│       └── cycleboard/             # CycleBoard UI module
│
├── contracts/
│   └── schemas/                    # JSON Schema contracts
│       ├── DailyPayload.v1.json    # CycleBoard consumption format
│       ├── CognitiveMetricsComputed.json
│       ├── DirectiveProposed.json
│       ├── DailyProjection.v1.json
│       ├── Closures.v1.json        # Phase 5B
│       ├── WorkLedger.v1.json      # Phase 6A
│       └── TimelineEvents.v1.json  # Phase 6C
│
├── data/
│   └── projections/
│       └── today.json              # Combined daily artifact
│
├── apps/
│   └── webos-333/                  # Browser-based OS simulator
│       ├── web-os-simulator.html   # 3,443 lines (standalone)
│       └── WEB-OS-DOCUMENTATION.md
│
├── research/
│   └── uasc-m2m/                   # Symbolic encoding research
│       ├── spec/                   # 5 specification documents
│       ├── reference-implementation/
│       └── generic/                # Generic Python framework
│
├── scripts/
│   ├── run_all.ps1                 # Full stack launcher
│   ├── run_cognitive.ps1           # Cognitive sensor only
│   ├── run_delta_api.ps1           # Delta API on :3001
│   └── run_delta_cli.ps1           # Interactive CLI
│
└── .delta-fabric/                  # State persistence (repo-local)
    ├── entities.json               # Entity store
    └── deltas.json                 # Append-only delta log
```

---

# 3. Core Logic Breakdown

## 3.1 Delta Engine (`delta.ts`)

| Function | Input | Output | Side Effects |
|----------|-------|--------|--------------|
| `createEntity()` | entityType, initialState | entity, delta, state | None (caller persists) |
| `createDelta()` | entity, currentState, patch, author | updatedEntity, delta, newState | None |
| `applyPatch()` | state, JsonPatch[] | newState | None (pure function) |
| `verifyHashChain()` | Delta[] | boolean | None |
| `reconstructState()` | Delta[] | state | None |

**Law Genesis Layer** (lines 89-104): Auto-creates parent path nodes before leaf-patch operations. This enables the kernel to host "constitutional state branches" without crashing.

**Failure Mode**: Hash chain verification fails if deltas are tampered with or arrive out of order.

---

## 3.2 Routing Engine (`routing.ts`)

```typescript
// Pure function — NO side effects
function computeNextMode(currentMode: Mode, buckets: BucketedSignals): Mode
```

| Signal | LOW | OK | HIGH |
|--------|-----|----|----|
| sleep_hours | < 6 | 6–7.5 | ≥ 7.5 |
| open_loops | ≥ 4 (bad) | 2–3 | ≤ 1 (good) |
| assets_shipped | 0 | 1 | ≥ 2 |
| deep_work_blocks | 0 | 1 | ≥ 2 |
| money_delta | ≤ 0 | 1–999 | ≥ 1000 |

**Global Overrides** (highest priority):
- `sleep_hours === LOW` → RECOVER
- `open_loops === LOW` → CLOSE_LOOPS

---

## 3.3 Closure Endpoint (`/api/law/close_loop`)

The **atomic closure law** performs in ONE delta:

1. **Enforcement reset**: `violations_count → 0`
2. **Metrics mutation**: `closed_loops_total++`, `closure_ratio`, `last_closure_at`
3. **Streak increment**: BUILD-only (no inflation)
4. **Mode transition**: Based on ratio thresholds:
   - ≥ 80% → SCALE
   - ≥ 60% → BUILD
   - ≥ 40% → MAINTENANCE
   - < 40% → CLOSURE
5. **Physical removal**: Updates `loops_latest.json`, appends to `loops_closed.json`

**Idempotency**: Duplicate closures (same `loop_id`) return `409 Conflict`.

---

## 3.4 Cognitive Sensor Pipeline (`refresh.py`)

Runs 8 scripts in sequence:

```python
loops.py              # Detect open loops from results.db
completion_stats.py   # Calculate closure statistics
export_cognitive_state.py
route_today.py        # Compute mode based on rules
export_daily_payload.py
wire_cycleboard.py    # Update CycleBoard data
reporter.py           # Generate reports
build_dashboard.py    # Rebuild dashboard HTML
```

**Output contracts** (validated against JSON Schema):
- `cognitive_state.json` → `CognitiveMetricsComputed.json`
- `daily_payload.json` → `DailyPayload.v1.json`
- `data/projections/today.json` → `DailyProjection.v1.json`

---

## 3.5 Governance Daemon (`governance_daemon.ts`)

| Job | Schedule | Action |
|-----|----------|--------|
| heartbeat | */5 * * * * | Update daemon status |
| refresh | 0 * * * * | Run cognitive refresh |
| day_start | 0 6 * * * | Reset daily counters, recalc mode |
| day_end | 0 22 * * * | Streak reset if no BUILD closure |
| mode_recalc | */15 * * * * | Autonomous mode governance |

---

# 4. Code Quality Findings

## 4.1 Bugs & Issues

| Location | Issue | Severity | Fix |
|----------|-------|----------|-----|
| `server.ts:69-71` | Hardcoded `repoRoot` path calculation differs from line 34-36 | LOW | Consolidate path logic |
| `routing.ts` | `open_loops` bucket inverted (LOW = bad) | CONFUSING | Add explicit comments or rename |
| `types.ts:45` | `audio_surface` defined but no corresponding `AudioSurfaceData` | MISSING | Add type definition |

## 4.2 Missing Tests

| Module | Coverage | Critical Gap |
|--------|----------|--------------|
| `delta.ts` | `fabric-tests.ts` exists | Hash chain verification untested for edge cases |
| `routing.ts` | None | Mode transitions need property-based tests |
| `server.ts` | None | API endpoints need integration tests |
| Cognitive Sensor | `test_vectorization.py` only | `loops.py`, `route_today.py` untested |

## 4.3 Architectural Debt

| Debt | Impact | Recommendation |
|------|--------|----------------|
| **No dependency injection** | Hard to test Storage, Daemon | Introduce constructor injection |
| **Mixed async/sync in delta.ts** | `computeHash()` is sync, `hashState()` is async | Standardize on async |
| **Magic numbers** | Bucket thresholds hardcoded in routing.ts | Move to config file |
| **Python scripts use subprocess** | No error propagation | Use importlib or error codes |

## 4.4 Risky Patterns

| Pattern | Risk | Location |
|---------|------|----------|
| `as any` casts | Type safety bypass | `server.ts:420`, `463`, `509`, `631`, etc. |
| Global state | Daemon/Storage as module-level singletons | `server.ts:29-46` |
| Uncaught Promise rejections | Crash risk | `governance_daemon.ts` cron jobs |
| File reads without locks | Race conditions | `closures.json` read/write in close_loop |

---

# 5. Immediate Action Plan

| Priority | Task | Impact | Risk | Effort |
|----------|------|--------|------|--------|
| **P0** | Add integration tests for `/api/law/close_loop` | Critical path, high complexity | HIGH | 4h |
| **P0** | Fix `audio_surface` missing type | Compilation may fail | LOW | 15min |
| **P1** | Add error handling in daemon cron jobs | Silent failures | MEDIUM | 2h |
| **P1** | Remove `as any` casts, add proper types | Type safety | MEDIUM | 3h |
| **P2** | Add property-based tests for `routing.ts` | Logic correctness | LOW | 2h |
| **P2** | Move bucket thresholds to config.json | Configurability | LOW | 1h |
| **P3** | Add file locking for `closures.json` | Race condition | LOW | 2h |
| **P3** | Add CI/CD pipeline (GitHub Actions) | Automation | LOW | 4h |

---

# 6. API Reference

## Delta Kernel REST API (`:3001`)

### State Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Get current system state |
| `/api/state` | PUT | Update system state |
| `/api/state/unified` | GET | Merged Delta + Cognitive state |
| `/api/ingest/cognitive` | POST | Ingest cognitive metrics |

### Task Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | GET | List all tasks |
| `/api/tasks` | POST | Create task |
| `/api/tasks/:id` | PUT | Update task |
| `/api/tasks/:id` | DELETE | Archive task |

### Law Enforcement

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/law/close_loop` | POST | Canonical closure event (Phase 5B) |
| `/api/law/acknowledge` | POST | Acknowledge daily order |
| `/api/law/violation` | POST | Log build violation |
| `/api/law/override` | POST | Log enforcement override |
| `/api/law/archive` | POST | Archive a loop |
| `/api/law/refresh` | POST | Request cognitive refresh |

### Work Admission (Phase 6A)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/work/request` | POST | Request permission to start job |
| `/api/work/complete` | POST | Report job completion |
| `/api/work/status` | GET | Query current work state |
| `/api/work/cancel` | POST | Cancel queued/active job |
| `/api/work/history` | GET | Get completed jobs history |

### Timeline (Phase 6C)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/timeline` | GET | Query timeline events |
| `/api/timeline/stats` | GET | Get timeline statistics |
| `/api/timeline/day/:date` | GET | Get events for specific day |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/stats` | GET | Storage statistics |
| `/api/daemon/status` | GET | Governance daemon status |
| `/api/daemon/run` | POST | Manually trigger daemon job |

---

# 7. Quick Start Commands

```powershell
# Full stack (Delta API + Cognitive Sensor + Daily Projection)
.\scripts\run_all.ps1

# Individual services
.\scripts\run_cognitive.ps1    # Cognitive analysis only
.\scripts\run_delta_api.ps1    # Delta API on :3001
.\scripts\run_delta_cli.ps1    # Interactive CLI

# First-time setup
cd services/delta-kernel
npm install

# Run tests
npm run test

# Build TypeScript
npm run build
```

---

# 8. Ready for Tasks

This analysis is complete. Next steps available:

1. **Fix** bugs with precise diffs
2. **Extend** features (new endpoints, modules, Python scripts)
3. **Optimize** (reduce `as any`, add proper typing)
4. **Test** (write integration/unit tests)
5. **Document** (API docs, README updates)

---

*Analysis generated by Claude Code on 2026-01-14*
