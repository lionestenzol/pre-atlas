# CycleBoard Component Registry

> Source: `services/cognitive-sensor/cycleboard/`  
> Served at: `http://localhost:8889/`  
> Stack: Vanilla JS · Tailwind CSS (CDN 3.4.1) · Font Awesome 6.4  
> Generated from: source read + live UI capture, 2026-07-16

---

## Shell

### `index.html`
Top-level page scaffold. Loads all modules and declares the permanent DOM skeleton.

**Static DOM regions (always present)**

| ID | Role |
|----|------|
| `#service-health-bar` | Sticky top bar — service dots + mode + directive text |
| `#cognitive-directive` | Collapsible sticky banner (online/offline states) |
| `#cognitive-indicator` | Minimized dot (top-right, shown when banner is hidden) |
| `#app` | Root flex container (sidebar + main) |
| `#sidebar` | Left navigation (desktop, fixed on mobile) |
| `#nav` | Dynamic nav list — rendered by `renderNav()` |
| `#main-content` | Scrollable main area |
| `#lifecycle-panel` | Thread lifecycle section (always visible above screens) |
| `#modal-container` | Portal for all modals |
| `#toast-container` | Fixed bottom-right toast stack |
| Mobile `<nav>` | Bottom tab bar (Home / Command / Statistics / OSINT) |

**Script load order**

```
state.js → validator.js → ui.js → helpers.js →
screens.js → functions.js → command.js →
cognitive.js → strategic.js →
ai-context.js → ai-actions.js →
app.js
```

---

## Modules

### `js/state.js` — `CycleBoardState`

Global state singleton (`stateManager`). Persists to `localStorage` and syncs to delta-kernel API (:3001).

**Inputs**
- `localStorage['cycleboard-state']` — persisted JSON blob on boot
- `GET /api/state` (delta-kernel) — hydrates from API if newer
- `stateManager.apiKey` — bearer token loaded via `loadApiKey()`

**Outputs**
- `stateManager.state` — reactive object exposed as `window.state` via `Object.defineProperty`
- `stateManager.update()` — triggers debounced save + API sync
- `stateManager.undo()` / `redo()` — 50-entry history ring

**State shape (default)**

| Key | Type | Description |
|-----|------|-------------|
| `version` | `"2.0"` | Schema version |
| `screen` | `string` | Current screen ID (e.g. `"Home"`) |
| `AZTask` | `Task[]` | A–Z letter-task list |
| `DayPlans` | `Record<date, DayPlan>` | Per-date day plans |
| `FocusArea` | `FocusArea[]` | 6 named focus areas with colors + tasks |
| `Routine` | `{Morning, Commute, Evening}` | Checklist arrays |
| `DayTypeTemplates` | `{A, B, C}` | Named day-type time-block schedules |
| `Reflections` | `Reflection[]` | Weekly/monthly/quarterly/yearly entries |
| `Journal` | `JournalEntry[]` | Free-form journal entries |
| `Skills` | `Skill[]` | Tracked skills |
| `Network` | `Contact[]` | Network contacts |
| `Settings` | `{darkMode, ...}` | App preferences |
| `Finance` | `FinanceEntry[]` | Finance entries |

**Constants**
- `TASK_STATUS`: `Not Started · In Progress · Completed`
- `DAY_TYPE`: `A · B · C`
- `REFLECTION_PERIOD`: `weekly · monthly · quarterly · yearly`

---

### `js/ui.js` — `UI`

Shared UI utility object. Handles toasts, modals, XSS escaping, and Tailwind color class lookup.

**Inputs** — called by any module

**Outputs / methods**

| Method | Description |
|--------|-------------|
| `UI.showToast(msg, type)` | Appends toast to `#toast-container`; auto-removes after 3 s |
| `UI.showModal(html)` | Injects HTML into `#modal-container` and shows it |
| `UI.closeModal()` | Clears `#modal-container` |
| `UI.sanitize(str)` | HTML-escapes string (XSS guard) |
| `UI.getColorClass(color, type)` | Returns safe Tailwind class from `colorClasses` map |

**Color palette**: `blue · green · purple · orange · yellow · red · amber`

---

### `js/helpers.js` — `Helpers`

Pure utility functions (no DOM side effects).

**Key methods**

