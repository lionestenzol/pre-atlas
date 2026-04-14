# Pre Atlas — Architecture Briefing (Missing System Knowledge)

Generated: 2026-03-10 | Updated: 2026-03-11 (stabilization: unified routing, SQLite, retries)
Purpose: Extract undocumented architecture from UI, API handlers, daemon logic, and state files.
Target: Another reasoning model (DeepSeek) that cannot access the repository.

---

## 1. CycleBoard UI Architecture

### 1.1 Framework

Vanilla JavaScript (no framework). Styling: Tailwind CSS 3.4.1 (CDN) + FontAwesome 6.4.0 (CDN) + custom CSS. No build step. Loaded directly in browser.

### 1.2 Module Load Order (11 JS files)

```
1. js/state.js         — CycleBoardState class (state management + persistence)
2. js/validator.js     — DataValidator class (input validation)
3. js/ui.js            — UI utilities (toast, modal, spinner, progress ring)
4. js/helpers.js       — Calculation helpers (progress, streaks, formatting)
5. js/screens.js       — Screen renderers (10 screens)
6. js/functions.js     — Action functions (task CRUD, day planning, routines)
7. js/cognitive.js     — CognitiveController (behavioral governance overlay)
8. js/strategic.js     — StrategicRouter (leverage-based daily directive)
9. js/ai-context.js    — AIContext (machine-readable state snapshots)
10. js/ai-actions.js   — AIActions (programmatic action API for LLMs)
11. js/app.js          — Initialization (create state, dark mode, boot controllers)
```

### 1.3 Component Tree

```
body
├── #cognitive-directive        ← CognitiveController banner (sticky, z-50)
│   ├── directive-mode          ← Mode text (CLOSURE/MAINTENANCE/BUILD)
│   ├── directive-risk          ← Risk badge (HIGH/MEDIUM/LOW)
│   ├── directive-loops         ← Open loop count
│   └── directive-action        ← Primary action text
├── #cognitive-indicator        ← Pulsing dot indicator (fixed top-right, hidden)
├── #strategic-directive        ← StrategicRouter banner (sticky, z-49)
│   ├── primary_focus
│   ├── cluster_id
│   ├── deep_block_mins
│   └── primary_action
├── #app
│   ├── header (mobile only)
│   │   └── #mobile-menu-toggle
│   ├── #sidebar (w-64, fixed)
│   │   ├── #nav (10 screen buttons)
│   │   ├── Weekly Progress section (#weekly-progress-bar)
│   │   └── Utilities (Copy AI Context, Export, Import, Clear)
│   ├── #main-content (renders active screen)
│   └── nav (mobile bottom bar, 4 buttons)
├── #modal-container (z-50)
└── #toast-container (fixed bottom-right, z-50)
```

### 1.4 State Management

**Class**: `CycleBoardState` (state.js)

**Persistence**: `localStorage` key `cycleboard-state`. Debounced saves (1000ms). QuotaExceededError handling with automatic cleanup.

**Undo/Redo**: History stack (max 50 deep copies). `pushHistory()` on every `update()`. `undo()`/`redo()` restore from history.

**State Schema (v2.0)**:
```javascript
{
  version: '2.0',
  screen: 'Home',                    // Active screen name
  AZTask: [],                        // Monthly A-Z tasks [{id, letter, task, notes, status, createdAt}]
  DayPlans: {                        // Date-keyed day plans
    '2026-03-10': {
      date: '2026-03-10',
      type: 'A',                     // A=Optimal, B=Low energy, C=Chaos
      time_blocks: [{id, time, title, completed, duration}],
      goals: { baseline: '', baseline_completed: false, stretch: '', stretch_completed: false },
      routines_completed: { Morning: {completed,steps:[]}, Commute: {...}, Evening: {...} },
      rating: null,                  // 0-5 end-of-day rating
      notes: ''
    }
  },
  FocusArea: ['Production','Image','Growth','Personal','Errands','Network'],
  Routine: {
    Morning: { steps: ['Wake 5:30','Cold shower','Review plan','Deep work block 1'], active: true },
    Commute: { steps: ['Review goals','Listen to audiobook'], active: true },
    Evening: { steps: ['Journal','Review tomorrow','Devices off by 10pm'], active: true }
  },
  DayTypeTemplates: {
    A: { time_blocks: [{time,title,duration}...], goals: {baseline,stretch}, routines: ['Morning','Commute','Evening'] },
    B: { ... },  // Low energy variant
    C: { ... }   // Chaos variant
  },
  Settings: { darkMode: true, notifications: true, autoSave: true, defaultDayType: 'A' },
  History: { completedTasks: [], productivityScore: 0, streak: 0, timeline: [] },
  Journal: [],                       // [{id,date,title,content,type,mood,createdAt}]
  EightSteps: {},                    // Date-keyed step tracking
  Contingencies: { runningLate:{}, lowEnergy:{}, freeTime:{}, disruption:{} },
  Reflections: { weekly:[], monthly:[], quarterly:[], yearly:[] },
  MomentumWins: []                   // [{id,text,date,createdAt}]
}
```

**Migration**: On load, detects v1 (array-based DayPlans) → converts to v2 (object-keyed). Ensures all new properties exist.

**Cleanup**: Removes DayPlans older than 30 days. Trims completed tasks to 50. Trims timeline to 100.

### 1.5 Polling Mechanisms

CycleBoard has **NO polling intervals**. All updates are event-driven (user clicks → state mutation → render). The two external controllers load data once on boot:

| Controller | File Loaded | Timing | Fallback |
|---|---|---|---|
| CognitiveController | `cognitive_state.json` (relative path) | Once on DOMContentLoaded | 404 = silently ignore, keep banner hidden |
| StrategicRouter | `brain/strategic_priorities.json` | Once on DOMContentLoaded | 404 = silently ignore, no directive |

