# Pre Atlas — Phase Roadmap

**Created:** 2026-01-09
**Purpose:** Complete history of implementation phases

---

## Overview

Pre Atlas development follows a phased approach, building from basic data processing through full cybernetic governance. Each phase adds a new capability layer.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PHASE PROGRESSION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5B ──► Phase 6     │
│  (Genesis)   (Bridge)   (Autonomy) (Enforce)  (Closure)   (Work+Time)       │
│                                                                              │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  │
│  │ Sense  │  │ Export │  │ Daemon │  │ Gate   │  │ Close  │  │ Admit    │  │
│  │ Memory │  │Contract│  │ Jobs   │  │ Build  │  │ Loops  │  │ Timeline │  │
│  │ Detect │  │ Bridge │  │ Unified│  │ Track  │  │ Streak │  │ Control  │  │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └──────────┘  │
│                                                                              │
│  [Phase 5A: WebSocket Push — DEFERRED]                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 — Genesis (2026-01-03)

**Status:** ✅ COMPLETE
**Focus:** Build the cognitive sensing foundation

### What Was Built

The cognitive-sensor system from scratch:

| Component | Purpose |
|-----------|---------|
| `results.db` | SQLite database from ChatGPT conversation export |
| `init_*.py` scripts | Database initialization pipeline |
| `loops.py` | Open loop detection algorithm |
| `radar.py` | Attention drift detection |
| `completion_stats.py` | Closure ratio calculation |
| `cognitive_state.json` | Machine-readable brain state |
| `daily_directive.txt` | Human-readable routing |
| `dashboard.html` | Analytics interface |
| `control_panel.html` | Master control interface |
| `cycleboard_app3.html` | Planning tool with governance overlay |

### Key Outputs

- 6-layer cognitive architecture (Memory → Intelligence → Nervous System → Law → Interface → Decision Tracking)
- Loop detection algorithm: `score = user_words + (intent_topic_weight × 30) - (done_topic_weight × 50)`
- Routing modes: CLOSURE (red), MAINTENANCE (yellow), BUILD (green)
- `refresh.py` master script running the full pipeline

### Design Principles Established

1. Single source of truth (`results.db`)
2. Transparent logic (no black boxes)
3. Enforcement over suggestion
4. Feedback loop closure

---

## Phase 2 — Bridge (2026-01-08)

**Status:** ✅ COMPLETE
**Focus:** Connect cognitive-sensor to delta-kernel

### Phase 2.1 — Contract Enforcement

| File | Purpose |
|------|---------|
| `contracts/schemas/DailyPayload.v1.json` | CycleBoard payload schema |
| `contracts/schemas/CognitiveMetricsComputed.json` | Cognitive state schema |
| `contracts/schemas/DailyProjection.v1.json` | Combined artifact schema |
| `validate.py` | Contract validation module |

All exports now validate against JSON Schema before writing.

### Phase 2.2 — Daily Projection

| File | Purpose |
|------|---------|
| `build_projection.py` | Creates `data/projections/today.json` |
| `data/projections/today.json` | Combined cognitive + directive artifact |

### Phase 2.3 — C→D Bridge

| File | Purpose |
|------|---------|
| `push_to_delta.py` | POSTs projection to Delta API |
| `server.ts` | Added `POST /api/ingest/cognitive` endpoint |
| `types.ts` | Added `'cognitive-sensor'` to Author type |

### Key Outputs

- Cognitive metrics flow into Delta via REST API
- 4-step pipeline: Delta API → Cognitive Sensor → Daily Projection → Push to Delta
- `run_all.ps1` launcher script

---

## Phase 3 — Autonomy (2026-01-08)

**Status:** ✅ COMPLETE
**Focus:** Autonomous governance daemon

### What Was Built

| Component | Location | Purpose |
|-----------|----------|---------|
| `governance_daemon.ts` | `services/delta-kernel/src/governance/` | Scheduled job runner |
| `/api/state/unified` | `server.ts` | Merged Delta + Cognitive state |
| `/api/daemon/status` | `server.ts` | Daemon status endpoint |
| `/api/daemon/run` | `server.ts` | Manual job trigger |

### Daemon Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| heartbeat | */5 * * * * | Update daemon status |
| refresh | 0 * * * * | Run cognitive refresh |
| day_start | 0 6 * * * | Record start-of-day marker |
| day_end | 0 22 * * * | Record end-of-day marker |

### Key Outputs

- Daemon starts automatically with API server
- Unified endpoint provides single source of truth for UI
- Day boundaries tracked in system state

---

