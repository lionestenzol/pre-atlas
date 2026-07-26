# Pre Atlas Frontend Audit

> Generated from codebase analysis on 2026-04-05
> Covers all 8 frontend applications, 30+ components, state management, and API integrations

---

## 1. Executive Summary

Pre Atlas has 8 distinct frontend surfaces spanning React (Next.js), vanilla HTML/JS, and Plotly/Sigma.js visualizations. They connect to 3 backend services via REST APIs, with localStorage as fallback persistence.

```
FRONTEND SURFACE MAP
+==================================================================+
|                                                                    |
|  +------------------+    +------------------+    +---------------+ |
|  | MOSAIC DASHBOARD |    |    CYCLEBOARD    |    | AEGIS FABRIC  | |
|  | Next.js :3000    |    |  HTML/JS :8889   |    | DASHBOARD     | |
|  | 10 components    |    |  12 screens      |    | :3002/ui      | |
|  +--------+---------+    +--------+---------+    | 8 tabs        | |
|           |                       |               +-------+-------+ |
|           v                       v                       v         |
|  +--------+---------+    +--------+---------+    +-------+-------+ |
|  | Proxy Routes     |    | Direct API calls |    | Direct API    | |
|  | /api/delta/*     |    | :3001/api/*      |    | :3002/api/*   | |
|  | /api/aegis/*     |    +------------------+    +---------------+ |
|  | /api/mirofish/*  |                                              |
|  | /api/mosaic/*    |                                              |
|  +------------------+                                              |
|                                                                    |
|  +------------------+    +------------------+    +---------------+ |
|  | DELTA-KERNEL WEB |    | COGNITIVE SENSOR |    | BLUEPRINT     | |
|  | React SPA        |    | DASHBOARDS (5)   |    | GENERATOR     | |
|  +------------------+    +------------------+    | Next.js       | |
|                                                   +---------------+ |
|  +------------------+    +------------------+                      |
|  | ATLAS BOOT SHELL |    | SYSTEM PAGES (3) |                      |
|  | HTML iframe host |    | Static HTML      |                      |
|  +------------------+    +------------------+                      |
+==================================================================+
```

---

## 2. Component Catalog

---

### 2.1 MOSAIC DASHBOARD (Next.js :3000)

```
Location:   services/mosaic-dashboard/
Framework:  Next.js 16 + TypeScript + Tailwind CSS
Port:       3000
Theme:      Dark (zinc-900 bg, zinc-800 borders)
API Layer:  Proxy routes forwarding to backend services
```

#### Component Tree

```
services/mosaic-dashboard/src/
+-- app/
|   +-- page.tsx ..................... Main page (5-panel grid)
|   +-- layout.tsx ................... Root layout
|   +-- api/
|       +-- delta/[...path]/route.ts . Proxy -> :3001
|       +-- aegis/[...path]/route.ts . Proxy -> :3002
|       +-- mirofish/[...path]/route.ts Proxy -> :3003
|       +-- mosaic/[...path]/route.ts  Proxy -> :3005
+-- components/
|   +-- CockpitPanel.tsx ............. Mode + risk + approvals + directive
|   +-- UsageCounter.tsx ............. AI usage meter + pause toggle
|   +-- FestivalPanel.tsx ............ Festival progress + execution
|   +-- SimulationPanel.tsx .......... MiroFish sim form + D3 chart
|   +-- AtlasClusters.tsx ............ Idea scatter plot (Plotly)
|   +-- ModePanel.tsx ................ Mode display + 6-stat grid
|   +-- ModeTag.tsx .................. Color-coded mode badge
|   +-- Panel.tsx .................... Reusable card wrapper
|   +-- ApprovalPanel.tsx ............ Approval actions panel
+-- lib/
    +-- api.ts ....................... Typed API client (all endpoints)
    +-- types.ts ..................... Shared type definitions
```

#### Panel Layout (page.tsx)

```
+==================================================================+
|                     MOSAIC DASHBOARD (:3000)                       |
+==================================================================+
|                                                                    |
| +--------------------------------------------------------------+ |
| |                     COCKPIT PANEL                              | |
| | [BUILD] Risk: LOW   Build: OK   Loops: 3   Closure: 78%      | |
| |                                                                | |
| | Pending Approvals:     | Today's Directive:                   | |
| | [Approve] [Reject]     | "Close 2 loops before BUILD work"    | |
| |                        | Top Moves: 1. ... 2. ... 3. ...      | |
| +--------------------------------------------------------------+ |
|                                                                    |
| +---------------------------+ +---------------------------+       |
| |     USAGE COUNTER         | |     FESTIVAL PANEL        |       |
| | |||||||||||||||........... | | Phase 2/4: EXECUTE        |       |
| | 342s / 600s    [Pause]    | | ||||||||......  67%        |       |
| +---------------------------+ | [Execute Next]             |       |
|                               +---------------------------+       |
|                                                                    |
| +---------------------------+ +---------------------------+       |
| |    SIMULATION PANEL       | |    ATLAS CLUSTERS         |       |
| | Topic: [__________]       | |                           |       |
| | Agents: [===5===]         | |    o  O    .              |       |
| | Ticks: [===50==]          | |  .    o  O                |       |
| | [Run Simulation]          | |    .       o              |       |
| |                           | | Priority ^                |       |
| | [D3 consensus chart]      | |          Alignment ->     |       |
| +---------------------------+ +---------------------------+       |
+==================================================================+
```

#### Component: CockpitPanel