| Method | Returns |
|--------|---------|
| `Helpers.formatDate(date)` | Locale date string |
| `Helpers.calculateCompletionPercentage(tasks)` | `0–100` (for AZTask) |
| `Helpers.getDayType(plan)` | `"A" · "B" · "C"` |
| `Helpers.getMonthlyStats(state)` | `{days, completed, total}` |
| `Helpers.getWeeklyStats(state)` | `{percentage, completed, total}` |

---

### `js/screens.js` — `screens` array + `ScreenRenderers`

Declares the 16 navigable screens and their renderer functions.

**`screens` array** (defines nav order, icon, label)

| Index | ID | Label | Icon |
|-------|----|-------|------|
| 0 | `Command` | Command | `fa-terminal` |
| 1 | `Home` | Home | `fa-home` |
| 2 | `Daily` | Daily | `fa-calendar-day` |
| 3 | `AtoZ` | A to Z | `fa-list-ol` |
| 4 | `WeeklyFocus` | Weekly Focus | `fa-bullseye` |
| 5 | `Routines` | Routines | `fa-clock` |
| 6 | `Journal` | Journal | `fa-book` |
| 7 | `Reflections` | Reflections | `fa-lightbulb` |
| 8 | `Energy` | Energy | `fa-bolt` |
| 9 | `Finance` | Finance | `fa-wallet` |
| 10 | `Skills` | Skills | `fa-graduation-cap` |
| 11 | `Network` | Network | `fa-users` |
| 12 | `OSINT` | OSINT | `fa-satellite-dish` |
| 13 | `Statistics` | Statistics | `fa-chart-line` |
| 14 | `Timeline` | Timeline | `fa-stream` |
| 15 | `Settings` | Settings | `fa-cog` |

**Navigation functions**

| Function | Description |
|----------|-------------|
| `renderNav()` | Builds `#nav` list; adds `%` badge on Home when completion > 0 |
| `navigate(screenId)` | Sets `state.screen`, calls `stateManager.update()` + `render()`, closes mobile sidebar |
| `render()` | Dispatches to `ScreenRenderers[state.screen]()`, injects into `#main-content` |

---

#### Screen Renderers

Each renderer reads from `state` and/or `BrainData` and writes HTML into `#main-content`.

---

##### `ScreenRenderers.Home`

**Inputs**
- `BrainData.energyMetrics` → energy level, mental load, burnout risk, red alert, life phase
- `BrainData.financeMetrics` → runway months, money delta
- `BrainData.skillsMetrics` → utilization %
- `BrainData.networkMetrics` → collaboration score
- `BrainData.governorHeadline` → drift score, drift alerts, compliance rate
- `CognitiveController.payload` → closure ratio, open loops, mode
- `state.AZTask` → completion %, task status distribution
- `state.DayPlans` → monthly / weekly stats, day-type distribution

**Outputs (rendered sections)**

| Section | Contents |
|---------|----------|
| Strategic HUD | 5-column grid: Energy · Runway · Skills · Network · Mental Load; each links to its screen |
| Active Days card | `monthlyStats.days` / 30 days active % |
| Weekly Success card | `weeklyStats.percentage` % of days meeting goals |
| Task Status Distribution | Bar chart: Completed / In Progress / Not Started (AZTask) |
| Day Type Usage | Bar chart: A / B / C day counts |
| Recent Activity | Last 5 completed AZTasks |
| Cognitive Health | Mode · Closure Ratio · Drift Score · Compliance; drift alerts list; "Full atlas →" button |

---

##### `ScreenRenderers.Statistics`

**Inputs**: `state.AZTask`, `state.DayPlans`, `state.Reflections`

**Outputs**: Active days, weekly success %, task status distribution bars, day-type usage bars, recent completed-task activity feed

---

##### `ScreenRenderers.Command`

Handled by `js/command.js` — see Command module below.

---

##### Other screens (inputs → state keys)