### 1.6 CognitiveController (cognitive.js)

**Purpose**: Behavioral governance overlay in CycleBoard.

**Data source**: `cognitive_state.json` (loaded via fetch, relative path from cycleboard/).

**Mode calculation** (FOURTH independent routing implementation):
```javascript
if (closure.ratio < 15)     → mode = 'CLOSURE',      risk = 'HIGH'
else if (closure.open > 10) → mode = 'MAINTENANCE',   risk = 'MEDIUM'
else                        → mode = 'BUILD',          risk = 'LOW'
```

**DOM effects**:
- Banner colors: red (CLOSURE), yellow/amber (MAINTENANCE), green (BUILD)
- Indicator dot: pulsing circle in mode color (top-right fixed)
- Sidebar risk badge: `bg-red-100`/`bg-yellow-100`/`bg-green-100`

**Exposed API**:
- `getMode()` → string
- `getRisk()` → string
- `getOpenLoops()` → array
- `isClosureMode()` → boolean

### 1.7 StrategicRouter (strategic.js)

**Purpose**: Leverage-based daily directive computed from cluster analysis.

**Data source**: `brain/strategic_priorities.json`.

**Banner injection**: Below cognitive banner (z-49). Shows primary_focus, cluster_id, suggested deep block minutes, gap classification, primary action.

**Gap color mapping**:
- `high_leverage_low_execution` → indigo
- `high_leverage_high_execution` → emerald
- `balanced` → slate
- `low_leverage_low_execution` → gray

**Methods**:
- `getTopCluster()` → first ranked cluster
- `getDailyDirective()` → directive object
- `getFocusAreaWeights()` → weights by area name
- `suggestAZOverride()` → find unfinished task matching top_ngrams
- `suggestTimeBlock()` → time block suggestion from directive
- `renderStrategicCard()` → HTML card for Home screen
- `reweightFocusAreas()` → sort FocusArea[] by strategic weights

### 1.8 AI Context System (ai-context.js + ai-actions.js)

**AIContext.getContext()** returns full structured snapshot:
```javascript
{
  _meta: { generated_at, version, source },
  temporal: { today, dayOfWeek, currentTime },
  navigation: { currentScreen, availableScreens },
  todayPlan: { dayType, goals, timeBlocks, routines },
  progress: { overall, breakdown, streak, weeklyAverage },
  tasks: { all, summary, byStatus, availableLetters },
  routines: { definitions, todayCompletion },
  focusAreas: { areas, summary },
  journal: { totalEntries, recentEntries },
  history: { recentActivity, completedTasksCount, streak },
  weeklyStats: { completed, total, percentage },
  cognitive: { mode, risk, openLoops, isClosureMode },
  dayTypeTemplates: { A, B, C },
  reflections: { counts, recent },
  momentumWins: { todayWins }
}
```

**AIActions** provides programmatic API:
- `createTask(letter, text, notes)` → `{success, taskId}`
- `completeTask(taskId)` → `{success, task}`
- `setDayType(type, applyTemplate)` → `{success, dayType}`
- `setGoals(baseline, stretch)` → `{success, plan}`
- `addTimeBlock(time, title, duration)` → `{success, blockId}`
- `createJournalEntry(title, content, type, mood)` → `{success, id}`
- `addMomentumWin(text)` → `{success, id}`
- `completeRoutineStep(routineName, stepIndex)` → `{success}`

### 1.9 Screens (10 total)

| Screen | Purpose | Key Renders |
|---|---|---|
| Home | Dashboard overview | A-Z progress ring, weekly metric, today's progress (weighted), strategic card, streak tracker, 7-day history, routine cards, momentum wins |
| Daily | Day planning | Day type selector (A/B/C), time blocks (add/edit/complete/delete), goals (baseline+stretch) |
| AtoZ | Monthly task grid | A-Z letter tasks, filter (all/completed/in-progress/not-started), search |
| WeeklyFocus | Focus area management | 6 focus areas with strategic weight badges |
| Reflections | Periodic reviews | Weekly/monthly/quarterly/yearly reflection entries |
| Timeline | Activity log | Chronological activity history from `History.timeline` |
| Routines | Routine management | Morning/Commute/Evening routines with step editing |
| Journal | Journaling | Entries with title, content, type, mood |
| Statistics | Analytics | Progress charts, completion rates, streak data |
| Settings | Configuration | Dark mode toggle, auto-save, default day type |

### 1.10 Progress Calculation (helpers.js)

**Weighted composite** (4 categories):
```
Progress = Time Blocks (30%) + Goals (30%) + Routines (25%) + Focus Areas (15%)
```

**Milestone toasts** at 25%, 50%, 75%, 100% (once per threshold per day, tracked in localStorage).

**Streak**: Count of consecutive days with progress ≥ 70%.

### 1.11 Event Handlers Summary

| User Action | Handler | Side Effects |
|---|---|---|
| Click nav button | `navigate(screen)` | Set state.screen, render, hide mobile sidebar |
| Complete A-Z task | `completeTask(id)` | Set status=COMPLETED, log activity, save, render, toast |
| Delete A-Z task | `deleteTask(id)` | Filter from array, log activity, save, render, toast |
| Set day type | `setDayType(type, apply)` | Modal if changing, optionally apply template, save |
| Add time block | `addTimeBlock()` | Create block with auto-id, save, render |
| Toggle time block | `toggleTimeBlockCompletion(id)` | Flip completed, save, render |
| Complete goal | `completeGoal(goalType)` | Flip completed, log, save, render |
| Add momentum win | `addMomentumWin()` | Modal for input, append to MomentumWins, save |
| Copy AI context | button click | `AIContext.getClipboardSnapshot()` → clipboard |
| Export data | button click | Download state as JSON file |
| Import data | button click | File input → validate → merge, save |
| Clear data | button click | Confirm → reset to defaults |
| Toggle dark mode | button click | Toggle `dark` class on html, update Settings |