```
File:     src/components/CockpitPanel.tsx
Renders:  Mode tag, risk badge, build status, loop count,
          closure ratio, stale indicator, pending approvals,
          directive text, top moves list, active lanes
API:      GET /api/delta/daily-brief        (30s polling)
          GET /api/aegis/v1/approvals       (30s polling)
          POST /api/aegis/v1/approvals/:id  (approve/reject)
State:    brief (DailyBrief), approvals[], loading, error, acting
Colors:   RED=#ff6b6b (danger), AMBER=#fbbf24 (warning), GREEN=#7dff9b (ok)
```

#### Component: UsageCounter

```
File:     src/components/UsageCounter.tsx
Renders:  Usage metric "{used}s / {total}s", progress bar, pause/resume button
API:      GET  /api/mosaic/v1/metering/usage
          POST /api/mosaic/v1/metering/pause
State:    data (UsageData), loading, error, toggling
```

#### Component: FestivalPanel

```
File:     src/components/FestivalPanel.tsx
Renders:  Mode tag, risk badge, phase progress bars, execute button
API:      GET  /api/mosaic/v1/status
          POST /api/mosaic/v1/tasks/execute
State:    data (OrchestratorStatus), loading, error, executing, execResult
```

#### Component: SimulationPanel

```
File:     src/components/SimulationPanel.tsx
Renders:  2-column form+results, text inputs, sliders, D3 line chart, report
API:      POST /api/mirofish/v1/simulations           (start sim)
          GET  /api/mirofish/v1/simulations            (list sims)
          GET  /api/mirofish/v1/simulations/:id        (poll every 2s)
          GET  /api/mirofish/v1/simulations/:id/report (get report)
State:    sims[], ticks[], topic, docText, agentCount, tickCount,
          activeId, simStatus, report, loading, error, submitting
```

#### Component: AtlasClusters

```
File:     src/components/AtlasClusters.tsx
Renders:  Plotly scatter plot (alignment vs priority, bubble=mentions)
API:      GET /api/delta/ideas
State:    ideas (PlotIdea[]), loading, error
Colors:   execute_now=#22c55e, next_up=#3b82f6, backlog=#6b7280, archive=#6b7280
```

#### Component: ModeTag

```
File:     src/components/ModeTag.tsx
Renders:  Inline badge with mode-specific background color
Props:    mode (Mode), large? (boolean)
Colors:   RECOVER=red, CLOSURE=amber, MAINTENANCE=blue,
          BUILD=green, COMPOUND=purple, SCALE=cyan
Used By:  CockpitPanel, FestivalPanel, ModePanel
```

#### Component: Panel (Wrapper)

```
File:     src/components/Panel.tsx
Renders:  Card container with title, loading skeleton, error state, retry
Props:    title, children, loading?, error?, onRetry?
CSS:      bg-zinc-900 border-zinc-800 rounded-xl p-6
Used By:  All 5 main panels
```

#### Proxy Routes

```
/api/delta/[...path]    --> http://localhost:3001  (Delta-Kernel)
/api/aegis/[...path]    --> http://localhost:3002  (Aegis-Fabric)
/api/mirofish/[...path] --> http://localhost:3003  (MiroFish)
/api/mosaic/[...path]   --> http://localhost:3005  (Mosaic-Orchestrator)

Methods: GET, POST, PUT, DELETE, PATCH all forwarded
Headers: Passthrough (including X-API-Key for Aegis)
```

---

### 2.2 CYCLEBOARD (HTML/JS Application)

```
Location:   services/cognitive-sensor/cycleboard/
Technology: Vanilla HTML + JavaScript (no framework)
Port:       8889 (via Live Server or similar)
Theme:      Dark (customizable via state)
API:        Direct calls to delta-kernel :3001
```

#### File Structure

```
services/cognitive-sensor/cycleboard/
+-- index.html ..................... Main HTML shell
+-- css/
|   +-- styles.css ................. Base styles + responsive
+-- js/
|   +-- state.js ................... CycleBoardState (persistence + undo/redo)
|   +-- screens.js ................. 12 screen renderers
|   +-- functions.js ............... Business logic helpers
|   +-- cognitive.js ............... Cognitive integration + data loading
|   +-- strategic.js ............... Strategic routing logic
|   +-- command.js ................. Command palette (Ctrl+K)
|   +-- app.js ..................... Initialization + orchestration
+-- brain/
    +-- cognitive_state.json ....... Current cognitive metrics
    +-- daily_payload.json ......... Daily action payload
    +-- daily_directive.txt ........ Today's directive
    +-- governance_state.json ...... Governance decisions
    +-- governor_headline.json ..... Governance summary
    +-- idea_registry.json ......... Top ideas
    +-- prediction_results.json .... ML predictions
    +-- strategic_priorities.json .. Priority ranking
```

#### Screen Navigation Map

```
+==================================================================+
|                    CYCLEBOARD SCREEN MAP                           |
+==================================================================+
|                                                                    |
|                      +----------+                                  |
|                      |  HOME    |  (Welcome + quick stats)         |
|                      +----+-----+                                  |
|                           |                                        |
|         +---------+-------+-------+---------+                      |
|         |         |               |         |                      |
|    +----+---+ +---+----+   +-----+---+ +---+------+              |
|    | DAILY  | |CALENDAR|   |  A-Z    | | JOURNAL  |              |
|    | Planner| |  View  |   | Goals   | | Entries  |              |
|    +--------+ +--------+   +---------+ +----------+              |
|                                                                    |
|    +----------+ +----------+ +----------+ +----------+            |
|    | WEEKLY   | |REFLECTIONS| | TIMELINE | | ROUTINES |            |
|    | Focus    | |  Prompts  | |  Events  | |  Builder |            |
|    +----------+ +----------+ +----------+ +----------+            |
|                                                                    |
|    +----------+ +----------+                                       |
|    |STATISTICS| | SETTINGS |                                       |
|    |  Charts  | |  Config  |                                       |
|    +----------+ +----------+                                       |
|                                                                    |
|    +--------------------------------------+                        |
|    | COMMAND PALETTE (Ctrl+K)             |                        |
|    | > navigate, search, quick actions    |                        |
|    +--------------------------------------+                        |
+==================================================================+
```