| Screen | Primary state keys | BrainData keys |
|--------|--------------------|----------------|
| `Daily` | `state.DayPlans[today]`, `state.Routine`, `state.DayTypeTemplates` | — |
| `AtoZ` | `state.AZTask`, `state.FocusArea` | — |
| `WeeklyFocus` | `state.DayPlans` (weekly window), `state.FocusArea` | `weeklyPlan` |
| `Routines` | `state.Routine`, `state.DayTypeTemplates` | — |
| `Journal` | `state.Journal` | — |
| `Reflections` | `state.Reflections` | — |
| `Energy` | `state.Settings` | `energyMetrics` |
| `Finance` | `state.Finance` | `financeMetrics` |
| `Skills` | `state.Skills` | `skillsMetrics` |
| `Network` | `state.Network` | `networkMetrics` |
| `OSINT` | — | `osintFeed` |
| `Timeline` | `state.DayPlans`, `state.AZTask`, `state.Reflections` | — |
| `Settings` | `state.Settings` | — |

---

### `js/app.js` — Bootstrap + global singletons

**Singletons declared**

| Name | Type | Purpose |
|------|------|---------|
| `stateManager` | `CycleBoardState` | Global state |
| `AtlasNav` | object | Cross-view navigation |
| `BrainData` | object | Brain JSON data store |
| `ServiceHealthBar` | object | Top health bar updater |
| `window.state` | proxy | Reactive alias to `stateManager.state` |

---

#### `AtlasNav`

Routes navigation between views. Detects embedded (in `atlas_boot.html`) vs standalone.

**Inputs**
- `window !== window.parent` — embedded detection

**Outputs**
- `AtlasNav.open(target)` — sends `postMessage` to parent (embedded) or `window.open` (standalone)

**Target → URL map**

| Target | URL |
|--------|-----|
| `control` | `/cognitive-sensor/control_panel.html` |
| `atlas` | `/cognitive-sensor/cognitive_atlas.html` |
| `ideas` | `/cognitive-sensor/idea_dashboard.html` |
| `docs` | `/cognitive-sensor/docs_viewer.html` |
| `aegis` | `../../aegis-fabric/src/ui/dashboard.html` |
| `timeline` | `../../delta-kernel/src/ui/timeline.html` |
| `boot` | `../../../atlas_boot.html` |

---

#### `BrainData`

Async data store. Tries delta-kernel API first, falls back to local `brain/*.json` files.

**Load sequence**: `BrainData.load()` → `Promise.allSettled` over all sources

| Key | API source | Fallback file |
|-----|-----------|---------------|
| `ideaRegistry` | `:3001/api/ideas` | `brain/idea_registry.json` |
| `governanceState` | `:3001/api/governance/config` | `brain/governance_state.json` |
| `governorHeadline` | — (file only) | `brain/governor_headline.json` |
| `energyMetrics` | — | `brain/energy_metrics.json` |
| `financeMetrics` | — | `brain/finance_metrics.json` |
| `skillsMetrics` | — | `brain/skills_metrics.json` |
| `networkMetrics` | — | `brain/network_metrics.json` |
| `osintFeed` | — | `brain/osint_feed.json` |
| `weeklyPlan` | — | `brain/weekly_plan.json` |

**Accessor methods**

| Method | Returns |
|--------|---------|
| `getTopIdeas(n=3)` | First n `execute_now` ideas |
| `getNextUpIdeas(n=5)` | First n `next_up` ideas |
| `getDriftScore()` | `governorHeadline.drift_score` |
| `getDriftAlerts()` | `governorHeadline.drift_alerts[]` |
| `getComplianceRate()` | `governorHeadline.compliance_rate` |
| `getLastRefresh()` | `governorHeadline.generated_at` |
| `getTopMove()` | `governorHeadline.top_move` |
| `getWarning()` | `governorHeadline.warning` |
| `getEnergyLevel()` | `energyMetrics.energy_level` (default 50) |
| `getMentalLoad()` | `energyMetrics.mental_load` (default 5) |
| `getBurnoutRisk()` | `energyMetrics.burnout_risk` (default false) |
| `getRedAlertActive()` | `energyMetrics.red_alert_active` |
| `getRunwayMonths()` | `financeMetrics.runway_months` (default 3) |
| `getMoneyDelta()` | `financeMetrics.money_delta` |
| `getSkillsUtilization()` | `skillsMetrics.utilization_pct` |
| `getNetworkScore()` | `networkMetrics.collaboration_score` |
| `getLifePhase()` | `energyMetrics.life_phase` → `governanceState.life_phase` → 1 |
| `getLifePhaseName()` | `{1:"Stabilization", 2:"Leverage", 3:"Extraction", 4:"Scaling", 5:"Generational"}` |

