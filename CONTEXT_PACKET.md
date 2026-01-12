# Pre Atlas — Context Packet

**Generated:** 2026-01-08
**Updated:** 2026-01-12 (Phase 6C complete, doc sync)
**Purpose:** Federated monorepo for behavioral governance
**Status:** ✅ PHASE 6C COMPLETE (work admission, timeline layer)

---

## 0) ASSUMPTIONS I MADE (updated post-consolidation)

1. ~~**Delta's data directory** (`~/.delta-fabric`) is intentionally outside the repo for user-level persistence.~~ **RESOLVED:** Now uses repo-local `.delta-fabric/` via `DELTA_DATA_DIR` env var.
2. **cognitive-sensor's `results.db`** is the authoritative conversation data. It's not version-controlled (too large) and stays in-place at `services/cognitive-sensor/results.db`.
3. **uasc-m2m** is research/standalone — no integration with other services. Lives in `research/uasc-m2m/`.
4. **webos-333** is a demo project with no dependencies. Lives in `apps/webos-333/`.
5. ~~**`refresh.py` expects CWD = My_Workspace**~~ **RESOLVED:** Hardened with `cwd=BASE` parameter. Now CWD-safe.
6. **Node version** not specified; assumed Node 18+ based on Express 5 and tsx usage.
7. **Python version** not specified; assumed Python 3.10+ based on `match` statement absence and pathlib usage.

---

## 1) EXEC SUMMARY

- **What the repo is:** A federated monorepo for personal behavioral governance
- **Structure:** `services/`, `apps/`, `research/`, `contracts/`, `data/`, `scripts/`
- **Pipeline:** `run_all.ps1` runs 4-step flow: Delta API → Cognitive Sensor → Daily Projection → Push to Delta
- **Contracts:** All exports validated against JSON Schema before writing
- **Bridge:** Cognitive metrics flow into Delta via `POST /api/ingest/cognitive`
- **Phase History:** See `PHASE_ROADMAP.md` for complete implementation timeline (Phase 1 → 5B)

---

## 2) PROJECT PUBLIC SURFACE (updated paths)

### 2.1 .delta-fabric (repo-local data)

| Attribute | Value |
|-----------|-------|
| **Location** | `.delta-fabric/` (repo root) |
| **Entrypoints** | None (data-only) |
| **Run commands** | N/A |
| **Inputs read** | None |
| **Outputs written** | `entities.json`, `deltas.json` |
| **Ports** | None |
| **Dependencies** | None |

**Notes:** Repo-local data store. Launcher scripts configure `DELTA_DATA_DIR` to point here.

---

### 2.2 delta-kernel (services/delta-kernel/)

| Attribute | Value |
|-----------|-------|
| **Location** | `services/delta-kernel/` |
| **Entrypoints** | `src/cli/index.ts`, `src/api/server.ts`, `start.bat` |
| **Run commands** | `npm run start` (CLI), `npm run api` (REST), `npm run test`, `npm run build` |
| **Launcher scripts** | `scripts/run_delta_cli.ps1`, `scripts/run_delta_api.ps1` |
| **Inputs read** | `.delta-fabric/entities.json`, `.delta-fabric/deltas.json` |
| **Outputs written** | Same as inputs |
| **Ports** | 3001 (API), 5173 (web dev server) |
| **Dependencies** | Node.js, npm, tsx, typescript, express, cors |

**Path logic (FIXED):**
- `src/api/server.ts:19` — `process.env.DELTA_DATA_DIR || path.join(os.homedir(), '.delta-fabric')` ✓
- CLI accepts `--data <dir>` to override
- Launcher scripts set `DELTA_DATA_DIR` to repo-local `.delta-fabric/`

---

### 2.3 cognitive-sensor (services/cognitive-sensor/)