#### State Manager (state.js)

```
CycleBoardState
  |
  +-- version: '2.0'
  +-- screen: 'Home' | 'Daily' | 'AtoZ' | 'Calendar' | ...
  +-- AZTask[]: Monthly A-Z goals
  +-- DayPlans{}: Date-keyed daily plans
  +-- FocusArea[6]: Production, Image, Growth, Personal, Errands, Network
  +-- Routine{}: Morning, Commute, Evening routines
  +-- DayTypeTemplates: Time-blocked A/B/C schedules
  +-- Settings{}: darkMode, notifications, autoSave, defaultDayType
  +-- History{}: completion tracking, productivity scores, streaks
  +-- Journal[]: Journal entries
  +-- EightSteps{}: 8 Steps to Success per day
  +-- Contingencies{}: runningLate, lowEnergy, freeTime, disruption
  +-- Reflections{}: weekly, monthly, quarterly, yearly

  Persistence: localStorage + API sync (2s debounce)
  Undo/Redo:   Max 50 history items
  API Sync:    http://localhost:3001/api/cycleboard
```

#### API Calls (from app.js + cognitive.js)

```
CycleBoard --> Delta-Kernel (:3001)
  GET  /api/state/unified ........... Unified state (mode, risk, loops)
  GET  /api/cycleboard .............. CycleBoard persisted state
  POST /api/cycleboard .............. Save CycleBoard state
  GET  /api/ideas ................... Idea registry
  GET  /api/governance/config ....... Governance config
  GET  /api/preparation ............. Task preparation
  GET  /api/notifications ........... Recent events
  GET  /api/auth/token .............. Auth token
  POST /api/tasks ................... Create task
  PUT  /api/tasks/:id ............... Update task
  POST /api/law/close_loop .......... Close a loop

Fallback: brain/*.json files (local read when API unavailable)
```

#### CycleBoard Layout (index.html)

```
+==================================================================+
|  [=] Cognitive Directive: BUILD | LOW risk | 3 loops | "Ship v2"  |
+==================================================================+
| SIDEBAR (240px)  |  MAIN CONTENT (flex-grow)                      |
| +-------------+  |  +------------------------------------------+ |
| | Welcome     |  |  |                                          | |
| | Name        |  |  |    [Current Screen Content]              | |
| |-------------|  |  |                                          | |
| | > Home      |  |  |    Rendered by screens.js                | |
| |   Daily     |  |  |    Based on state.screen                 | |
| |   Calendar  |  |  |                                          | |
| |   A-Z       |  |  |                                          | |
| |   Weekly    |  |  |                                          | |
| |   Reflect   |  |  |                                          | |
| |   Timeline  |  |  |                                          | |
| |   Routines  |  |  |                                          | |
| |   Journal   |  |  |                                          | |
| |   Stats     |  |  |                                          | |
| |   Settings  |  |  |                                          | |
| |-------------|  |  |                                          | |
| | Progress:   |  |  |                                          | |
| | |||||| 67%  |  |  +------------------------------------------+ |
| |-------------|  |                                                |
| | [Docs]      |  |                                                |
| | [Atlas]     |  |                                                |
| +-------------+  |                                                |
+==================================================================+
| MOBILE BOTTOM NAV: [Home] [Daily] [A-Z] [More]                   |
+==================================================================+
```

---

### 2.3 AEGIS-FABRIC DASHBOARD

```
Location:   services/aegis-fabric/src/ui/dashboard.html
Technology: Vanilla HTML + JavaScript + Tailwind CSS + Font Awesome
Port:       3002 (served at /ui path)
Theme:      Dark
Auth:       Admin key + Tenant key (session-based)
```

#### Tab Structure

```
+==================================================================+
|  AEGIS FABRIC DASHBOARD                                           |
|  [Health: OK]  [Uptime: 4h 23m]  [Auth: Connected]              |
+==================================================================+
| AUTH PANEL (shown when not connected)                             |
| +--------------------------------------------------------------+ |
| | Admin Key: [______________]                                    | |
| | Tenant Key: [______________]                                   | |
| | [Connect]  [Health Only]  [Create Tenant]                      | |
| +--------------------------------------------------------------+ |
+==================================================================+
| TABS (shown when connected):                                      |
| [Overview] [Agents] [Policies] [Approvals]                       |
| [State] [Metrics] [Calendar] [Delta Log]                         |
+------------------------------------------------------------------+

TAB: OVERVIEW
+------+------+------+------+
|Health|Tenant|Agents|Today |
| OK   |Demo  | 3    | 12   |
+------+------+------+------+
| Quotas: 1000 actions/day  |
| Recent Activity log       |
+---------------------------+

TAB: AGENTS
+------------------------------------------+
| Agent Name | Provider | Status | Actions  |
+------------------------------------------+
| planner    | claude   | active | 45       |
| reviewer   | claude   | active | 23       |
+------------------------------------------+
| [Register New Agent Form]                |
+------------------------------------------+

TAB: POLICIES
+------------------------------------------+
| Policy Name | Rules | Target | Active     |
+------------------------------------------+
| cost-limit  | 2     | *      | Yes        |
| require-appr| 1     | planner| Yes        |
+------------------------------------------+
| [Add Rule Form]  [Policy Simulator]      |
+------------------------------------------+

TAB: APPROVALS
+------------------------------------------+
| Action     | Agent  | Status  | Actions   |
+------------------------------------------+
| mode_change| planner| pending | [OK] [No] |
+------------------------------------------+

TAB: STATE EXPLORER
+------------------------------------------+
| Entity Type: [v agents]                   |
| Entity List: [agent-001] [agent-002]      |
| Detail: { JSON viewer }                   |
+------------------------------------------+

TAB: METRICS
+------------------------------------------+
| Agent: planner  | Actions: 45 | Cost: $2  |
| Agent: reviewer | Actions: 23 | Cost: $1  |
+------------------------------------------+
| Raw Prometheus metrics display            |
+------------------------------------------+

TAB: CALENDAR
+------------------------------------------+
|     March 2026                            |
| Mo Tu We Th Fr Sa Su                      |
|                    1                       |
|  2  3  4  5  6  7  8                      |
|  9 10 11 12 13 14 15                      |
| ...                                       |
+------------------------------------------+
| Filters: [x]Tasks [x]Approvals [x]Events |
| Day Detail: ...                           |
| Upcoming 7 days: ...                      |
+------------------------------------------+

TAB: DELTA LOG
+------------------------------------------+
| Hash Chain Viewer                         |
| Entity Filter: [__________]              |
| Delta Detail: { JSON }                    |
| [Verify Chain]                            |
+------------------------------------------+
```