---

#### `ServiceHealthBar`

Polls service health every 60 s. Updates the `#service-health-bar` DOM region.

**Inputs**
- `brain/daily_payload.json` → `{generated_at, mode, directive, primary_action}`
- `GET /api/services/health` → `{delta: {status}, uasc: {status}, cortex: {status}}`

**Outputs (DOM)**

| Element | Content |
|---------|---------|
| `#health-dot-delta/uasc/cortex` | CSS class `service-health-dot--up/down` |
| `#health-last-refresh` | Formatted timestamp |
| `#health-mode` | Mode string |
| `#health-directive` | Primary directive text |

---

### `js/cognitive.js` — `CognitiveController` + `DataFreshness`

Manages the sticky cognitive-directive banner. Polls delta-kernel's unified state endpoint.

**`DataFreshness`**

Utility: `DataFreshness.check(dateString, thresholdHours=24)` → `{stale, ageHours, ageText}`

**`CognitiveController`**

**Inputs**
- `GET :3001/api/state/unified` → `{ok, cognitive: {cognitive_state, today}, derived: {build_allowed}, ts}`
- `brain/daily_payload.json` → directive text fallback
- `stateManager.apiKey` — auth header

**Outputs (DOM)**

| Element | Content |
|---------|---------|
| `#cognitive-directive` | Shown/hidden; colored by mode |
| `#cognitive-online-msg` | Visible when API available |
| `#cognitive-offline-msg` | Visible when API offline |
| `#directive-mode` | Mode label (e.g. `BUILD`) |
| `#directive-risk` | Risk tier |
| `#directive-loops` | Open loops count (links to control panel) |
| `#directive-action` | Recommended action text |
| `#cognitive-indicator` | Minimized dot (color reflects mode) |

**State fields**

| Field | Type | Description |
|-------|------|-------------|
| `payload` | object | `cognitive_state` from unified API |
| `dailyPayload` | object | `today` from unified API |
| `buildAllowed` | bool | Whether build mode is permitted |
| `bannerVisible` | bool | Banner expand/collapse state |
| `directiveText` | string | Directive text for display |
| `freshness` | object | `DataFreshness` result |

**Methods**

| Method | Description |
|--------|-------------|
| `CognitiveController.init()` | First load; calls `_loadData(true)` |
| `CognitiveController.startPolling()` | Sets poll timer (interval from unified response or 5 min default) |
| `toggleCognitiveBanner()` | Global function — toggles banner / indicator |

---

### `js/strategic.js` — `StrategicRouter`

**Inputs**: `CognitiveController.payload`, `BrainData.governorHeadline`

**Outputs**: Strategic recommendations overlay or sidebar widget (exact DOM target: `#strategic-panel` if present)

---

### `js/command.js` — Command screen

Renders the Command screen (`#main-content` when `state.screen === "Command"`).

**Inputs**
- `BrainData.getTopIdeas()` → top 3 execute-now ideas
- `BrainData.getNextUpIdeas()` → next 5 ideas
- `BrainData.getTopMove()`, `getWarning()`
- `CognitiveController.payload` → mode, open loops

**Outputs**: Rendered HTML with command-center layout (ideas, top move, warning, mode context)

---

### `js/functions.js` — Data operations

Global utility functions (called from sidebar buttons).

| Function | Trigger | Effect |
|----------|---------|--------|
| `exportState()` | Sidebar "Export Data" button | Downloads `cycleboard-export-<date>.json` |
| `showImportModal()` | Sidebar "Import Data" button | Opens file-picker modal via `UI.showModal` |
| `clearData()` | Sidebar "Clear All Data" button | Resets `state` to default, saves |

---

### `js/ai-context.js`

**`showCopyContextModal()`** — Triggered by sidebar "Copy AI Context" button.

**Inputs**: Full `stateManager.state`, `CognitiveController.payload`, `BrainData.*`

**Output**: Modal with formatted AI context blob (copy-to-clipboard)

---

### `js/ai-actions.js`

AI action dispatch layer. Handles AI-generated action suggestions and confirmation flows.

**Inputs**: `CognitiveController.payload`, user confirmation events

**Outputs**: Calls `stateManager.update()` or delta-kernel write endpoints

---

### `js/validator.js`

