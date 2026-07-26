# Pre Atlas — Simplification Candidates

Generated: 2026-03-10
Method: Repository inspection identifying redundancy, unnecessary abstraction, and merge opportunities.

---

## S1. Remove `lut.ts` (Legacy Router)

**File**: `services/delta-kernel/src/core/lut.ts`
**Evidence**: `routing.ts` is the canonical mode router used by `server.ts`, `governance_daemon.ts`, and `daily-screen.ts`. `lut.ts` uses a different signal set (leverage_balance, streak_days, pending_actions vs sleep_hours, open_loops, assets_shipped, deep_work_blocks, money_delta) and different bucket names (CRITICAL/MANY/DEFICIT vs LOW/OK/HIGH).
**Only consumer**: `renderer.ts` imports MODE_DESCRIPTIONS and MODE_ORDER from `lut.ts`.
**Action**: Move MODE_DESCRIPTIONS and MODE_ORDER to `routing.ts`. Delete `lut.ts`. Update `renderer.ts` import.
**Impact**: Eliminates divergent routing implementation. Reduces confusion for maintainers.

---

## S2. Merge `route_today.py` Into `export_daily_payload.py`

**Files**:
- `services/cognitive-sensor/route_today.py` → writes `daily_directive.txt`
- `services/cognitive-sensor/export_daily_payload.py` → writes `daily_payload.json`

**Evidence**: Both scripts:
1. Read `cognitive_state.json`
2. Apply identical routing thresholds (ratio<15→CLOSURE, open>20→CLOSURE, open>10→MAINTENANCE, else→BUILD)
3. Compute the same mode and risk level

**Action**: Merge into one script that produces both `daily_directive.txt` and `daily_payload.json`. Remove `route_today.py`. Update `refresh.py` to call single script at step 4-5.
**Impact**: Eliminates duplicated routing logic. Reduces refresh pipeline from 10 to 9 steps.

---

## S3. Share `delta.ts` Between Services

**Files**:
- `services/delta-kernel/src/core/delta.ts`
- `services/aegis-fabric/src/core/delta.ts`

**Evidence**: Both implement identical functions: `generateUUID()`, `hashState()`, `createEntity()`, `createDelta()`, `applyPatch()`, `applyDelta()`, `verifyHashChain()`. Copy-pasted with no divergence tracking.

**Action**: Create `contracts/shared/delta.ts` (or a shared npm workspace package). Both services import from shared.
**Alternative**: If merging services (see S7), this resolves automatically.
**Impact**: Single source of truth for delta operations. Bug fixes propagate to both services.

---

## S4. Share Mode Type Across Services

**Files**:
- `services/delta-kernel/src/core/types.ts` — defines `Mode = 'RECOVER' | 'CLOSURE' | 'MAINTENANCE' | 'BUILD' | 'COMPOUND' | 'SCALE'`
- `services/aegis-fabric/src/core/types.ts` — defines identical Mode type independently
- `services/cognitive-sensor/atlas_config.py` — hardcodes mode strings

**Action**: Create `contracts/shared/types.ts` with the Mode enum. Import in both TypeScript services. Export as `contracts/schemas/Mode.json` for Python validation.
**Impact**: Prevents Mode enum drift across languages and services.

---

## S5. Inline `wire_cycleboard.py`

**File**: `services/cognitive-sensor/wire_cycleboard.py`
**Evidence**: The entire script is:
```python
shutil.copy("cognitive_state.json", "cycleboard/brain/cognitive_state.json")
shutil.copy("daily_directive.txt", "cycleboard/brain/daily_directive.txt")
```
Two file copy operations. Called as a separate subprocess in the refresh pipeline.

**Action**: Add these two copy calls to `export_cognitive_state.py` and the merged `export_daily_payload.py` respectively. Remove `wire_cycleboard.py`. Update `refresh.py`.
**Impact**: Eliminates a subprocess spawn for 2 lines of code. Pipeline goes from 10→8 steps (combined with S2).

---

## S6. Fold `build_projection.py` Into `push_to_delta.py`

**Files**:
- `services/cognitive-sensor/build_projection.py` — reads `cognitive_state.json`, wraps it with version/directive metadata, writes `data/projections/today.json`
- `services/cognitive-sensor/push_to_delta.py` — reads `data/projections/today.json`, POSTs to Delta API

**Evidence**: `build_projection.py` adds a thin wrapper (version string + directive fields already computed in `export_daily_payload.py`). The intermediate file `data/projections/today.json` is only consumed by `push_to_delta.py`.

**Action**: Have `push_to_delta.py` read `cognitive_state.json` + `daily_payload.json` directly and construct the projection inline. Remove `build_projection.py`. Delete intermediate file.
**Impact**: Eliminates intermediate file and one subprocess call. Startup goes from 5→4 steps.

---

## S7. Consider Merging delta-kernel + aegis-fabric

**Current state**:
- delta-kernel: TypeScript/Express on port 3001, 45 endpoints
- aegis-fabric: TypeScript/Express on port 3002, ~13 endpoints
- Both use Express 5.2.1, cors 2.8.5, tsx, TypeScript 5.3.0
- Both implement delta.ts (see S3) and Mode types (see S4)
- Both run on same machine, no network separation
- No observed multi-tenant usage (prototype)