#### API Calls

```
Aegis Dashboard --> Aegis-Fabric (:3002)
  POST (connect)    Auth with admin_key + tenant_key
  GET  /health      Health status
  GET  /api/v1/tenants          Tenant info
  GET  /api/v1/agents           Agent list
  POST /api/v1/agents           Register agent
  GET  /api/v1/policies         Policy list
  POST /api/v1/policies         Create policy
  POST /api/v1/policy/:id/decision  Simulate policy
  GET  /api/v1/approvals        Pending approvals
  POST /api/v1/approval/:id/approve|deny  Decision
  GET  /api/v1/state/:entity_id Entity state
  GET  /api/v1/metrics          Usage metrics
  GET  /api/v1/deltas/:entity_id Delta history

State: sessionStorage (adminKey, tenantKey, connected, tenant)
Refresh: 10s auto-refresh on active tabs
```

---

### 2.4 DELTA-KERNEL WEB (React SPA)

```
Location:   services/delta-kernel/web/src/App.tsx
Technology: React + TypeScript + CSS Modules
API:        Direct calls to :3001
Fallback:   localStorage when API unavailable
```

#### Component Layout

```
+==================================================================+
|  DELTA-KERNEL WEB                          [o Synced / o Local]   |
+==================================================================+
|                                                                    |
|  MODE: BUILD                                                       |
|  "Focus on shipping. Deep work blocks. No new loops."             |
|                                                                    |
|  SIGNALS                                                           |
|  +----------+  +----------+  +----------+  +----------+          |
|  | Sleep    |  | Open     |  | Leverage |  | Streak   |          |
|  |  7.5h    |  | Loops: 3 |  | +2       |  | 5 days   |          |
|  +----------+  +----------+  +----------+  +----------+          |
|                                                                    |
|  [Slept Well (8h)]  [Slept Poorly (4h)]  [Big Win!]              |
|                                                                    |
|  TASKS (3 open)                              [+ New Task]          |
|  +--------------------------------------------------------------+ |
|  | [ ] Fix login bug                    OPEN    [Start] [Delete] | |
|  | [~] Deploy v2.1                      IN_PROGRESS     [Done]   | |
|  | [ ] Write tests                      OPEN    [Start] [Delete] | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  Status: "Task created successfully"                               |
+==================================================================+
```

#### API Calls

```
Delta-Kernel Web --> Delta-Kernel (:3001)
  GET    /api/state ............. Load system state
  PUT    /api/state ............. Save state changes
  GET    /api/tasks ............. Load task list
  POST   /api/tasks ............. Create task
  PUT    /api/tasks/:id ......... Update task status
  DELETE /api/tasks/:id ......... Delete task

Fallback: localStorage (state + tasks) when API unreachable
```

#### Mode Transition Logic (Client-Side)

```
IF sleepHours < 5           --> RECOVER
IF sleepHours < 7
   AND mode in [BUILD, COMPOUND, SCALE]
                             --> CLOSURE
IF sleepHours >= 7
   AND mode === CLOSURE
   AND openLoops <= 3       --> BUILD
IF openLoops > 7            --> CLOSURE
IF leverageBalance >= 5
   AND mode === BUILD        --> COMPOUND
IF leverageBalance >= 10
   AND streakDays >= 3
   AND mode === COMPOUND     --> SCALE
```

---

### 2.5 COGNITIVE SENSOR DASHBOARDS

#### 2.5.1 Dashboard (dashboard.html)

```
Location:  services/cognitive-sensor/dashboard.html
Type:      Static HTML (generated by Python scripts)
Purpose:   System state snapshot + analytics
```

```
+==================================================================+
| COGNITIVE SENSOR DASHBOARD                                        |
+==================================================================+
| Latest State Snapshot                                              |
|   Mode: BUILD | Risk: LOW | Loops: 3 | Ratio: 78%               |
+------------------------------------------------------------------+
| Top 10 Open Loops                                                  |
| +----+------------------------+----------+-------+               |
| | #  | Loop Title             | Created  | Stale |               |
| +----+------------------------+----------+-------+               |
| | 1  | Deploy monitoring      | 2026-03  | No    |               |
| | 2  | Review auth changes    | 2026-03  | Yes   |               |
| | ...                                                             |
| +----+------------------------+----------+-------+               |
+------------------------------------------------------------------+
| Completion Analytics                                               |
|   Total Closed: 145 | This Week: 7 | Avg/Week: 4.2              |
+------------------------------------------------------------------+
| Lifetime Anchors (Top 15 Topics)                                   |
| +----+-------------------+--------+                               |
| | #  | Topic             | Count  |                               |
| +----+-------------------+--------+                               |
| | 1  | System design     | 34     |                               |
| | ...                                                             |
+==================================================================+
No interactive elements. Static output.
```