Input validation utilities. Called by `functions.js` and screen renderers before state writes.

---

## Permanent Panels

### `#lifecycle-panel` (inline script in `index.html`)

Always visible above screen content. Fed by `brain/lifecycle_board.json`, generated by `python wire_cycleboard.py`.

**Inputs**
- `brain/lifecycle_board.json` (fetched no-store on load)
  - `in_progress[]` → `{convo_id|loop_id, title, status, artifact_path}`
  - `terminal_today` → `{DONE[], RESOLVED[], DROPPED[]}` each with same shape + `coverage_score`
  - `counts` → `{HARVESTED, PLANNED, BUILDING, REVIEWING, DONE, RESOLVED, DROPPED}`
  - `generated_at` → timestamp string

**Outputs (DOM)**

| Element | Content |
|---------|---------|
| `#lifecycle-generated` | `generated_at` timestamp |
| `#lifecycle-in-progress-list` | Rows: `[STATUS badge] [#id] [title] [:artifact_path]` |
| `#lifecycle-terminal-list` | Same format + `cov N.NN` for terminal items |
| `#lifecycle-counts` | Inline count chips for all 7 statuses |

**Status badge colors**

| Status | Color |
|--------|-------|
| PLANNED | `bg-yellow-700` |
| BUILDING | `bg-blue-700` |
| REVIEWING | `bg-purple-700` |
| DONE | `bg-green-700` |
| RESOLVED | `bg-cyan-700` |
| DROPPED | `bg-gray-600` |

---

## Sidebar Actions

| Button | `onclick` | Effect |
|--------|-----------|--------|
| Copy AI Context | `showCopyContextModal()` | Opens AI context modal |
| Export Data | `exportState()` | Downloads JSON export |
| Import Data | `showImportModal()` | Opens import file modal |
| Clear All Data | `clearData()` | Clears + resets state |

---

## Cognitive Banner Actions

| Button | `onclick` | Effect |
|--------|-----------|--------|
| Control Panel icon | `openControlPanel()` | Opens control panel (AtlasNav) |
| Minimize chevron | `toggleCognitiveBanner()` | Collapses banner; shows indicator dot |
| MODE text | `AtlasNav.open('atlas')` | Opens Cognitive Atlas |
| OPEN LOOPS text | `AtlasNav.open('control')` | Opens Control Panel |

---

## Data Flow Summary

```
delta-kernel :3001
  ├─ /api/state/unified         → CognitiveController (banner, mode, risk, loops)
  ├─ /api/ideas                 → BrainData.ideaRegistry
  └─ /api/governance/config     → BrainData.governanceState

brain/*.json (local files, from wire_cycleboard.py / refresh.py)
  ├─ lifecycle_board.json       → #lifecycle-panel (inline script)
  ├─ daily_payload.json         → ServiceHealthBar
  ├─ governor_headline.json     → BrainData.governorHeadline
  ├─ energy_metrics.json        → BrainData.energyMetrics
  ├─ finance_metrics.json       → BrainData.financeMetrics
  ├─ skills_metrics.json        → BrainData.skillsMetrics
  ├─ network_metrics.json       → BrainData.networkMetrics
  ├─ osint_feed.json            → BrainData.osintFeed
  └─ weekly_plan.json           → BrainData.weeklyPlan

localStorage
  └─ cycleboard-state           → CycleBoardState (AZTask, DayPlans, Journal, ...)
```

---

## CSS

**`css/styles.css`** — custom classes for:
- `.service-health-bar` / `.service-health-dot--up/down`
- `.fade-in` animation
- Dark-mode overrides not covered by Tailwind CDN config

Tailwind `darkMode: 'class'` — toggled via `toggleDarkMode()` (adds/removes `dark` on `<html>`). Always starts in dark mode.

---

## Init Sequence (DOMContentLoaded in `app.js`)

```
1. Force dark mode
2. init()                          → renderNav() + navigate(state.screen)
3. ServiceHealthBar.init()         → poll /api/services/health + brain/daily_payload.json
4. stateManager.loadApiKey()
   └── stateManager.loadFromApi()  → hydrate state from delta-kernel; re-render if newer
   └── CognitiveController.init()  → load /api/state/unified; start polling
   └── BrainData.load()            → load all brain sources; re-render
5. StrategicRouter.init()          → (no API key needed)
```