| Attribute | Value |
|-----------|-------|
| **Location** | `services/cognitive-sensor/` |
| **Entrypoints** | `refresh.py` (master), individual scripts |
| **Run commands** | `python refresh.py` (runs full pipeline) |
| **Launcher scripts** | `scripts/run_cognitive.ps1` |
| **Inputs read** | `results.db`, `loops_latest.json`, `cognitive_state.json` |
| **Outputs written** | `cognitive_state.json`, `daily_directive.txt`, `loops_latest.json`, `completion_stats.json`, `dashboard.html`, `~/Downloads/cycleboard/brain/daily_payload.json` |
| **Ports** | 8080 (optional) |
| **Dependencies** | Python 3.x, sqlite3 (stdlib) |

**Path logic (FIXED):**
- `refresh.py` uses `BASE = Path(__file__).parent.resolve()` and `cwd=BASE` ✓ CWD-safe
- `export_daily_payload.py` uses `Path.home() / "Downloads" / ...` ✓ portable
- `cluster_business_topics.py` uses `BASE / "results.db"` ✓ portable
- All scripts now CWD-independent

---

### 2.4 webos-333 (apps/webos-333/)

| Attribute | Value |
|-----------|-------|
| **Location** | `apps/webos-333/` |
| **Entrypoints** | `web-os-simulator.html` (open in browser) |
| **Run commands** | None (static HTML) |
| **Inputs read** | None |
| **Outputs written** | localStorage only |
| **Ports** | None |
| **Dependencies** | Modern browser |

**Notes:** Fully self-contained. No external dependencies.

---

### 2.5 uasc-m2m (research/uasc-m2m/)

| Attribute | Value |
|-----------|-------|
| **Location** | `research/uasc-m2m/` |
| **Entrypoints** | `generic/uasc_generic.py`, `generic/examples.py` |
| **Run commands** | `python uasc_generic.py --demo`, `python uasc_generic.py --server [port]` |
| **Inputs read** | None (self-contained) |
| **Outputs written** | None |
| **Ports** | 8420 (optional HTTP server) |
| **Dependencies** | Python 3.x (stdlib only) |

**Notes:** Research project. Fully portable.

---

## 3) DATA I/O MAP (updated paths)

### Canonical Runtime Data Files

| File | Location | Writers | Readers | Type |
|------|----------|---------|---------|------|
| `entities.json` | `.delta-fabric/` | delta-kernel CLI/API | delta-kernel CLI/API | **Authoritative state** |
| `deltas.json` | `.delta-fabric/` | delta-kernel CLI/API | delta-kernel CLI/API | **Authoritative log** |
| `results.db` | `services/cognitive-sensor/` | Init scripts only | loops.py, cognitive_api.py, radar.py, etc. | **Raw immutable input** |
| `cognitive_state.json` | `services/cognitive-sensor/` | export_cognitive_state.py | route_today.py, export_daily_payload.py, CycleBoard | **Derived projection** |
| `daily_directive.txt` | `services/cognitive-sensor/` | route_today.py | wire_cycleboard.py, humans | **Derived projection** |
| `daily_payload.json` | `~/Downloads/cycleboard/brain/` | export_daily_payload.py | CycleBoard HTML | **Derived projection** |
| `loops_latest.json` | `services/cognitive-sensor/` | loops.py | cognitive_api.py, route_today.py | **Derived projection** |
| `completion_stats.json` | `services/cognitive-sensor/` | completion_stats.py | build_dashboard.py | **Derived projection** |
| `today.json` | `data/projections/` | build_projection.py | Delta API, consumers | **Combined daily artifact** |

**Key insight:** delta-kernel and cognitive-sensor are now **bridged** via `POST /api/ingest/cognitive`.

---

## 4) HARDCODED PATH & COUPLING SCAN (post-fix status)

### 4.1 Absolute Path References — ✅ ALL FIXED

| File | Line | Snippet | Status |
|------|------|---------|--------|
| `services/cognitive-sensor/export_daily_payload.py` | - | Now uses `Path.home() / ...` | ✅ **FIXED** |
| `services/cognitive-sensor/cluster_business_topics.py` | - | Now uses `BASE / "results.db"` | ✅ **FIXED** |