#### 2.5.2 Control Panel (control_panel.html)

```
Location:  services/cognitive-sensor/control_panel.html
Type:      Interactive HTML (Tailwind CSS)
Purpose:   Quick system control interface
```

```
+==================================================================+
| COGNITIVE CONTROL PANEL                                           |
+==================================================================+
| SYSTEM STATUS                                                      |
| +-------------+ +-------------+ +-------------+ +-------------+  |
| | Mode        | | Risk Level  | | Open Loops  | | Closure     |  |
| | [BUILD]     | | [LOW]       | | [3]         | | [78%]       |  |
| +-------------+ +-------------+ +-------------+ +-------------+  |
+------------------------------------------------------------------+
| REQUIRED ACTION                                                    |
| +--------------------------------------------------------------+ |
| |  !  "Close 2 open loops before starting new BUILD work"      | |
| |                                                                | |
| |                    [I'll Do This Now]                           | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
| OPEN LOOPS                                                         |
| +--------------------------------------------------------------+ |
| | [ ] Deploy monitoring                              [Close]    | |
| | [ ] Review auth changes                            [Close]    | |
| | [ ] Update API docs                                [Close]    | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
| QUICK ACTIONS                                                      |
| [Refresh System] [View Dashboard] [Close Loop] [Open CycleBoard] |
+==================================================================+

Data source: /data/cognitive_state.json, /data/daily_payload.json
Mode calc:   closure_ratio < 15 -> CLOSURE
             open_loops > 10    -> MAINTENANCE
             else               -> BUILD
```

#### 2.5.3 Atlas Template (atlas_template.html)

```
Location:  services/cognitive-sensor/atlas_template.html
Type:      Advanced visualization (Plotly + Sigma.js)
Purpose:   Cognitive atlas with multi-layer analysis
```

```
+==================================================================+
| [<- CycleBoard]  COGNITIVE ATLAS  "Behavioral Pattern Map"       |
+==================================================================+
| Stats: | Clusters: 8 | Nodes: 142 | Edges: 367 | Coverage: 94% ||
+------------------------------------------------------------------+
| Mode: [Analytics] [Graph]                                         |
| Layer: [Cluster][Role][Time][Conversation][Leverage][Prediction]  |
+------------------------------------------------------------------+
| MAIN AREA (flex-grow)         | SIDEBAR (420px, collapsible)     |
| +---------------------------+ | +------------------------------+ |
| |                           | | | Prediction Engine            | |
| |  [Plotly scatter chart]   | | | > Next mode: BUILD (82%)     | |
| |  OR                       | | | > Exit path: close 2 loops   | |
| |  [Sigma.js force graph]   | | +------------------------------+ |
| |                           | | | Leverage Ranking             | |
| |  Layers toggle between:   | | | 1. System design  |||||| 34  | |
| |  - Cluster view           | | | 2. API work       ||||   28  | |
| |  - Role distribution      | | | 3. Auth           |||    22  | |
| |  - Time heatmap           | | +------------------------------+ |
| |  - Conversation map       | | | Cluster Inspector            | |
| |  - Leverage scores        | | | > Selected: "Infrastructure" | |
| |  - Prediction overlay     | | | > Nodes: 18 | Density: 0.7   | |
| |                           | | +------------------------------+ |
| +---------------------------+ | | Cluster Summary (table)       | |
|                               | +------------------------------+ |
|                               | | Role Distribution             | |
|                               | +------------------------------+ |
+------------------------------------------------------------------+

Libraries: Plotly.js, Graphology, Sigma.js
Data: __DATA_PAYLOAD__ global (server-preprocessed)
No API calls (all data baked in at render time)
```

#### 2.5.4 Idea Dashboard (idea_dashboard.html)

```
Location:  services/cognitive-sensor/idea_dashboard.html
Type:      Interactive HTML
Purpose:   Browse and manage excavated ideas
```

```
+==================================================================+
| IDEA DASHBOARD                    [Search: ___________] [Sync]    |
+==================================================================+
| Stats: Total: 47 | Execute: 5 | Next: 12 | Backlog: 25 | Arch: 5|
+------------------------------------------------------------------+
| Tabs: [Overview] [Execute Now] [Next Up] [Vision Clusters]       |
|       [Timelines] [All Ideas] [Backlog]                          |
+------------------------------------------------------------------+
| IDEA CARDS                                                         |
| +---------------------------+ +---------------------------+       |
| | "Personal CRM"           | | "Auto-brief generator"    |       |
| | Tier: EXECUTE_NOW        | | Tier: NEXT_UP             |       |
| | Priority: 0.91           | | Priority: 0.78            |       |
| | Alignment: 0.85          | | Alignment: 0.72           |       |
| | Mentions: 7              | | Mentions: 4               |       |
| | [Details] [Add to A-Z]   | | [Details] [Add to A-Z]    |       |
| +---------------------------+ +---------------------------+       |
+==================================================================+

Data: /api/idea_registry.json or /data/idea_registry.json
Search: Client-side filtering by title/description
Detail: Modal overlay with full idea view
Integration: addToAZ() writes to localStorage for CycleBoard
```

#### 2.5.5 Docs Viewer (docs_viewer.html)