## Phase 4 — Enforcement (2026-01-09)

**Status:** ✅ COMPLETE
**Focus:** Progressive enforcement with real teeth

### Enforcement Ladder

| Violations | Level | Behavior |
|------------|-------|----------|
| 0 | 0 | Warning banner only |
| 1 | 1 | Warn + require "ACKNOWLEDGE ORDER" |
| 2 | 2 | Disable "Create / New Project / Add Task" actions |
| 3+ | 3 | Hard lock build surfaces until loop closed/archived |

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/law/violation` | POST | Log build violation when locked |
| `/api/law/override` | POST | Log emergency override with reason |
| `/api/law/close_loop` | POST | Log closure and reset violations |

### Unified State Enhancement

```json
{
  "derived": {
    "build_allowed": true,
    "enforcement_level": 0,
    "violations_count": 0,
    "overrides_count": 0,
    "override_available": true
  }
}
```

### UI Enforcement

- `guardBuild()` wrapper function in CycleBoard
- Progressive UI: warning → disabled controls → hard lock overlay
- Override flow with reason prompt
- Enforcement badge in Atlas cockpit

### Critical Hardening Note

Post-Phase-4 identified issue: enforcement writes should use **leaf-path patches** instead of replacing entire `/enforcement` subtree to prevent clobbering fields during concurrent writes.

---

## Phase 5A — Live Push (DEFERRED)

**Status:** ⏸️ DEFERRED
**Focus:** WebSocket push instead of polling

### Planned Features

- Stop polling unified endpoint
- Push state changes instantly to all UIs
- Real-time mode transitions
- Live enforcement updates

### Why Deferred

Phase 5B (Closure Mechanics) was prioritized because:
- Closing loops is how users escape enforcement lock
- Mode transitions should be automatic based on closure behavior
- Streaks only meaningful with proper closure tracking
- 5A is polish; 5B completes the feedback loop

---

## Phase 5B — Closure Mechanics (2026-01-09)

**Status:** ✅ COMPLETE
**Specification:** `services/delta-kernel/specs/phase-5b-closure-mechanics.md`
**Focus:** Closure as a real state-transition event

### Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| Law Genesis Layer | `delta.ts:89-104` | Auto-creates constitutional state branches |
| Closure Endpoint | `server.ts:718-1029` | Canonical `POST /api/law/close_loop` |
| Closure Registry | `closures.json` | Persistent closure history + streak stats |
| Physical Closure | `loops_latest.json` → `loops_closed.json` | Real loop removal |
| Mode Engine | `governance_daemon.ts` | Autonomous 15-minute recalculation |
| Streak Engine | `server.ts` + daemon | BUILD-only increment, day-end reset |

### Mode Transition Rules

| closure_ratio | Mode | build_allowed |
|---------------|------|---------------|
| ≥ 0.80 | SCALE | true |
| ≥ 0.60 | BUILD | true |
| ≥ 0.40 | MAINTENANCE | false |
| < 0.40 | CLOSURE | false |

### New Daemon Job

| Job | Schedule | Description |
|-----|----------|-------------|
| mode_recalc | */15 * * * * | Autonomous mode governance |

### Key Behaviors

1. **Atomic Closure:** Single delta patches `/enforcement/*`, `/metrics/*`, `/mode`
2. **Idempotency:** Duplicate `loop_id` returns 409 Conflict
3. **BUILD-only Streaks:** Increment only in BUILD/SCALE mode
4. **Day-End Reset:** Streak → 0 if no productive closure
5. **Autonomous Mode:** Recalculated every 15 minutes without closure events
6. **Physical Closure:** Loops actually removed from `loops_latest.json`

### New Files

| File | Purpose |
|------|---------|
| `closures.json` | Closure registry with streak stats |
| `loops_closed.json` | Archive of closed loops |
| `Closures.v1.json` | Closure registry schema |
| `phase-5b-closure-mechanics.md` | Full specification |

### Design Principles

- **Leaf-patch only:** No subtree replacements
- **Law Genesis:** Parent paths auto-created
- **Contract enforcement:** Closures validated against schema
- **Physical closure:** Loops actually removed

---

## Current State Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE CYBERNETIC STACK                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SENSE        ← cognitive-sensor reads conversation history  │
│  2. DECIDE       ← directive + mode computed from metrics       │
│  3. GOVERN       ← delta law with immutable audit trail         │
│  4. ENFORCE      ← progressive gates block unauthorized build   │
│  5. REMEMBER     ← all actions logged as deltas                 │
│  6. AUTONOMIZE   ← daemon heartbeat + refresh + mode recalc     │
│  7. CLOSE        ← closure mechanics complete the feedback loop │
│  8. ADMIT        ← work controller gates all work (human + AI)  │
│  9. REMEMBER     ← timeline logs all system events over time    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 6A — Work Admission Control (2026-01-09)

**Status:** ✅ COMPLETE
**Specification:** `services/delta-kernel/specs/phase-6a-work-admission-control.md`
**Focus:** Universal work controller for humans AND machines

### Core Idea

Transform Pre-Atlas from a human governance system into a **universal work controller**. All work — human and AI — passes through a single admission gate.

### Three Primitives

| Endpoint | Purpose |
|----------|---------|
| `POST /api/work/request` | Ask permission to start a job |
| `POST /api/work/complete` | Report job completion |
| `GET /api/work/status` | Query current work state |

### Admission Logic

```
Request arrives:
  → Mode check (is build_allowed?)
  → Capacity check (slots available?)
  → Dependency check (blocked by other jobs?)
  → APPROVED / QUEUED / DENIED
```

### What This Enables

1. **AIs are under law** — must ask permission, must report completion
2. **Capacity is bounded** — max concurrent jobs, queue depth limits
3. **Dependencies enforced** — work happens in correct order
4. **Closure unified** — human and AI work in same ledger
5. **Cost trackable** — AI metrics flow through completion reports

### Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| Work Controller | `services/delta-kernel/src/core/work-controller.ts` | Admission gate + queue logic |
| Work Endpoints | `services/delta-kernel/src/api/server.ts` | 4 REST endpoints |
| Work Ledger | `services/cognitive-sensor/work_ledger.json` | Persistent job registry |
| Schema | `contracts/schemas/WorkLedger.v1.json` | Contract validation |
| Daemon Job | `governance_daemon.ts` | Queue management every minute |
| Validation | `validate.py` | `validate_work_ledger()` function |

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/work/request` | POST | Request permission to start a job |
| `/api/work/complete` | POST | Report job completion |
| `/api/work/status` | GET | Query current work state |
| `/api/work/cancel` | POST | Cancel a job |

### Key Behaviors

1. **Mode Enforcement:** AI jobs denied in CLOSURE mode by default
2. **Capacity Bounded:** `max_concurrent_jobs=1`, `max_queue_depth=5`
3. **Dependency Tracking:** Jobs can block on unmet dependencies
4. **Timeout Handling:** Jobs auto-fail after `default_timeout_ms`
5. **Queue Advancement:** Daemon promotes queued jobs when slots free
6. **Cost Tracking:** AI metrics (`tokens_used`, `cost_usd`) flow through completion

### Design Principle

> First you make law apply to machines.
> Then machines become safe to automate.

---

## Phase 6A.1 — Ambient Gate (2026-01-09)

**Status:** ✅ COMPLETE
**Focus:** Make the work controller always available

### Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| Gate Client | `services/delta-kernel/src/tools/gate_client.ts` | Auto-starts kernel, ambient access |
| Gate CLI | `services/delta-kernel/src/tools/gate.ts` | Command-line interface |
| Control Panel | `services/delta-kernel/src/ui/control.html` | Live governor state viewer |

### Key Behavior

- If kernel isn't running, `gate_client.ts` starts it automatically
- Law is never optional — if work is attempted, the law wakes up
- Control panel shows mode, capacity, active jobs, queue at a glance

### Access

- **Control Panel:** http://localhost:3001/control/control.html
- **Gate CLI:** `npm run gate -- status`

---

## Phase 6C — Timeline Layer (2026-01-09)

**Status:** ✅ COMPLETE
**Focus:** Temporal visibility — see what the machine actually did

### Core Idea

Pre-Atlas now has temporal memory. Every significant state change writes an event to an append-only log. You can query, filter, and replay system activity over time.

### Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| Schema | `contracts/schemas/TimelineEvents.v1.json` | Event structure definition |
| Logger | `services/delta-kernel/src/core/timeline-logger.ts` | Append-only event log with query |
| Data | `services/cognitive-sensor/timeline_events.json` | Event storage |
| API | `services/delta-kernel/src/api/server.ts` | Timeline query endpoints |
| UI | `services/delta-kernel/src/ui/timeline.html` | Visual timeline viewer |

### Event Types

| Event | Source | Description |
|-------|--------|-------------|
| `SYSTEM_START` | daemon | Kernel booted |
| `DAEMON_HEARTBEAT` | daemon | 5-minute pulse |
| `WORK_REQUESTED` | work_controller | Job submitted |
| `WORK_APPROVED` | work_controller | Job started |
| `WORK_DENIED` | work_controller | Admission rejected |
| `WORK_QUEUED` | work_controller | Job waiting |
| `WORK_COMPLETED` | work_controller | Job finished |
| `WORK_FAILED` | work_controller | Job failed |
| `WORK_TIMEOUT` | work_controller | Job timed out |
| `WORK_CANCELLED` | work_controller | Job cancelled |
| `WORK_ABANDONED` | work_controller | Job abandoned |
| `MODE_CHANGED` | daemon | Governance mode transition |

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/timeline` | GET | Query events with filters |
| `/api/timeline/stats` | GET | Event statistics |
| `/api/timeline/day/:date` | GET | All events for a specific day |

### Query Parameters

```
GET /api/timeline?from=2026-01-09T00:00:00Z&to=2026-01-09T23:59:59Z&type=WORK_COMPLETED&limit=50
```

### Access

- **Timeline Viewer:** http://localhost:3001/control/timeline.html
- **API:** http://localhost:3001/api/timeline

### Design Principle

> Two timelines exist:
> - **Intent (Calendar A):** What you plan to do — from CycleBoard
> - **Reality (Calendar B):** What actually happened — from Timeline
>
> The gap between them is where you learn.

---

## Phase 6B — Work Preparation (FUTURE)

**Status:** 📋 CONCEPT
**Focus:** Background workers that ready work before humans start

### Planned Features

- Prep workers (background jobs that ready work)
- Scheduling bots (agents that plan future work)
- Multi-agent routing (directing work to best-fit agents)
- Predictive loading (pre-running likely-needed jobs)

All become **clients of the work controller** from Phase 6A.

---

## Future Phases (Potential)

### Phase 7 — Federated State
- Multiple data sources
- Cross-device sync
- Distributed delta replication

### Phase 8 — Adaptive Learning
- Priority weighting based on outcomes
- Velocity tracking (intent → completion time)
- Pattern prediction

---

## Files Modified By Phase

### Phase 1
- All `services/cognitive-sensor/*.py` scripts
- All `services/cognitive-sensor/*.html` interfaces
- `services/cognitive-sensor/results.db`

### Phase 2
- `contracts/schemas/*.json` (new)
- `services/cognitive-sensor/validate.py` (new)
- `services/cognitive-sensor/build_projection.py` (new)
- `services/cognitive-sensor/push_to_delta.py` (new)
- `services/delta-kernel/src/api/server.ts`
- `services/delta-kernel/src/core/types.ts`
- `scripts/run_all.ps1`

### Phase 3
- `services/delta-kernel/src/governance/governance_daemon.ts` (new)
- `services/delta-kernel/src/api/server.ts`

### Phase 4
- `services/delta-kernel/src/api/server.ts`
- `services/cognitive-sensor/cycleboard_app3.html`
- `atlas_boot.html`

### Phase 5B
- `services/delta-kernel/src/core/delta.ts`
- `services/delta-kernel/src/api/server.ts`
- `services/delta-kernel/src/governance/governance_daemon.ts`
- `services/cognitive-sensor/validate.py`
- `contracts/schemas/Closures.v1.json` (new)
- `services/delta-kernel/specs/phase-5b-closure-mechanics.md` (new)

### Phase 6A
- `services/delta-kernel/src/core/work-controller.ts` (new)
- `services/delta-kernel/src/api/server.ts`
- `services/delta-kernel/src/governance/governance_daemon.ts`
- `services/cognitive-sensor/work_ledger.json` (new)
- `contracts/schemas/WorkLedger.v1.json` (new)
- `services/cognitive-sensor/validate.py`

### Phase 6A.1
- `services/delta-kernel/src/tools/gate_client.ts` (new)
- `services/delta-kernel/src/tools/gate.ts` (new)
- `services/delta-kernel/src/ui/control.html` (new)
- `services/delta-kernel/package.json` (added gate script)

### Phase 6C
- `services/delta-kernel/src/core/timeline-logger.ts` (new)
- `services/delta-kernel/src/ui/timeline.html` (new)
- `services/cognitive-sensor/timeline_events.json` (new)
- `contracts/schemas/TimelineEvents.v1.json` (new)
- `services/delta-kernel/src/api/server.ts` (timeline endpoints)
- `services/delta-kernel/src/core/work-controller.ts` (event emission)
- `services/delta-kernel/src/governance/governance_daemon.ts` (event emission)

---

*Phase 6C Complete — The system now has temporal visibility.*
*You can see what the machine did, replay any day, audit all events.*