### 4.2 Home-Relative Paths (SAFE)

| File | Line | Snippet |
|------|------|---------|
| `services/delta-kernel/src/api/server.ts` | 19 | `process.env.DELTA_DATA_DIR \|\| path.join(os.homedir(), '.delta-fabric')` |
| `services/cognitive-sensor/wire_cycleboard.py` | 16 | `Path.home() / "Downloads" / "cycleboard"` |
| `services/cognitive-sensor/inject_directive.py` | 8-9 | `Path.home() / "Downloads" / ...` |
| `services/cognitive-sensor/export_daily_payload.py` | - | `Path.home() / "Downloads" / ...` |

### 4.3 Script-Relative Paths (SAFE)

| File | Line | Snippet |
|------|------|---------|
| `services/cognitive-sensor/refresh.py` | - | `BASE = Path(__file__).parent.resolve()` |
| `services/cognitive-sensor/wire_cycleboard.py` | 15 | `Path(__file__).parent.resolve()` |
| `services/cognitive-sensor/cluster_business_topics.py` | - | `BASE = Path(__file__).parent.resolve()` |
| `services/cognitive-sensor/export_daily_payload.py` | - | `BASE = Path(__file__).parent.resolve()` |

### 4.4 CWD-Relative Paths — ✅ MITIGATED

Scripts still use bare filenames internally (`"results.db"`), but `refresh.py` now runs them with `cwd=BASE`, making them CWD-safe when invoked via the master script.

### 4.5 Subprocess CWD Dependency — ✅ FIXED

| File | Line | Snippet | Status |
|------|------|---------|--------|
| `services/cognitive-sensor/refresh.py` | - | Now uses `subprocess.check_call(..., cwd=BASE)` | ✅ **FIXED** |

**Scripts can now be run from any directory.**

### 4.6 "Pre Atlas" String References

Only in documentation files. No code references.

### 4.7 `.delta-fabric` String References

| File | Line | Context |
|------|------|---------|
| `services/delta-kernel/src/api/server.ts` | 5, 19 | Comment + path construction (env var first) |
| `services/delta-kernel/src/cli/index.ts` | 12 | Default data dir |
| `scripts/*.ps1` | - | Set `DELTA_DATA_DIR` to repo-local `.delta-fabric/` |

---

## 5) RUNBOOK CHECK (updated)

### 5.1 Run Location Requirements — ✅ ALL CWD-SAFE

| Project | Must run from project folder? | Reason |
|---------|-------------------------------|--------|
| delta-kernel | No | Uses `DELTA_DATA_DIR` env var or `~/.delta-fabric` fallback |
| cognitive-sensor | **No** (fixed) | `refresh.py` uses `cwd=BASE` for subprocess calls |
| webos-333 | No | Static HTML, open anywhere |
| uasc-m2m | No | No file dependencies |
| .delta-fabric | N/A | Data only |

### 5.2 One-Time Setup Steps

| Project | Setup |
|---------|-------|
| delta-kernel | `cd services/delta-kernel && npm install` |
| delta-kernel/web | `cd services/delta-kernel/web && npm install` |
| cognitive-sensor | None (uses Python stdlib) |
| uasc-m2m | None (uses Python stdlib) |
| webos-333 | None |

### 5.3 What Breaks If Folders Move — ✅ SAFE NOW

| Scenario | Impact |
|----------|--------|
| Move entire repo | **Safe** — scripts use `Path(__file__).parent` |
| Move `services/cognitive-sensor/` | Safe — uses `BASE` variable |
| Move `services/delta-kernel/` | Safe — uses env var, launcher scripts configure path |
| Move `apps/webos-333/` | Safe — self-contained |
| Move `research/uasc-m2m/` | Safe — self-contained |
| Move `.delta-fabric/` | Update `DELTA_DATA_DIR` in launcher scripts |

### 5.4 Import Dependencies