```
Location:  services/cognitive-sensor/docs_viewer.html
Type:      3-column document browser
Purpose:   Browse project documentation
```

```
+==================================================================+
| DOCS VIEWER                              [Search: ___________]    |
+==================================================================+
| SIDEBAR (250px)  | CONTENT (flex-grow)                            |
| +-------------+  | +------------------------------------------+  |
| | > services/ |  | |                                          |  |
| |   > delta/  |  | |  # Rendered Markdown                     |  |
| |     types.ts|  | |                                          |  |
| |     server..|  | |  Content displayed via Marked.js         |  |
| |   > cogn../ |  | |  Code blocks via Highlight.js            |  |
| |   > miro../ |  | |                                          |  |
| | > contracts |  | |                                          |  |
| | > scripts   |  | |                                          |  |
| +-------------+  | +------------------------------------------+  |
+==================================================================+

Libraries: Marked.js (markdown), Highlight.js (syntax)
Data: Local markdown files + JSON directory structure
```

---

### 2.6 DELTA-KERNEL CONTROL PANELS

#### 2.6.1 Work Queue Control (control.html)

```
Location:  services/delta-kernel/src/ui/control.html
Type:      Auto-refreshing dashboard (5s interval)
API:       GET /api/work/status, GET /api/work/history
```

```
+==================================================================+
| WORK QUEUE CONTROL                                                |
+==================================================================+
| SYSTEM STATE                                                       |
| Mode: BUILD | Build: OK | Ratio: 78% | Active: 1 | Queue: 2     |
+------------------------------------------------------------------+
| ACTIVE JOB                                                         |
| Job: work-001 | Type: ai | Title: "Generate brief"               |
| Time remaining: 4m 23s                                             |
+------------------------------------------------------------------+
| JOB QUEUE (2 items)                                                |
| #1: work-002 | human | "Review deployment plan"                  |
| #2: work-003 | system | "Run predictions"                        |
+------------------------------------------------------------------+
| RECENT COMPLETIONS                                                 |
| work-000 | completed | 2m 15s | "Morning refresh"                |
| work-099 | failed    | 10m 0s | "Weekly analysis" (timeout)      |
+==================================================================+

Colors: good=#7dff9b, bad=#ff6b6b
Auto-refresh: 5 seconds
```

#### 2.6.2 Timeline (timeline.html)

```
Location:  services/delta-kernel/src/ui/timeline.html
Type:      Filterable event timeline (10s refresh)
API:       GET /api/timeline, GET /api/timeline/stats
```

```
+==================================================================+
| TIMELINE                                                          |
+==================================================================+
| Controls: Type [All v]  Limit [50 v]  [Refresh]                  |
+------------------------------------------------------------------+
| Stats: Events: 234 | Approved: 45 | Denied: 3 | Mode Changes: 7 |
+------------------------------------------------------------------+
| TIMELINE VIEW                                                      |
|                                                                    |
| 10:23 AM  o--  WORK_COMPLETED  "Morning refresh" (2m 15s)        |
|           |                                                        |
| 10:20 AM  o--  WORK_REQUESTED  "Morning refresh" (priority: HIGH)|
|           |                                                        |
| 09:15 AM  o--  MODE_CHANGED    CLOSURE -> BUILD                   |
|           |                                                        |
| 09:00 AM  o--  LOOP_CLOSED     "Review auth changes"              |
|           |                                                        |
| 06:00 AM  o--  SYSTEM_START    Day start sequence                  |
|                                                                    |
+==================================================================+

Event type colors:
  WORK_REQUESTED  = blue
  WORK_APPROVED   = green
  WORK_DENIED     = red
  WORK_COMPLETED  = green
  WORK_FAILED     = red
  WORK_TIMEOUT    = orange
  MODE_CHANGED    = purple
  LOOP_CLOSED     = cyan
  SYSTEM_START    = gray
```

---

### 2.7 TOP-LEVEL PAGES

#### 2.7.1 Atlas Boot Shell (atlas_boot.html)

```
Location:  atlas_boot.html (repo root)
Type:      Application shell with iframe embedding
Purpose:   Main entry point that hosts all other UIs
```

```
+==================================================================+
|  ATLAS CORE                                                        |
|  Directive: [BUILD] Risk: LOW  Loops: 3  Ratio: 78%              |
|  Primary Order: "Close 2 loops, then ship feature v2"            |
+==================================================================+
| TABS: [CycleBoard] [Cognitive Atlas] [System Map] [...]          |
+------------------------------------------------------------------+
| TAB CONTENT (iframe, flex-grow)  | DASHBOARD PANEL (400px)       |
| +------------------------------+ | +---------------------------+ |
| |                              | | |                           | |
| |  [Embedded page via iframe]  | | | [Mosaic Dashboard iframe] | |
| |                              | | | or other dashboard        | |
| |  Current tab content:       | | |                           | |
| |  - CycleBoard (:8889)      | | |                           | |
| |  - Atlas template          | | |                           | |
| |  - System map              | | |                           | |
| |                              | | |                           | |
| +------------------------------+ | +---------------------------+ |
+------------------------------------------------------------------+
| [Collapse Panel >>]                                               |
+==================================================================+

Features: Tab switching, panel collapse/expand, exponential backoff polling
API: GET :3001/api/state/unified (backoff: 10s -> 120s, visibility pause)
```

#### 2.7.2 System Map (system-map.html)

```
Location:  system-map.html (repo root)
Type:      Static informational page
Purpose:   Visual architecture overview
```