---

## 2. Full API Surface

### 2.1 Unified State

**`GET /api/state/unified`**

Request: none

Response:
```json
{
  "ok": true,
  "ts": "ISO timestamp",
  "delta": {
    "system_state": { "mode":"SCALE", "sleep_hours":8, "open_loops":0, ... } | null
  },
  "cognitive": {
    "cognitive_state": { "state":{...}, "loops":[...], "drift":{...}, "closure":{...} } | null,
    "loops_latest": [ {"convo_id","title","score"} ... ] | null,
    "today": { "cognitive":{...}, "directive":{...} } | null,
    "closures": { "closures":[], "stats":{} } | null
  },
  "derived": {
    "mode": "CLOSURE|MAINTENANCE|BUILD|SCALE|RECOVER|COMPOUND",
    "risk": "HIGH|MEDIUM|LOW",
    "open_loops": number,
    "closure_ratio": decimal (0-1),
    "primary_order": string,
    "build_allowed": boolean,
    "enforcement_level": 0|1|2|3,
    "violations_count": number,
    "overrides_count": number,
    "override_available": boolean,
    "closures_today": number,
    "total_closures": number,
    "streak_days": number,
    "best_streak": number
  },
  "errors": ["file read errors if any"]
}
```

Side effects: none (read-only merge of 4 files + delta state).

**Derivation priority** (each field checked in order, first non-null wins):
- mode: `today.json.directive.mode` → `deltaState.mode` → `'RECOVER'`
- risk: `today.json.directive.risk` → `deltaState.risk` → `'MEDIUM'`
- open_loops: `cognitive_state.closure.open` → `today.json.cognitive.closure.open` → `deltaState.open_loops` → `0`
- closure_ratio: raw value from cognitive/today/delta; if > 1 then ÷ 100 (normalization)
- build_allowed: `today.json.directive.build_allowed` → `deltaState.build_allowed` → `!(mode==='CLOSURE')`
- enforcement_level: `Math.min(violations_count, 3)`
- override_available: `enforcementLevel < 3 OR overridesCount === 0`

### 2.2 System State

**`GET /api/state`** — Returns `{mode, sleepHours, openLoops, leverageBalance, streakDays}` from first system_state entity. Defaults if none exist.

**`PUT /api/state`** — Body: `{mode, sleepHours, openLoops, leverageBalance, streakDays}`. Creates or updates system_state entity with delta.

### 2.3 Tasks

**`GET /api/tasks`** — Returns array of `{id, title, status, priority, createdAt}`.

**`POST /api/tasks`** — Body: `{title (required), priority: "NORMAL"|"HIGH"}`. Creates task entity with status `OPEN`.

**`PUT /api/tasks/:id`** — Body: `{status?, priority?}`. If status=`DONE`, sets `closed_at`. Direct state write (NO delta created for task updates).

**`DELETE /api/tasks/:id`** — Soft delete: marks as `ARCHIVED`.

### 2.4 Cognitive Ingestion

**`POST /api/ingest/cognitive`**

Body:
```json
{
  "cognitive": { "closure": { "open": number, "ratio": number } },
  "directive": { "mode": string, "risk": string, "build_allowed": boolean, "primary_action": string, "open_loop_count": number, "closure_ratio": number }
}
```

Side effects: Creates/updates system_state entity via delta with `{mode, open_loops, closure_ratio, risk, build_allowed, primary_action, last_ingest}`.

Response: `{success, mode, open_loops}`.

### 2.5 Law Endpoints

**`POST /api/law/acknowledge`** — Body: `{order: string}`. Updates `last_acknowledged_at`, `last_acknowledged_order`.

**`POST /api/law/archive`** — Body: `{loop_id?, loop_title?, reason?}`. Appends to `archived_loops` array via delta. Requires loop_id OR loop_title.

**`POST /api/law/refresh`** — Body: empty. Records `last_refresh_requested_at`.

**`POST /api/law/violation`** — Body: `{action (required), context?}`. Increments `enforcement.violations_count`, appends to `violation_log`. Response includes `enforcement_level`.

**`POST /api/law/override`** — Body: `{reason (required)}`. Increments `enforcement.overrides_count`, appends to `override_log`.

**`POST /api/law/close_loop`** (Phase 5B — most complex endpoint)

Body: `{loop_id?, title?, outcome: "closed"|"archived" (required)}`