| File | Imports From |
|------|--------------|
| `services/delta-kernel/src/cli/app.ts` | `../core/*` (relative) |
| `services/delta-kernel/src/api/server.ts` | `../cli/storage`, `../core/delta` (relative) |

All TypeScript imports are relative. No absolute imports.

### 5.5 Launcher Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_all.ps1` | Full 4-step pipeline |
| `scripts/run_cognitive.ps1` | Cognitive analysis only |
| `scripts/run_delta_api.ps1` | Delta REST API |
| `scripts/run_delta_cli.ps1` | Delta CLI |

**Pipeline (`run_all.ps1`):**
```
[1/4] Delta API        → http://localhost:3001
[2/4] Cognitive Sensor → cognitive_state.json
[3/4] Daily Projection → data/projections/today.json
[4/4] Push to Delta    → POST /api/ingest/cognitive
```

All launcher scripts set `DELTA_DATA_DIR` to repo-local `.delta-fabric/`.

---

## 6) CONSOLIDATION READINESS SCORECARD — ✅ ALL GREEN

| Category | Status | Reason |
|----------|--------|--------|
| **Path portability** | 🟢 GREEN | All hardcoded paths fixed; CWD-safe subprocess calls |
| **Data boundary clarity** | 🟢 GREEN | delta-kernel and cognitive-sensor are completely isolated |
| **Runtime isolation** | 🟢 GREEN | No shared processes; can run independently |
| **Documentation accuracy** | 🟢 GREEN | PRE_ATLAS_MAP.md and CONTEXT_PACKET.md updated |
| **Monorepo structure** | 🟢 GREEN | `services/`, `apps/`, `research/`, `contracts/`, `scripts/` |
| **Delta data directory** | 🟢 GREEN | Repo-local `.delta-fabric/` via `DELTA_DATA_DIR` env var |
| **Shared contracts** | 🟢 GREEN | `contracts/schemas/` with JSON Schema definitions |
| **Contract validation** | 🟢 GREEN | All exports validated before writing |
| **Daily projection** | 🟢 GREEN | `data/projections/today.json` combines cognitive + directive |
| **C→D bridge** | 🟢 GREEN | `POST /api/ingest/cognitive` updates Delta state |
| **Launcher scripts** | 🟢 GREEN | PowerShell scripts in `scripts/` folder |

---

## 7) DECISIONS MADE

### Resolved Decisions

1. **CWD strategy for cognitive-sensor:**
   - ✅ **Option B chosen:** `refresh.py` hardened with `BASE = Path(__file__).parent.resolve()` and `cwd=BASE` for subprocess calls

2. **Data directory strategy:**
   - ✅ `results.db` stays in `services/cognitive-sensor/` (authoritative conversation data)
   - ✅ `.delta-fabric/` is now repo-local (launcher scripts set `DELTA_DATA_DIR`)

3. **Integration intent:**
   - ✅ delta-kernel and cognitive-sensor are now bridged
   - Shared contracts in `contracts/schemas/` define data exchange formats
   - `POST /api/ingest/cognitive` allows Delta to consume cognitive metrics

4. **Contract enforcement (Phase 2.1):**
   - ✅ `validate.py` module with `require_valid()` function
   - ✅ `export_cognitive_state.py` validates against `CognitiveMetricsComputed.json`
   - ✅ `export_daily_payload.py` validates against `DailyPayload.v1.json`
   - ✅ `build_projection.py` validates against `DailyProjection.v1.json`

5. **Daily projection (Phase 2.2):**
   - ✅ `data/projections/today.json` — single stamped artifact
   - Combines cognitive state + directive in one file

6. **C→D bridge (Phase 2.3):**
   - ✅ `push_to_delta.py` POSTs projection to Delta API
   - ✅ Delta ingests via `POST /api/ingest/cognitive`
   - ✅ `Author` type extended with `'cognitive-sensor'`

### Deferred

- UASC-M2M integration role (standalone research)
- webos-333 integration (standalone demo)

---

## 8) PHASE 5B — CLOSURE MECHANICS (2026-01-09)

### Overview