```
+==================================================================+
|           PRE ATLAS SYSTEM MAP                                     |
|  "How the system works, at a glance"                              |
+==================================================================+
| BIG PICTURE FLOW                                                   |
|                                                                    |
|  [Conversations] --> [Cognitive Sensor] --> [Mode Routing]        |
|                                               |                    |
|                                    +----------+----------+        |
|                                    |          |          |        |
|                                 [BUILD]  [CLOSURE] [MAINT.]      |
|                                    |          |          |        |
|                                    +----------+----------+        |
|                                               |                    |
|                                    [Work Queue] --> [Output]      |
+------------------------------------------------------------------+
| MODE STRIP                                                         |
| +--------+ +--------+ +--------+ +--------+ +--------+ +--------+|
| |RECOVER | |CLOSURE | | MAINT. | | BUILD  | |COMPOUND| | SCALE  ||
| |  Rest  | | Close  | |  Fix   | |  Ship  | | Grow   | | Expand ||
| +--------+ +--------+ +--------+ +--------+ +--------+ +--------+|
+==================================================================+
Static page. No API calls. Educational reference.
```

#### 2.7.3 System Tour (system-tour.html)

```
Location:  system-tour.html (repo root)
Type:      Interactive guided tour (10 tabs)
Purpose:   Deep-dive explanation of each system layer
Tabs:      Home | Big Picture | 6 Modes | The Brain | The Spine |
           The Gate | The Tools | Data Flow | 5 Projects | Why
```

#### 2.7.4 Pattern Map (pre-atlas-pattern-map.html)

```
Location:  pre-atlas-pattern-map.html (repo root)
Type:      Expandable pattern reference (14+ patterns)
Purpose:   Document behavioral patterns detected in conversations
Features:  Collapsible cards, sticky nav, color-coded sections
```

---

### 2.8 BLUEPRINT GENERATOR (Next.js App)

```
Location:   apps/blueprint-generator/
Technology: Next.js + TypeScript + CSS Modules
Theme:      Dark
Purpose:    Deterministic blueprint generation from idea input
```

#### Component Layout

```
+==================================================================+
| BLUEPRINT GENERATOR                                                |
+==================================================================+
| INPUT VIEW                           | OUTPUT VIEW                |
| +----------------------------------+ | +------------------------+ |
| | What are you building?           | | | OBJECTIVE              | |
| | [_____________________________]  | | | Build X that lets...   | |
| |                                  | | +------------------------+ |
| | Who is it for?                   | | | TARGET USER            | |
| | [_____________________________]  | | | People who can't...    | |
| |                                  | | +------------------------+ |
| | What will they do with it?       | | | CORE FUNCTION          | |
| | [_____________________________]  | | | Let user do X via Y    | |
| |                                  | | +------------------------+ |
| | [Generate Blueprint]             | | | CONSTRAINTS (V1 Only)  | |
| |                                  | | | - No auth              | |
| | Error: "Too vague..."           | | | - No backend           | |
| +----------------------------------+ | | - Web only             | |
|                                      | +------------------------+ |
|                                      | | MVP FEATURES (5)       | |
|                                      | | 1. Core interface      | |
|                                      | | 2. Validation          | |
|                                      | | 3. localStorage        | |
|                                      | | 4. Responsive          | |
|                                      | | 5. Error/empty states  | |
|                                      | +------------------------+ |
|                                      | | BUILD STEPS (7)        | |
|                                      | | 1. Data model          | |
|                                      | | 2. Interface           | |
|                                      | | ...                    | |
|                                      | +------------------------+ |
|                                      | | [Copy] [Start Over]    | |
|                                      | +------------------------+ |
|                                      | | ADD FEATURE            | |
|                                      | | [____________] [Add]   | |
|                                      | | "Classified: MVP"      | |
|                                      | +------------------------+ |
+==================================================================+

Files:
  app/page.tsx ................. Main component (input/output views)
  app/layout.tsx ............... Root layout
  lib/generateBlueprint.ts ..... Blueprint generation logic
  lib/scopeLock.ts ............. Feature classification (MVP vs V2)
  lib/types.ts ................. Type definitions

No API calls. All generation is client-side.
Persistence: localStorage via loadState()/saveState()
Validation: Vague word detection, minimum 2+ words
```

---

## 3. Cross-Component Connections

### 3.1 API Call Map (Frontend -> Backend)

```
+=======================================================================+
|              FRONTEND-TO-BACKEND API CALL MAP                         |
+=======================================================================+

MOSAIC DASHBOARD (:3000) -----> DELTA-KERNEL (:3001)
  CockpitPanel          GET  /api/delta/daily-brief       (30s poll)
  AtlasClusters         GET  /api/delta/ideas
  ModePanel             GET  /api/delta/state/unified      (30s poll)

MOSAIC DASHBOARD (:3000) -----> AEGIS-FABRIC (:3002)
  CockpitPanel          GET  /api/aegis/v1/approvals       (30s poll)
  CockpitPanel          POST /api/aegis/v1/approvals/:id

MOSAIC DASHBOARD (:3000) -----> MIROFISH (:3003)
  SimulationPanel       POST /api/mirofish/v1/simulations
  SimulationPanel       GET  /api/mirofish/v1/simulations
  SimulationPanel       GET  /api/mirofish/v1/simulations/:id  (2s poll)
  SimulationPanel       GET  /api/mirofish/v1/simulations/:id/report

MOSAIC DASHBOARD (:3000) -----> MOSAIC-ORCHESTRATOR (:3005)
  UsageCounter          GET  /api/mosaic/v1/metering/usage
  UsageCounter          POST /api/mosaic/v1/metering/pause
  FestivalPanel         GET  /api/mosaic/v1/status
  FestivalPanel         POST /api/mosaic/v1/tasks/execute

CYCLEBOARD (:8889) -----------> DELTA-KERNEL (:3001)
  app.js                GET  /api/state/unified
  app.js                GET  /api/ideas
  app.js                GET  /api/governance/config
  state.js              GET  /api/cycleboard
  state.js              POST /api/cycleboard
  cognitive.js          GET  /api/preparation
  cognitive.js          GET  /api/notifications
  cognitive.js          POST /api/tasks
  cognitive.js          PUT  /api/tasks/:id
  cognitive.js          POST /api/law/close_loop

DELTA-KERNEL WEB ------------> DELTA-KERNEL (:3001)
  App.tsx               GET  /api/state
  App.tsx               PUT  /api/state
  App.tsx               GET  /api/tasks
  App.tsx               POST /api/tasks
  App.tsx               PUT  /api/tasks/:id
  App.tsx               DELETE /api/tasks/:id

AEGIS DASHBOARD -------------> AEGIS-FABRIC (:3002)
  dashboard.html        All /api/v1/* endpoints (agents, policies, etc.)

ATLAS BOOT ------------------> DELTA-KERNEL (:3001)
  atlas_boot.html       GET  /api/state/unified (exponential backoff)
```