**Evidence for merging**:
- aegis-fabric's policy engine could be a middleware layer in delta-kernel
- Agent action endpoints could mount under `/api/v1/agents/` on port 3001
- Eliminates code duplication (delta.ts, types.ts)
- Reduces operational complexity (1 service instead of 2)
- atlas_boot.html only polls port 3001 — it doesn't know about port 3002

**Evidence against merging**:
- Separation enforces policy isolation
- aegis-fabric is designed for multi-tenant operation
- Different release cycles possible

**Recommendation**: Merge for now (prototype stage). Re-separate if multi-tenancy becomes real.

---

## S8. Remove Unintegrated IoT/Streaming Modules

**Modules with type definitions but no runtime wiring**:
| Module | File | Lines |
|---|---|---|
| Delta Sync | delta-sync.ts | ~200 |
| Off-Grid Nodes | off-grid-node.ts | ~100 |
| UI Streaming | ui-stream.ts | ~150 |
| Camera Streaming | camera-stream.ts, camera-surface.ts, camera-renderer.ts, camera-extractor.ts, camera-adapter.ts | ~500 |
| Actuation | actuation.ts, control-surface.ts, device-agent.ts | ~350 |
| Audio | audio-renderer.ts, audio-adapter.ts, codec2-adapter.ts | ~250 |

**Total**: ~1,550 lines of type definitions + supporting code with zero runtime consumers.

**Action**: Move to `services/delta-kernel/src/future/` or `_deferred/`. Remove from `types.ts` (split into `types-core.ts` and `types-iot.ts`). This reduces `types.ts` from 1162 lines to ~600.
**Impact**: Reduces cognitive load. Prevents pre-existing type errors in unused modules from blocking compilation. Specs remain in `specs/` for future reference.

---

## S9. Consolidate Orchestration Entry Points

**Current parallel orchestrators for the same scripts**:
| Entry Point | Scripts Called |
|---|---|
| `refresh.py` | loops, completion_stats, export_cognitive_state, route_today, export_daily_payload, wire_cycleboard, reporter, build_dashboard, build_strategic_priorities, build_docs_manifest |
| `run_daily.py` | loops, completion_stats, export_cognitive_state, route_today, export_daily_payload, wire_cycleboard, reporter, governor_daily |
| `atlas_agent.run_daily()` | Same as run_daily.py (calls scripts via subprocess) |
| `run_weekly.py` | run_daily + classifier_convo + synthesizer + governor_weekly |

**Overlap**: Steps 1-7 are identical between `refresh.py` and `run_daily.py`.

**Action**: Make `refresh.py` the single pipeline. Add `--governance` flag to append governor_daily.py. Make `run_daily.py` call `refresh.py --governance`. Eliminate `atlas_agent._run()` subprocess pattern — have it import and call directly.
**Impact**: Single source of truth for pipeline ordering. Easier to debug and modify.

---

## S10. Replace File-Based State With SQLite

**Current state stores**:
- `.delta-fabric/entities.json` — full entity map, read/written as complete JSON file
- `.delta-fabric/deltas.json` — append-only array, loaded entirely into memory
- `.aegis-data/tenants/{id}/entities.json` — per-tenant entity map
- `cognitive_state.json`, `loops_latest.json`, etc. — intermediate pipeline outputs

**Evidence for SQLite**:
- `results.db` already uses SQLite successfully for the Python side
- JSON file read/write has no locking (causes hash chain forks)
- Full file rewrite on every mutation is inefficient
- SQLite provides transactions, WAL mode for concurrent access, and crash recovery

**Action**: Replace `.delta-fabric/*.json` with `delta.db` (SQLite). Tables: `entities`, `deltas`, `dictionary_tokens`, `dictionary_patterns`, `dictionary_motifs`. Use WAL mode for concurrent reads.
**Impact**: Eliminates file locking issues, hash chain forks, and full-file rewrites.

---

## S11. Eliminate Redundant HTML Dashboards

**Current dashboards**:
| File | Purpose | Accessed Via |
|---|---|---|
| `atlas_boot.html` | Master shell (4 tabs, telemetry, commands) | Direct browser open |
| `cycleboard/index.html` | Operational dashboard | iframe in atlas_boot |
| `dashboard.html` | Analytics dashboard | iframe in atlas_boot (telemetry panel) |
| `control_panel.html` | Control interface | iframe in atlas_boot |
| `cognitive_atlas.html` | 84K-point visualization | iframe in atlas_boot |
| `idea_dashboard.html` | Idea registry | iframe in atlas_boot |
| `docs_viewer.html` | Documentation browser | iframe in atlas_boot |
| `services/delta-kernel/src/ui/control.html` | Delta control panel | Served by delta-kernel API |
| `services/delta-kernel/src/ui/timeline.html` | Timeline visualization | Served by delta-kernel API |
| `services/delta-kernel/web/` | React app (port 5173) | Vite dev server |

**Evidence**: 10 separate HTML/JS interfaces. The React web app and the delta-kernel control.html overlap with atlas_boot.html functionality. CycleBoard duplicates data already shown in atlas_boot.

**Action**: Audit which dashboards are actively used. Consider consolidating into atlas_boot.html + 2-3 specialized views.
**Impact**: Reduces maintenance surface. Fewer files to keep in sync with state format changes.