Phase 5B establishes closure as a **real state-transition event** with automatic mode flips and streak compounding. The system now operates as a sovereign cybernetic constitution.

### Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| Law Genesis Layer | `delta.ts:89-104` | Auto-creates constitutional state branches |
| Closure Endpoint | `server.ts:718-1029` | `POST /api/law/close_loop` |
| Closure Registry | `closures.json` | Persistent closure history + streak stats |
| Physical Closure | `loops_latest.json` → `loops_closed.json` | Real loop removal |
| Mode Engine | `governance_daemon.ts` | Autonomous 15-minute recalculation |
| Streak Engine | `server.ts` + `daemon` | BUILD-only increment, day-end reset |

### Mode Transition Rules

| closure_ratio | Mode | build_allowed |
|---------------|------|---------------|
| ≥ 0.80 | SCALE | true |
| ≥ 0.60 | BUILD | true |
| ≥ 0.40 | MAINTENANCE | false |
| < 0.40 | CLOSURE | false |

### Governance Daemon Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| heartbeat | */5 * * * * | Update daemon status |
| refresh | 0 * * * * | Run cognitive refresh |
| day_start | 0 6 * * * | Reset daily counters, recalc mode |
| day_end | 0 22 * * * | Streak reset if no BUILD closure |
| mode_recalc | */15 * * * * | Autonomous mode governance |

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/law/close_loop` | POST | Canonical closure event |
| `/api/law/acknowledge` | POST | Acknowledge daily order |
| `/api/law/violation` | POST | Log build violation |
| `/api/law/override` | POST | Emergency override with reason |
| `/api/law/archive` | POST | Archive loop without closure |
| `/api/law/refresh` | POST | Trigger cognitive refresh |
| `/api/daemon/status` | GET | Governance daemon status |
| `/api/daemon/run` | POST | Manually trigger daemon job |
| `/api/state/unified` | GET | Merged Delta + Cognitive state |
| `/api/health` | GET | Health check endpoint |
| `/api/work/request` | POST | Request permission to start a job (Phase 6A) |
| `/api/work/complete` | POST | Report job completion (Phase 6A) |
| `/api/work/status` | GET | Query current work state (Phase 6A) |
| `/api/work/cancel` | POST | Cancel a job (Phase 6A) |
| `/api/work/history` | GET | Get job history (Phase 6A) |
| `/api/timeline` | GET | Query events with filters (Phase 6C) |
| `/api/timeline/stats` | GET | Event statistics (Phase 6C) |
| `/api/timeline/day/:date` | GET | All events for a day (Phase 6C) |

### New Files

| File | Purpose |
|------|---------|
| `services/cognitive-sensor/closures.json` | Closure registry with streak stats |
| `services/cognitive-sensor/loops_closed.json` | Archive of closed loops *(created on first closure)* |
| `services/cognitive-sensor/work_ledger.json` | Work admission ledger (Phase 6A) |
| `services/cognitive-sensor/timeline_events.json` | Event log *(created on first system start)* |
| `contracts/schemas/Closures.v1.json` | Closure registry schema |
| `contracts/schemas/WorkLedger.v1.json` | Work ledger schema (Phase 6A) |
| `contracts/schemas/TimelineEvents.v1.json` | Timeline events schema (Phase 6C) |
| `services/delta-kernel/specs/phase-5b-closure-mechanics.md` | Phase 5B specification |
| `services/delta-kernel/specs/phase-6a-work-admission-control.md` | Phase 6A specification |
| `services/delta-kernel/src/core/work-controller.ts` | Work admission controller |
| `services/delta-kernel/src/core/timeline-logger.ts` | Timeline event logger |
| `services/delta-kernel/src/tools/gate.ts` | Gate CLI (Phase 6A.1) |
| `services/delta-kernel/src/tools/gate_client.ts` | Gate client library |
| `services/delta-kernel/src/ui/control.html` | Control panel UI |
| `services/delta-kernel/src/ui/timeline.html` | Timeline viewer UI |

### Key Behaviors

1. **Atomic Closure:** Single delta patches `/enforcement/*`, `/metrics/*`, `/mode`
2. **Idempotency:** Duplicate `loop_id` returns 409 Conflict
3. **BUILD-only Streaks:** Increment only in BUILD/SCALE mode
4. **Day-End Reset:** Streak → 0 if no productive closure
5. **Autonomous Mode:** Recalculated every 15 minutes without closure events

### Design Principles

- **Leaf-patch only:** No subtree replacements
- **Law Genesis:** Parent paths auto-created
- **Contract enforcement:** Closures validated against schema
- **Physical closure:** Loops actually removed from `loops_latest.json`

---

## 9) FIXES APPLIED (all complete)

### Fix 1: `services/cognitive-sensor/export_daily_payload.py` ✅

```python
# BEFORE (broken)
OUT = r"C:\Users\bruke\Downloads\cycleboard\brain\daily_payload.json"

# AFTER (portable)
from pathlib import Path
BASE = Path(__file__).parent.resolve()
OUT = Path.home() / "Downloads" / "cycleboard" / "brain" / "daily_payload.json"
```

### Fix 2: `services/cognitive-sensor/cluster_business_topics.py` ✅

```python
# BEFORE (broken)
conn = sqlite3.connect(r'C:\Users\bruke\My_Workspace\results.db')

# AFTER (portable)
from pathlib import Path
BASE = Path(__file__).parent.resolve()
conn = sqlite3.connect(BASE / "results.db")
```

### Fix 3: `services/cognitive-sensor/refresh.py` ✅

```python
# BEFORE (CWD-dependent)
subprocess.check_call(["python","loops.py"])

# AFTER (CWD-safe)
from pathlib import Path
BASE = Path(__file__).parent.resolve()
def run(script: str):
    subprocess.check_call([sys.executable, script], cwd=BASE)
```

### Fix 4: `services/delta-kernel/src/api/server.ts` ✅

```typescript
// BEFORE (home-only)
const dataDir = path.join(os.homedir(), '.delta-fabric');

// AFTER (env var with fallback)
const dataDir = process.env.DELTA_DATA_DIR || path.join(os.homedir(), '.delta-fabric');
```

---

## 9) PHASE 2 ADDITIONS

### New Files

| File | Purpose |
|------|---------|
| `services/cognitive-sensor/validate.py` | Contract validation module |
| `services/cognitive-sensor/build_projection.py` | Builds `today.json` |
| `services/cognitive-sensor/push_to_delta.py` | POSTs to Delta API |
| `contracts/schemas/DailyProjection.v1.json` | Combined artifact schema |
| `data/projections/today.json` | Daily output artifact |

### New API Endpoint

```
POST /api/ingest/cognitive
Body: DailyProjection JSON
Response: { success: true, mode: "CLOSURE", open_loops: 14 }
```

### Updated Files

| File | Change |
|------|--------|
| `export_cognitive_state.py` | Added contract validation |
| `export_daily_payload.py` | Added contract validation |
| `run_all.ps1` | 4-step pipeline (was 2-step) |
| `server.ts` | Added `/api/ingest/cognitive` endpoint |
| `types.ts` | Added `'cognitive-sensor'` to `Author` type |

---

---

## 11) PHASE 5B FILES MODIFIED

| File | Changes |
|------|---------|
| `services/delta-kernel/src/core/delta.ts` | Added `ensurePathExists()` (Law Genesis Layer) |
| `services/delta-kernel/src/api/server.ts` | Rewrote `/api/law/close_loop` with atomic leaf-patches |
| `services/delta-kernel/src/governance/governance_daemon.ts` | Added `mode_recalc` job, streak reset in `day_end` |
| `services/cognitive-sensor/validate.py` | Added `validate_closures()` function |
| `contracts/schemas/Closures.v1.json` | New schema file |
| `services/delta-kernel/specs/phase-5b-closure-mechanics.md` | New specification |

---

*End of Context Packet — Phase 5B Complete*