### 3.2 State Synchronization Diagram

```
+=======================================================================+
|                   STATE SYNC ARCHITECTURE                             |
+=======================================================================+

                    +-----------------+
                    | DELTA-KERNEL    |
                    | :3001           |
                    | (Source of      |
                    |  Truth)         |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
    +---------+--+  +--------+---+  +-------+------+
    | CycleBoard |  | Mosaic     |  | Delta-Kernel |
    | state.js   |  | Dashboard  |  | Web App.tsx  |
    +-----+------+  +-----+-----+  +------+-------+
          |                |               |
          v                v               v
    localStorage      React state     localStorage
    (fallback)        (in-memory)     (fallback)
    +                 30s polling      on-demand
    API sync                          with fallback
    (2s debounce)

  COGNITIVE STATE FILES (cycleboard/brain/)
    Written by: cognitive-sensor wire_cycleboard.py
    Read by:    CycleBoard (fallback when API unavailable)
    Files:      cognitive_state.json, daily_payload.json,
                governance_state.json, idea_registry.json,
                prediction_results.json, daily_directive.txt

  IDEA FLOW
    idea_dashboard.html --addToAZ()--> localStorage
                                           |
    CycleBoard state.js  <----reads--------+
```

### 3.3 Mode Display Chain

```
  ORIGIN: delta-kernel routing.ts (deterministic Markov)
           |
           v
  /api/state/unified --> { mode: "BUILD" }
           |
     +-----+-----+-----+-----+-----+
     |     |     |     |     |     |
     v     v     v     v     v     v
  Mosaic  Cycle  DK   Aegis  Atlas Control
  Dash    Board  Web   Dash  Boot  Panel
  :3000   :8889       :3002       :3001/ui

  Each renders mode with color coding:
    RECOVER     = RED
    CLOSURE     = AMBER
    MAINTENANCE = BLUE
    BUILD       = GREEN
    COMPOUND    = PURPLE
    SCALE       = CYAN
```

### 3.4 Iframe Embedding Hierarchy

```
  atlas_boot.html (root shell)
    |
    +-- Tab iframes (center viewport)
    |   +-- CycleBoard (cycleboard/index.html)
    |   +-- Cognitive Atlas (atlas_template.html)
    |   +-- System Map (system-map.html)
    |   +-- Other pages...
    |
    +-- Dashboard iframe (right panel, 400px)
        +-- Mosaic Dashboard (:3000)
        +-- Or other dashboard surface

  Communication: window.postMessage (AtlasNav in app.js)
```

---

## 4. Polling & Refresh Intervals

```
+---------------------------+------------+---------------------------+
| Component                 | Interval   | Endpoint                  |
+---------------------------+------------+---------------------------+
| CockpitPanel (brief)      | 30s        | GET /api/delta/daily-brief|
| CockpitPanel (approvals)  | 30s        | GET /api/aegis/approvals  |
| ModePanel                 | 30s        | GET /api/delta/state/uni  |
| SimulationPanel (running) | 2s         | GET /api/mirofish/sim/:id |
| Atlas Boot                | 10s->120s  | GET /api/state/unified    |
|  (exponential backoff)    |            |  (pauses when tab hidden) |
| DK Control Panel          | 5s         | GET /api/work/status      |
| DK Timeline               | 10s        | GET /api/timeline         |
| Aegis Dashboard (tabs)    | 10s        | Various per-tab           |
| CycleBoard (state save)   | 2s debounce| POST /api/cycleboard      |
+---------------------------+------------+---------------------------+
```

---

## 5. CSS & Styling Summary

```
+---------------------------+------------------------------------------+
| Frontend                  | Styling Approach                          |
+---------------------------+------------------------------------------+
| Mosaic Dashboard          | Tailwind CSS, zinc-900 dark theme         |
| CycleBoard                | Custom CSS (styles.css), responsive       |
| Aegis Dashboard           | Tailwind CSS + custom dark theme          |
| Delta-Kernel Web          | CSS Modules (App.css), dark theme         |
| Control Panel             | Tailwind CSS + Font Awesome               |
| Atlas Template            | Custom CSS + Plotly/Sigma.js styles       |
| Idea Dashboard            | Custom CSS, dark cards, modal overlay     |
| Docs Viewer               | Custom CSS, 3-column flex layout          |
| Blueprint Generator       | CSS Modules, dark theme                   |
| Atlas Boot                | Custom CSS, flexbox shell layout          |
| System pages              | Custom CSS, gradients, cards              |
+---------------------------+------------------------------------------+
All frontends use DARK theme by default.
```