Logic (7 steps):
1. **Idempotency**: If loop_id already in closures.json → 409 Conflict
2. **Registry write**: Append to closures.json, increment total_closures, update closures_today (count today's entries), update last_closure_at. Durable write to disk BEFORE delta.
3. **Ratio computation**: `closureRatio = closedLoops / (openLoops + closedLoops)` (or 1 if total=0). Open loops from cognitive_state.json.
4. **Mode transition** (thresholds):
   - ratio ≥ 0.8 → SCALE, build_allowed=true
   - ratio ≥ 0.6 → BUILD, build_allowed=true
   - ratio ≥ 0.4 → MAINTENANCE, build_allowed=false
   - ratio < 0.4 → CLOSURE, build_allowed=false
5. **Streak** (BUILD-only gating): Only increment if today's first closure AND new mode is BUILD/SCALE. Update `last_streak_date`, `best_streak`.
6. **Physical removal**: Remove from `loops_latest.json`, append to `loops_closed.json`. Best-effort (non-fatal on error).
7. **Atomic delta**: All mutations in ONE delta: reset violations_count→0, append closure_log, update metrics (closed_total, ratio, open_loops, closures_today), update mode+build_allowed (if changed), update streak (if incremented).

Response:
```json
{
  "success": true,
  "closure": { "ts", "loop_id", "title", "outcome" },
  "metrics": { "closed_loops_total", "closure_ratio", "open_loops", "closures_today" },
  "mode": string,
  "mode_changed": boolean,
  "build_allowed": boolean,
  "violations_reset": true,
  "streak": { "days", "updated", "best", "build_only": true },
  "physical_closure": "attempted"|"skipped"
}
```

### 2.6 Work Admission (Phase 6A)

**`POST /api/work/request`** — Body: `{job_id?, type: "human"|"ai"|"system", title, agent?, weight: 1-10, depends_on: [], timeout_ms?, metadata?}`.

Three-stage admission:
1. MODE gate: CLOSURE+ai → DENY. !build_allowed+non-system → DENY.
2. DEPENDENCY gate: unmet deps → QUEUE.
3. CAPACITY gate: active weight > max_concurrent → QUEUE or DENY.

Response: `{status: "APPROVED"|"QUEUED"|"DENIED", job_id, ...}`.

**`POST /api/work/complete`** — Body: `{job_id, outcome: "completed"|"failed"|"abandoned", result?, error?, metrics: {duration_ms?, tokens_used?, cost_usd?}}`. Advances queue on completion.

**`GET /api/work/status`** — Returns capacity, active jobs, queued jobs, mode context.

**`POST /api/work/cancel`** — Body: `{job_id, reason?}`. Cancels and advances queue.

**`GET /api/work/history`** — Returns last 20 completed jobs + stats.

### 2.7 Timeline (Phase 6C)

**`GET /api/timeline`** — Query: `{from?, to?, type?, source?, limit?}`. Returns events sorted newest-first.

**`GET /api/timeline/stats`** — Returns `{total, by_type, by_source, first_event, last_event}`.

**`GET /api/timeline/day/:date`** — Returns events for YYYY-MM-DD.

### 2.8 System

**`GET /api/health`** — Returns `{ok, ts, version: "1.0.0", service: "delta-kernel"}`.

**`GET /api/daemon/status`** — Returns daemon state (running, heartbeat, job history, current job).

**`POST /api/daemon/run`** — Body: `{job: "heartbeat"|"refresh"|"day_start"|"day_end"}`. Manually trigger daemon job.

**`GET /api/stats`** — Returns storage statistics.

---

## 3. Data Schemas (Real Examples)

### 3.1 .delta-fabric/entities.json

Two entities exist. Primary system_state (version 1220):
```json
{
  "a3780988-3a6c-47c4-b4d2-3d02ea802261": {
    "entity": {
      "entity_id": "a3780988-3a6c-47c4-b4d2-3d02ea802261",
      "entity_type": "system_state",
      "created_at": 1767813873733,
      "current_version": 1220,
      "current_hash": "fb3724babadfe480f7210f732306bbd70dea657658dcd777f1a4c069074d4e52",
      "is_archived": false
    },
    "state": {
      "mode": "SCALE",
      "sleep_hours": 8,
      "open_loops": 0,
      "leverage_balance": 136,
      "streak_days": 66,
      "last_acknowledged_at": 1767921418762,
      "last_acknowledged_order": "Close or archive: Extrinsic vs Intrinsic Rewards",
      "last_refresh_requested_at": 1767930946126,
      "daemon": {
        "last_heartbeat": 1768204200030,
        "running": true,
        "last_refresh": 1768201202053,
        "refresh_output": "Running radar...\nSTATE_HISTORY.md updated...\nBuilt dashboard.html\nRefreshed."
      },
      "day": {
        "current_date": "2026-01-11",
        "started_at": 1768132800237,
        "status": "closed",
        "ended_at": 1768190400048
      }
    }
  }
}
```

### 3.2 .delta-fabric/deltas.json

Array of RFC 6902 patch objects with SHA256 hash chain:
```json
[
  {
    "delta_id": "550e8400-e29b-41d4-a716-446655440000",
    "entity_id": "a3780988-3a6c-47c4-b4d2-3d02ea802261",
    "timestamp": 1768195200023,
    "author": "governance_daemon",
    "patch": [
      {
        "op": "replace",
        "path": "/daemon",
        "value": {
          "last_heartbeat": 1768195200023,
          "running": true,
          "last_refresh": 1768194002114,
          "refresh_output": "..."
        }
      }
    ],
    "prev_hash": "a1b2c3d4e5f6...",
    "new_hash": "f7g8h9i0j1k2..."
  }
]
```

### 3.3 .delta-fabric/dictionary.json

**DOES NOT EXIST**. The Matryoshka dictionary (token/pattern/motif tiers) is defined in types.ts and dictionary.ts but has never been populated at runtime. Only entities.json and deltas.json exist in .delta-fabric/.

### 3.4 cognitive_state.json

```json
{
  "state": {
    "first_activity": "2024-08-21",
    "last_activity": "2025-03-12",
    "total_convos": 1397
  },
  "loops": [
    {"convo_id": "143", "title": "AI Workflow Orchestration", "score": 21538},
    {"convo_id": "1216", "title": "Cleaning Reflections and Feelings", "score": 20135},
    {"convo_id": "1141", "title": "Prompt Creation Collaboration", "score": 19611},
    {"convo_id": "359", "title": "Introduction to Binary Code", "score": 18960},
    {"convo_id": "1226", "title": "Selfish Interactions Narrative", "score": 18949},
    {"convo_id": "969", "title": "ChatGPT and Isolation", "score": 18288},
    {"convo_id": "986", "title": "Fear of Success Cycle", "score": 18265}
  ],
  "drift": {
    "like": 48182, "just": 35978, "execution": 35568, "what": 28081,
    "can": 24290, "system": 22367, "but": 22154, "data": 20818,
    "because": 18434, "people": 15670
  },
  "closure": {
    "open": 7,
    "closed": 18,
    "ratio": 72.0
  }
}
```

### 3.5 daily_payload.json

```json
{
  "mode": "BUILD",
  "build_allowed": true,
  "primary_action": "Create freely.",
  "open_loops": [
    "AI Workflow Orchestration",
    "Cleaning Reflections and Feelings",
    "Prompt Creation Collaboration",
    "Introduction to Binary Code",
    "Selfish Interactions Narrative"
  ],
  "open_loop_count": 7,
  "closure_ratio": 72.0,
  "risk": "LOW",
  "generated_at": "2026-02-12"
}
```

### 3.6 closures.json

```json
{
  "closures": [
    {
      "ts": 1767933809593,
      "loop_id": null,
      "title": "Phase 5B Test Closure",
      "outcome": "closed"
    }
  ],
  "stats": {
    "total_closures": 1,
    "closures_today": 1,
    "last_closure_at": 1767933809593,
    "streak_days": 1,
    "last_streak_date": "2026-01-08",
    "best_streak": 1
  }
}
```

### 3.7 governance_state.json

```json
{
  "generated_at": "2026-02-12T20:02:44.276928",
  "date": "2026-02-12",
  "mode": "BUILD",
  "risk": "LOW",
  "build_allowed": true,
  "north_star": {
    "weekly": "Ship 1 asset (doc, tool, GPT, chapter, client deliverable)",
    "monthly": "Generate revenue from AI consulting or products",
    "system": "Increase closure_ratio, decrease active_lanes",
    "guard": "Block new ideas unless current lane is shipped or archived"
  },
  "active_lanes": [
    {"id": "lane_1", "name": "Power Dynamics Book + Companion GPT", "status": "not_started"},
    {"id": "lane_2", "name": "AI Automation Consulting (First Client)", "status": "not_started"}
  ],
  "lane_violations": [
    {"idea": "...", "priority": 0.87, "action": "park", "reason": "Above moratorium threshold"}
  ],
  "targets": {
    "max_active_lanes": 2, "weekly_ship_target": 1, "min_closure_ratio": 15.0,
    "max_open_loops": 20, "idea_moratorium": true, "max_research_minutes": 30,
    "min_build_minutes": 90, "daily_work_blocks": 3
  },
  "guardrails": { "idea_moratorium": true, "max_lanes": 2 }
}
```

### 3.8 strategic_priorities.json

```json
{
  "generated": "2026-02-22T...",
  "mode": "BUILD",
  "risk": "LOW",
  "open_loops": 7,
  "closure_ratio": 0.72,
  "top_clusters": [
    {
      "rank": 1, "cluster_id": 121,
      "label": "The Concept of a Zero-Space AI-to-AI Language",
      "normalized_leverage": 10.0, "execution_ratio": 0.02,
      "reusability_index": 1.0, "market_score": 1.0,
      "asset_vector": "Tool", "revenue_tag": "productizable",
      "focus_area": "Production",
      "gap": "high_leverage_low_execution",
      "directive": "Build MVP",
      "top_ngrams": ["ai", "language", "system", "protocol"]
    }
  ],
  "focus_area_weights": {
    "Production": {"weight": 10.0, "clusters": [121,110,70], "reason": "Highest leverage clusters"},
    "Image": {"weight": 6.4, "clusters": [...], "reason": "..."},
    "Growth": {"weight": 3.6, "clusters": [...], "reason": "..."},
    "Personal": {"weight": 0.0}, "Errands": {"weight": 0.0}, "Network": {"weight": 0.0}
  },
  "daily_directive": {
    "primary_focus": "Production",
    "primary_cluster": 121,
    "primary_action": "Build MVP for Zero-Space AI-to-AI Language",
    "suggested_deep_block_mins": 60,
    "stretch_goal": "Prototype parser",
    "mode_escalation": null
  }
}
```

### 3.9 completion_stats.json

```json
{
  "closed_week": 3,
  "archived_week": 14,
  "closed_life": 3,
  "archived_life": 15,
  "closure_ratio": 16.7
}
```

---

## 4. Client → Server Interaction Flows

### 4.1 atlas_boot.html Unified State Polling (every 30 seconds)

```
atlas_boot.html
  │
  ├── setInterval(30000ms)
  │     │
  │     ├── loadUnifiedState()
  │     │     GET http://localhost:3001/api/state/unified
  │     │     │
  │     │     └── Update DOM:
  │     │           • #metric-mode: text + CSS class (mode-closure/maintenance/build/scale)
  │     │           • #metric-risk: text + CSS class (risk-high/medium/low)
  │     │           • #metric-loops: number
  │     │           • #metric-ratio: formatted as XX.X% (derived.closure_ratio * 100)
  │     │           • #metric-enforcement: badge (CLEAR/WARN/LOCKED/HARD LOCK)
  │     │           • #metric-closures: number, color (green≥3, yellow 1-2, gray 0)
  │     │           • #metric-streak: number, color (gold≥7, green≥3, yellow<3)
  │     │               tooltip: "Best: Xd | Total: Y"
  │     │           • #primary-order: text from derived.primary_order
  │     │           • Cache systemState object for command handlers
  │     │
  │     └── loadDaemonStatus()
  │           GET http://localhost:3001/api/daemon/status
  │           │
  │           └── Update #daemon-status:
  │                 • Running job → yellow dot + "Running: {job}"
  │                 • Active → green dot + "Daemon Active (Xs ago)"
  │                 • Stopped → red dot + "Daemon Stopped"
  │                 • Offline → no dot + "Daemon Offline"
  │
  └── On error: Show notification with instruction to run .\scripts\run_delta_api.ps1
```

### 4.2 atlas_boot.html Command Actions

```
[Acknowledge] button click
  → acknowledgeOrder()
    → POST /api/law/acknowledge { order: <#primary-order text> }
    → Success: notification + reload unified state
    → Failure: error notification

[Archive Loop] button click
  → archiveLoop()
    → Browser prompt("Why archive?")
    → POST /api/law/archive { loop_title: <from systemState>, reason: <user input> }
    → Success: notification + reload unified state

[Refresh] button click
  → refreshSystem()
    → Browser confirm("Run full refresh?")
    → POST /api/law/refresh {}
    → Success: notification with instruction to run .\scripts\run_all.ps1

[System Control] button click
  → openControlModal()
    → Display overlay modal with iframe → services/cognitive-sensor/control_panel.html

[Enter Desktop] button click
  → enterDesktop()
    → Full-screen overlay with iframe → apps/webos-333/web-os-simulator.html
```

### 4.3 atlas_boot.html Keyboard Shortcuts

```
Escape  → closeControlModal() + exitDesktop()
Ctrl+D  → enterDesktop()
Ctrl+R  → refreshSystem() (with confirmation)
```

### 4.4 atlas_boot.html Tab Switching

```
Tab click → switchTab(tabName)
  cycleboard → iframe src = services/cognitive-sensor/cycleboard/index.html
  control    → iframe src = services/cognitive-sensor/control_panel.html
  atlas      → iframe src = services/cognitive-sensor/cognitive_atlas.html
  docs       → iframe src = services/cognitive-sensor/docs_viewer.html
```

### 4.5 control.html Work Status Polling (every 5 seconds)

```
control.html (served at /control/ by delta-kernel)
  │
  └── setInterval(5000ms)
        GET /api/work/status
        │
        └── Update DOM:
              • Mode badge + build_allowed indicator
              • Closure ratio display
              • Active jobs capacity bar (current / max_concurrent)
              • Queue depth bar (current / max_queue)
              • Active jobs table (job_id, title, type, elapsed, timeout)
              • Queued jobs table (job_id, title, priority)
              • Recent completions table (last 5, outcome badge)
```

### 4.6 timeline.html Event Polling (every 10 seconds)

```
timeline.html (served at /control/ by delta-kernel)
  │
  └── setInterval(10000ms)
        ├── GET /api/timeline/stats → total events, by_type breakdown
        └── GET /api/timeline?limit=50&type={filter}
              │
              └── Render timeline:
                    • Color-coded dots per event type
                    • Relative timestamps ("5m ago")
                    • Formatted data (job details, mode transitions, closure ratios)
                    • Filter dropdown: WORK_*, MODE_CHANGED, LOOP_*, SYSTEM_START
```

### 4.7 CycleBoard (No Server Communication)

```
CycleBoard operates entirely on localStorage.
No fetch calls to delta-kernel API.
No polling intervals.

Data flow:
  User click → handler function → mutate state → stateManager.update()
    → pushHistory() (undo stack)
    → saveDebounced() (1000ms timer)
      → localStorage.setItem('cycleboard-state', JSON.stringify(state))
    → render() (re-render current screen)
    → UI.showToast() (optional feedback)

External data (loaded once on boot):
  cognitive_state.json → CognitiveController (governance banner)
  brain/strategic_priorities.json → StrategicRouter (leverage banner)
```

### 4.8 Loop Closure End-to-End Flow

```
User clicks [Archive Loop] in atlas_boot.html
  │
  ├── 1. archiveLoop() prompts user for reason
  ├── 2. POST /api/law/archive { loop_title, reason }
  │       │
  │       ├── server.ts: Create archive entry
  │       ├── Append to system_state.archived_loops via delta
  │       └── Return { success, archived }
  │
  ├── 3. atlas_boot.html shows success notification
  └── 4. loadUnifiedState() re-polls GET /api/state/unified
          │
          └── UI updates all 7 metrics + primary order

--- OR for canonical closure ---

POST /api/law/close_loop { loop_id, title, outcome: "closed" }
  │
  ├── 1. Idempotency check against closures.json
  ├── 2. Append to closures.json (durable write)
  ├── 3. Compute new closure_ratio
  ├── 4. Determine new mode (CLOSURE→MAINTENANCE→BUILD→SCALE)
  ├── 5. Increment streak (BUILD/SCALE only, first daily closure only)
  ├── 6. Remove from loops_latest.json, append to loops_closed.json
  ├── 7. Create ONE atomic delta with all state mutations
  │       • Reset violations_count → 0
  │       • Update metrics (ratio, open_loops, closures_today)
  │       • Update mode + build_allowed (if changed)
  │       • Update streak (if incremented)
  └── 8. Return comprehensive response with all new values
```

---

## 5. State Storage Model

### 5.1 .delta-fabric/entities.json

**Format**: `Map<UUID, {entity: EntityMeta, state: any}>`

**Current content**: 2 entities (both `system_state` type).
- Primary entity: version 1220, hash `fb3724...`, contains mode/signals/daemon/day/enforcement state.
- Secondary entity: version 1, heartbeat-only state (artifact from daemon creating new entity instead of updating existing).

**Read by**: `server.ts` (all GET endpoints, unified state assembly), `governance_daemon.ts` (mode recalc, day start/end).

**Written by**: `server.ts` (PUT state, POST tasks, POST law/*, POST work/*), `governance_daemon.ts` (all 6 cron jobs via `updateSystemState()`).

**Write mechanism**: Full file rewrite via `JSON.stringify()` → `fs.writeFileSync()`. No locking.

### 5.2 .delta-fabric/deltas.json

**Format**: `Delta[]` (JSON array, append-only).

**Current content**: ~1220 entries (matching primary entity version count).

**Each entry**: `{delta_id, entity_id, timestamp, author, patch: [{op, path, value}...], prev_hash, new_hash}`

**Hash chain**: Each delta's `prev_hash` matches the entity's `current_hash` before mutation. `new_hash` is SHA256 of the resulting state. Genesis delta has `prev_hash` = 64 zeros.

**Known issue**: 10 fork points from concurrent writes (no file locking between server HTTP handlers and daemon cron jobs).

**Read by**: `server.ts` (reconstruction, verification), `storage.ts` (load).

**Written by**: `storage.ts` via `appendDelta()` — reads entire file, parses, pushes new entry, writes entire file back. Not a true append — full file rewrite.

### 5.3 .delta-fabric/dictionary.json

**DOES NOT EXIST at runtime**. The Matryoshka dictionary system (Token → Pattern → Motif tiers) has TypeScript type definitions in `types.ts` and operations in `dictionary.ts`, but no runtime code path creates or populates this file. Only `entities.json` and `deltas.json` exist in `.delta-fabric/`.

### 5.4 closures.json (cognitive-sensor workspace)

**Format**: `{closures: ClosureEntry[], stats: ClosureStats}`

**Written by**: `server.ts` POST /api/law/close_loop (durable write before delta creation).

**Read by**: `server.ts` GET /api/state/unified (merged into derived fields), `governance_daemon.ts` runDayStart (reset closures_today), runDayEnd (streak sovereignty check), runModeRecalc (ratio computation).

**Key fields in stats**: `total_closures`, `closures_today`, `last_closure_at`, `streak_days`, `last_streak_date`, `best_streak`.

### 5.5 Other State Files

| File | Written By | Read By | Lifecycle |
|---|---|---|---|
| `loops_latest.json` | `loops.py` | `server.ts` (unified state), close_loop (physical removal) | Regenerated hourly by refresh |
| `loops_closed.json` | `server.ts` close_loop | Not read by any module | Append-only archive of closed loops |
| `cognitive_state.json` | `export_cognitive_state.py` | `server.ts`, `governance_daemon.ts`, CycleBoard (CognitiveController) | Regenerated hourly by refresh |
| `daily_payload.json` | `export_daily_payload.py` | CycleBoard (via brain/ copy) | Regenerated hourly by refresh |
| `governance_state.json` | `governor_daily.py` | `atlas_boot.html` (via unified state) | Regenerated by daily governance |
| `strategic_priorities.json` | `build_strategic_priorities.py` | CycleBoard (StrategicRouter via brain/ copy) | Regenerated by refresh |
| `closures.json` (in .delta-fabric/) | N/A | N/A | NOT USED — closures.json lives in cognitive-sensor workspace, not .delta-fabric/ |

---

## 6. Hidden Logic

### 6.1 Enforcement Level Derivation

Not stored anywhere. Computed on every unified state read:
```javascript
enforcement_level = Math.min(violations_count, 3)
```
Levels: 0=CLEAR, 1=WARN, 2=LOCKED, 3=HARD LOCK.

atlas_boot.html renders: green badge (0), yellow (1), orange (2), red+pulsing (3).

### 6.2 Closure Ratio Normalization

Python stores `closure.ratio` as percentage (e.g., `72.0` meaning 72%). TypeScript expects decimal (e.g., `0.72`). The unified state endpoint normalizes:
```javascript
if (rawRatio > 1) closureRatio = rawRatio / 100;
```
This is a silent conversion that could mask bugs if the raw value happens to be between 1.0 and 1.99.

### 6.3 Streak Sovereignty (Day End)

At 10pm (day_end cron), the daemon checks if any closures happened today. If `last_streak_date !== today` AND `streak_days > 0`:
- Reset `streak_days = 0`
- Update closures.json registry
- Log streak reset

This prevents streak inflation from days with no closures.

### 6.4 Streak Gating (BUILD-Only Increment)

Streak only increments when:
1. This is the first closure of the day (`last_streak_date !== today`)
2. The resulting mode is BUILD or SCALE
3. Triggered by close_loop endpoint

CLOSURE and MAINTENANCE mode closures do NOT increment the streak. This incentivizes sustained building.

### 6.5 Violations Reset on Closure

Every successful close_loop resets `enforcement.violations_count` to 0. This means:
- Closing a loop forgives all accumulated violations
- Enforcement level drops to CLEAR immediately
- This creates a "closure amnesty" mechanic

### 6.6 Build Allowed Default

When `build_allowed` is not explicitly set by Python (today.json) or delta state:
```javascript
build_allowed = !(mode === 'CLOSURE')
```
All modes except CLOSURE allow building by default.

### 6.7 Mode Routing (Unified 2026-03-11)

**Before stabilization**: Six independent routing implementations with different thresholds. **After**: Two authoritative routers (one per language), documented in `contracts/schemas/ModeContract.v1.json`.

| # | Location | Role | Modes |
|---|---|---|---|
| 1 | `routing.ts:route()` | **Single TypeScript authority** | All 6 (RECOVER→SCALE) via Markov LUT |
| 2 | `atlas_config.py:compute_mode()` | **Single Python authority** | 3 (CLOSURE/MAINTENANCE/BUILD) |
| 3 | `cognitive.js` (CycleBoard) | Client-side display only | 3 (reads from payload) |

**Eliminated**: `lut.ts` (deleted), daemon inline thresholds (now calls `routing.ts`), duplicated Python routing in `route_today.py` and `export_daily_payload.py` (now import `compute_mode`).

**Cross-language contract**: Python proposes mode via `/api/ingest/cognitive` with `schema_version` + `mode_source` fields. TypeScript daemon may override via next `mode_recalc` cycle using full 5-signal routing.

### 6.8 Daemon Refresh Spawns Python

The daemon's hourly refresh job runs:
```
child_process.spawn('python', ['refresh.py'], { timeout: 120000 })
```
This is a hidden cross-language orchestration point. **Updated 2026-03-11**: Both sides now have retry logic (2 retries, 3-5s delay). The daemon's `runRefresh()` retries the entire spawn. Python's `refresh.py` retries each individual script and prints a summary (ok/failed/skipped).

### 6.9 Day Start Resets

At 6am (day_start cron):
- `closures_today` → 0 (reset in closures.json)
- `metrics.closures_today` → 0 (reset in system_state)
- Mode recalculated
- Day status set to `active`

### 6.10 Task Updates Skip Delta

`PUT /api/tasks/:id` directly mutates the entity state and saves — it does NOT create a delta. This breaks the event sourcing model for task updates. Task creation (POST) and deletion (DELETE/archive) do create deltas.

### 6.11 CycleBoard Progress Weights

Daily progress is a weighted composite not documented anywhere except helpers.js:
```
Progress = TimeBlocks(30%) + Goals(30%) + Routines(25%) + FocusAreas(15%)
```

### 6.12 CycleBoard AI Context Includes Cognitive State

The `AIContext.getContext()` snapshot includes cognitive fields:
```javascript
cognitive: { mode, risk, openLoops, isClosureMode }
```
This means any LLM using the CycleBoard context can see the behavioral governance state and respond accordingly.

### 6.13 Secondary System State Entity

`.delta-fabric/entities.json` contains TWO system_state entities. The second one (version 1, heartbeat-only) appears to be created by a daemon bug where `updateSystemState()` created a new entity instead of finding the existing one. The unified state reader takes the first match, so the second entity is effectively dead weight.

### 6.14 Closures.json Location

`closures.json` lives in the cognitive-sensor workspace (root of `services/cognitive-sensor/`), NOT in `.delta-fabric/`. The daemon and server both reference it via hardcoded relative paths. This is a hidden file location dependency.

---

## 7. System Architecture Summary

### End-to-End Flow

```
STATIC INPUT                    ANALYSIS                      STATE ENGINE                    UI
─────────────                   ────────                      ────────────                    ──

memory_db.json ──────┐
(1,397 convos)       │
                     ├──→ Python Pipeline ──→ JSON Files ──→ Delta Kernel ──→ atlas_boot.html
results.db ──────────┘    (cognitive-sensor)    │              (port 3001)     (browser, 30s poll)
(384-dim embeddings)       │                   │              │                │
                          10-step refresh      │              │   ┌────────────┘
                          5-agent idea pipe    │              │   │
                          2 governors          │              │   ├── CycleBoard (iframe, localStorage)
                                               │              │   ├── Control Panel (iframe, 5s poll)
                          ↓                    ↓              │   ├── Cognitive Atlas (iframe, static)
                    cognitive_state.json   closures.json      │   └── Docs Viewer (iframe, static)
                    daily_payload.json     loops_latest.json   │
                    governance_state.json  entities.json       ├── Aegis Fabric (port 3002)
                    strategic_priorities   deltas.json         │   └── AI Agent policy gate
                    idea_registry.json                        │
                                                              └── Governance Daemon (6 cron jobs)
                                                                    • heartbeat (5min)
                                                                    • refresh (1hr → spawns Python)
                                                                    • day_start (6am → reset counters)
                                                                    • day_end (10pm → streak sovereignty)
                                                                    • mode_recalc (15min → ratio thresholds)
                                                                    • work_queue (1min → timeout check)
```

### Three Polling Loops

| Client | Endpoint | Interval | Data |
|---|---|---|---|
| atlas_boot.html | GET /api/state/unified + GET /api/daemon/status | 30 seconds | Mode, risk, loops, ratio, enforcement, closures, streak, primary order, daemon state |
| control.html | GET /api/work/status | 5 seconds | Active jobs, queue depth, capacity, mode |
| timeline.html | GET /api/timeline + GET /api/timeline/stats | 10 seconds | Event log, type breakdown, totals |

### State Merging at Unified Endpoint

The GET /api/state/unified endpoint is the system's most critical read path. It merges four data sources with cascading priority:

```
Priority 1: data/projections/today.json (Python → push_to_delta.py)
Priority 2: cognitive_state.json (Python → export_cognitive_state.py)
Priority 3: .delta-fabric/entities.json (TypeScript → delta engine)
Priority 4: Hardcoded defaults (RECOVER mode, MEDIUM risk, 0 loops)
```

Each derived field (mode, risk, open_loops, etc.) is resolved independently through this cascade. The merge also normalizes units (Python percentage → TypeScript decimal for closure_ratio).

### Dual State Paths

The system maintains two parallel state paths that are eventually consistent:

**Path A — Python files**: cognitive_state.json, daily_payload.json, governance_state.json, loops_latest.json, strategic_priorities.json. Updated by Python pipeline (hourly via daemon cron or manual refresh). One-way push to delta-kernel via push_to_delta.py.

**Path B — TypeScript deltas**: .delta-fabric/entities.json, .delta-fabric/deltas.json, closures.json. Updated by server.ts endpoint handlers and daemon cron jobs. Append-only hash chain.

The unified endpoint merges both paths on read. There is no mechanism for the TypeScript side to push state back to Python. The Python side is authoritative for cognitive metrics; the TypeScript side is authoritative for mode transitions, closures, and enforcement.

### CycleBoard is a Parallel Universe

CycleBoard operates entirely in localStorage. It loads cognitive_state.json once on boot (from the `cycleboard/brain/` copy) but never communicates with the delta-kernel API. Its progress tracking (A-Z tasks, day plans, routines, journal) is invisible to the rest of the system. The strategic_priorities.json provides directive alignment but CycleBoard does not report compliance back to the governance engine.

This means the governance system (atlas_boot.html + daemon + Python pipeline) and the productivity system (CycleBoard) are **decoupled by design** — governance observes conversation history, while CycleBoard manages daily execution.

---

*End of Architecture Briefing*
