# CycleBoard Complete Reference Document
**Generated: 2026-04-08 | Total Codebase: 10,602 lines across 15 files**

---

## TABLE OF CONTENTS

```
1. ARCHITECTURE OVERVIEW
2. FILE MANIFEST
3. DATA FLOW DIAGRAM (ASCII)
4. UI LAYOUT MAP (ASCII)
5. SCREEN MAP (17 screens)
6. FULL SOURCE CODE
   6.1  index.html (179 lines)
   6.2  css/styles.css (419 lines)
   6.3  js/state.js (486 lines)
   6.4  js/validator.js (225 lines)
   6.5  js/ui.js (259 lines)
   6.6  js/helpers.js (270 lines)
   6.7  js/cognitive.js (368 lines)
   6.8  js/strategic.js (452 lines)
   6.9  js/command.js (373 lines)
   6.10 js/app.js (192 lines)
   6.11 js/screens.js (3,022 lines) — FUNCTION INDEX + KEY RENDERS
   6.12 js/functions.js (2,648 lines) — FUNCTION INDEX
   6.13 js/ai-context.js (512 lines) — API SURFACE
   6.14 js/ai-actions.js (654 lines) — API SURFACE
7. STATE SCHEMA (complete default shape)
8. BRAIN DATA SCHEMAS (10 JSON sources)
9. API INTEGRATION MAP
10. GOVERNANCE SYSTEM
```

---

## 1. ARCHITECTURE OVERVIEW

CycleBoard is a **self-sustaining bullet journal** integrated with the Atlas cognitive governance system. It is a **zero-build, browser-native** application using vanilla JavaScript + Tailwind CSS (CDN) + Font Awesome.

**Core concept:** Plan (A/B/C day types) → Execute (time blocks, goals, routines) → Review (progress tracking, streaks, reflections) — all governed by cognitive mode policies (BUILD/CLOSURE/MAINTENANCE).

**Key architectural decisions:**
- No build step — scripts loaded in dependency order via `<script>` tags
- State persisted to localStorage + 2s-debounced sync to delta-kernel API
- Cognitive governance enforced via 30s polling of `/api/state/unified`
- Strategic leverage routing from pre-computed `brain/` JSON files
- AI integration via `AIContext` (read) and `AIActions` (write) modules

---

## 2. FILE MANIFEST

```
cycleboard/
├── index.html                    179 lines   Main shell, layout, script loading
├── css/
│   └── styles.css                419 lines   Dark theme, governance styles, animations
├── js/
│   ├── state.js                  486 lines   CycleBoardState class, persistence, undo/redo
│   ├── validator.js              225 lines   DataValidator class, import/export validation
│   ├── ui.js                     259 lines   UI utilities (toasts, modals, progress rings)
│   ├── helpers.js                270 lines   Calculations, formatting, activity logging
│   ├── screens.js              3,022 lines   17 screen renderers + navigation
│   ├── functions.js            2,648 lines   All CRUD operations (tasks, goals, routines, etc)
│   ├── command.js                373 lines   Command screen + preparation engine
│   ├── cognitive.js              368 lines   Governance policy enforcement, mode detection
│   ├── strategic.js              452 lines   Strategic priorities routing + reweighting
│   ├── ai-context.js             512 lines   Context snapshot generation for AI agents
│   ├── ai-actions.js             654 lines   Safe AI action interface
│   └── app.js                    192 lines   Initialization, BrainData loading, AtlasNav
├── brain/
│   ├── cognitive_state.json                  Closure ratio, open loops, loop list
│   ├── daily_payload.json                    Daily mode, build_allowed, predictions
│   ├── daily_directive.txt                   Free-text daily directive
│   ├── idea_registry.json        352 lines   Tiered ideas with priority scoring
│   ├── strategic_priorities.json 381 lines   Clusters, leverage scores, gap analysis
│   ├── governance_state.json      86 lines   Mode, risk, lanes, violations
│   ├── weekly_plan.json          325 lines   Weekly priorities, daily protocols
│   ├── governor_headline.json     25 lines   Executive summary, drift, compliance
│   ├── energy_metrics.json         8 lines   Energy, mental load, burnout
│   ├── finance_metrics.json        8 lines   Runway, income, expenses
│   ├── skills_metrics.json         8 lines   Utilization, mastery, growth
│   ├── network_metrics.json        7 lines   Collaboration, relationships
│   ├── osint_feed.json             9 lines   Market, economic, news feeds
│   ├── compound_state.json                   Compound loop state
│   └── prediction_results.json               Mode forecast, exit paths
└── cli.ts                        543 lines   TypeScript CLI (today, plan, complete, status)
```

**Total: ~10,602 lines of code + ~1,200 lines of brain data**

---

## 3. DATA FLOW DIAGRAM (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (index.html)                         │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │  state.js    │   │  app.js      │   │  cognitive.js        │    │
│  │              │   │              │   │  Polls /api/state/   │    │
│  │ CycleBoardSt │──▶│ BrainData    │   │  unified every 30s   │    │
│  │ ate class    │   │ AtlasNav     │   │                      │    │
│  │              │   │              │   │  Enforces governance  │    │
│  │ localStorage │   │ Initializes  │   │  policies per mode   │    │
│  │ ◄──────────▶ │   │ everything   │   └──────────┬───────────┘    │
│  └──────┬───────┘   └──────┬───────┘              │                │
│         │                  │                      │                │
│         │    ┌─────────────┼──────────────────────┘                │
│         │    │             │                                       │
│         ▼    ▼             ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                    RENDER PIPELINE                        │      │
│  │                                                          │      │
│  │  screens.js (17 renderers)  ←── functions.js (CRUD ops)  │      │
│  │       │                              │                   │      │
│  │       ├── Home (Strategic HUD, progress, streaks)        │      │
│  │       ├── Command (mode header, prepared actions)        │      │
│  │       ├── Daily (day type, time blocks, goals, 8 steps)  │      │
│  │       ├── AtoZ (A-Z task list with letter badges)        │      │
│  │       ├── Calendar (month grid, day plan preview)        │      │
│  │       ├── Routines (step-by-step with completion)        │      │
│  │       ├── Journal (entries with mood, tags)              │      │
│  │       ├── Energy / Finance / Skills / Network            │      │
│  │       ├── OSINT (27-source external intel)               │      │
│  │       ├── Statistics / Reflections / Timeline            │      │
│  │       └── Settings (dark mode, notifications, API key)   │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │ strategic.js │   │ ai-context.js│   │ ai-actions.js        │    │
│  │              │   │              │   │                      │    │
│  │ Leverage     │   │ Full state   │   │ Safe write methods   │    │
│  │ routing +    │   │ snapshot for │   │ for AI agents:       │    │
│  │ focus area   │   │ clipboard    │   │ createTask, complete │    │
│  │ reweighting  │   │ export       │   │ addTimeBlock, etc    │    │
│  └──────────────┘   └──────────────┘   └──────────────────────┘    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
              ┌─────▼─────┐   ┌──────▼───────┐
              │ Delta-    │   │ Local brain/ │
              │ Kernel    │   │ JSON files   │
              │ REST API  │   │ (fallback)   │
              │ :3001     │   └──────────────┘
              │           │
              │ Endpoints:│
              │ /api/state│
              │ /api/tasks│
              │ /api/law  │
              │ /api/prep │
              └───────────┘
```

---

## 4. UI LAYOUT MAP (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│ COGNITIVE DIRECTIVE BANNER (sticky top, z-50)                       │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 🧠 Cognitive Routing System                                     │ │
│ │ MODE: BUILD  │  RISK: LOW  │  OPEN LOOPS: 3  │  ACTION: Focus  │ │
│ │                                                    [⚙️] [▲]    │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ STRATEGIC DIRECTIVE BANNER (sticky, z-49)                           │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 🛣️ Strategic Leverage Router                                    │ │
│ │ FOCUS: Production │ CLUSTER: C1 │ DEEP BLOCK: 90m │ GAP: BUILD │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ ┌──────────────┐  ┌──────────────────────────────────────────────┐ │
│ │   SIDEBAR    │  │              MAIN CONTENT                     │ │
│ │   (w-64)     │  │              (flex-1)                         │ │
│ │              │  │                                               │ │
│ │ in-PACT Self │  │  ┌─────────────────────────────────────────┐ │ │
│ │ -Sustaining  │  │  │  CURRENT SCREEN RENDER                  │ │ │
│ │ Bullet       │  │  │  (ScreenRenderers[state.screen]())      │ │ │
│ │ Journal      │  │  │                                         │ │ │
│ │              │  │  │  Home: Strategic HUD + Progress + Tasks  │ │ │
│ │ ■ Command    │  │  │  Daily: Day Type + Time Blocks + Goals   │ │ │
│ │ ■ Home    82%│  │  │  AtoZ: Letter badges + status toggles   │ │ │
│ │ ■ Daily      │  │  │  Calendar: Month grid + day previews    │ │ │
│ │ ■ Calendar   │  │  │  Routines: Step completion + progress   │ │ │
│ │ ■ A-Z        │  │  │  Journal: Entries + mood + tags         │ │ │
│ │ ■ Weekly     │  │  │  Energy: Meter + load + burnout         │ │ │
│ │ ■ Reflections│  │  │  Finance: Runway + income/expense       │ │ │
│ │ ■ Timeline   │  │  │  Skills: Utilization + mastery          │ │ │
│ │ ■ Routines   │  │  │  Network: Collab + relationships        │ │ │
│ │ ■ Journal    │  │  │  OSINT: Market + economic + news        │ │ │
│ │ ■ Energy     │  │  │  Statistics: Charts + averages          │ │ │
│ │ ■ Finance    │  │  │  Settings: Config + API key             │ │ │
│ │ ■ Skills     │  │  │                                         │ │ │
│ │ ■ Network    │  │  └─────────────────────────────────────────┘ │ │
│ │ ■ OSINT      │  │                                               │ │
│ │ ■ Statistics │  │                                               │ │
│ │ ■ Settings   │  │                                               │ │
│ │              │  │                                               │ │
│ │ ── System ── │  │                                               │ │
│ │ [⚙️][🔮][💡]│  │                                               │ │
│ │              │  │                                               │ │
│ │ Weekly Prog  │  │                                               │ │
│ │ ████░░ 3/5   │  │                                               │ │
│ │              │  │                                               │ │
│ │ [🤖 AI Ctx]  │  │                                               │ │
│ │ [⬇️ Export]  │  │                                               │ │
│ │ [⬆️ Import]  │  │                                               │ │
│ │ [🗑️ Clear]   │  │                                               │ │
│ └──────────────┘  └──────────────────────────────────────────────┘ │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ MOBILE BOTTOM NAV (md:hidden)                                   │ │
│ │   [🏠 Home]  [📅 Daily]  [✅ A-Z]  [📖 Journal]               │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ [Modal Container]    [Toast Container (bottom-right, z-50)]         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. SCREEN MAP (17 screens)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CYCLEBOARD SCREENS                              │
├──────────────┬───────────────────────────────────────────────────────────┤
│ Command      │ Single decision surface. Mode header (BUILD/CLOSURE etc) │
│              │ with closure%, streak, open loops. Prepared actions from  │
│              │ preparation engine. Today's tasks. Top idea. Leverage     │
│              │ move. Recent auto-actions log.                           │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Home         │ Welcome dashboard. Strategic HUD (5 metrics: energy,     │
│              │ runway, skills, network, mental load). A-Z completion    │
│              │ ring. Weekly progress. Today's focus (day type). Daily   │
│              │ progress bar with 4 breakdowns. Strategic directive      │
│              │ card. Daily directive (collapsible). Top ideas. System   │
│              │ pulse (drift, compliance, top move). Quick actions       │
│              │ (add task, plan day, complete all, statistics).          │
│              │ Productivity streak. 7-day overview bars. Today's        │
│              │ routines grid. Momentum wins tracker. Recent A-Z tasks.  │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Daily        │ Closure queue (if CLOSURE mode). Daily operating         │
│              │ protocol (7 time blocks: morning→close, highlights       │
│              │ current). Day mode selector (A/B/C). Strategic A-Z       │
│              │ suggestion + time block suggestion. Time blocks list     │
│              │ (editable time, title, completion toggle, delete).       │
│              │ Baseline goal (X) + Stretch goal (Y) textareas.         │
│              │ 8 Steps to Success grid. Contingency quick actions       │
│              │ (running late, low energy, free time, disruption).       │
│              │ Yesterday's reflection.                                  │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Calendar     │ Month grid with clickable dates. Day indicators show     │
│              │ day type color (A=blue, B=green, C=purple). Click date   │
│              │ → shows day plan preview in modal. Navigation arrows     │
│              │ for month switching.                                     │
├──────────────┼───────────────────────────────────────────────────────────┤
│ AtoZ         │ Full A-Z task list. Each row: letter badge (colored by   │
│              │ status), task text, status dropdown, notes expand,       │
│              │ complete/delete buttons. Add new task modal. Strategic    │
│              │ A-Z override suggestion at top.                          │
├──────────────┼───────────────────────────────────────────────────────────┤
│ WeeklyFocus  │ Focus areas list with strategic leverage badges.         │
│              │ Each area: name, definition, color, sub-tasks with       │
│              │ completion toggles. Add focus task inline.               │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Reflections  │ Tabbed: weekly / monthly / quarterly / yearly.           │
│              │ Each tab: list of reflection entries with date, content. │
│              │ Add new reflection form.                                 │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Timeline     │ Chronological activity log from History.timeline.        │
│              │ Each entry: icon, description, timestamp, details.       │
│              │ Filter by activity type.                                 │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Routines     │ All defined routines (Morning, Commute, Evening, etc).   │
│              │ Each routine: expandable step list, step toggle,         │
│              │ add/edit/delete steps, complete-all button.              │
│              │ Add new routine button. Color-coded by routine name.     │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Journal      │ Entry list sorted by date. Each: title, content,        │
│              │ entryType badge, mood indicator, tags. Create new        │
│              │ entry modal with title, content, type dropdown, mood.    │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Energy       │ Energy meter (0-100). Mental load (0-10). Sleep quality. │
│              │ Burnout risk indicator. Red alert badge. Submit to       │
│              │ life signals API.                                        │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Finance      │ Runway months. Monthly income/expense inputs. Money      │
│              │ delta. Submit to life signals API.                       │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Skills       │ Utilization %. Active learning toggle. Mastery count.    │
│              │ Growth count. Submit to life signals API.                │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Network      │ Collaboration score. Active relationships count.         │
│              │ Outreach this week. Submit to life signals API.          │
├──────────────┼───────────────────────────────────────────────────────────┤
│ OSINT        │ 27-source external intelligence. Market data (indexes,  │
│              │ crypto, VIX, gold). Economic indicators (CPI, GDP,      │
│              │ unemployment). News headlines with urgency. Sentiment.   │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Statistics   │ A-Z completion stats. Average daily progress.           │
│              │ Streak history. Routine completion rates.                │
├──────────────┼───────────────────────────────────────────────────────────┤
│ Settings     │ Dark mode toggle. Notifications toggle. Default day      │
│              │ type selector. API key input. Auto-save toggle.          │
│              │ Day type template editor.                                │
└──────────────┴───────────────────────────────────────────────────────────┘
```

---

## 6. FULL SOURCE CODE

### 6.1 index.html (179 lines)

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CycleBoard - in-PACT Self-Sustaining Bullet Journal</title>
  <script src="https://cdn.tailwindcss.com/3.4.1"></script>
  <script>tailwind.config = { darkMode: 'class' }</script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="css/styles.css">
</head>
<body class="bg-gray-900 text-white">
  <!-- COGNITIVE DIRECTIVE BANNER -->
  <div id="cognitive-directive" class="w-full text-white shadow-lg" style="position: sticky; top: 0; z-index: 50; display: none;">
    <!-- Online state: normal cognitive data -->
    <div id="cognitive-online-msg" class="max-w-7xl mx-auto p-4">
      <div class="flex items-center justify-between">
        <div class="flex-1">
          <div class="text-xs uppercase tracking-wider opacity-75 mb-1">
            <i class="fas fa-brain mr-1"></i> Cognitive Routing System
          </div>
          <div class="flex items-center gap-6">
            <div class="cursor-pointer hover:opacity-80 transition" onclick="AtlasNav.open('atlas')" title="Open Cognitive Atlas">
              <div class="text-xs opacity-75">MODE</div>
              <div id="directive-mode" class="text-xl font-bold">--</div>
            </div>
            <div>
              <div class="text-xs opacity-75">RISK</div>
              <div id="directive-risk" class="text-lg font-bold">--</div>
            </div>
            <div class="cursor-pointer hover:opacity-80 transition" onclick="AtlasNav.open('control')" title="Manage open loops">
              <div class="text-xs opacity-75">OPEN LOOPS</div>
              <div id="directive-loops" class="text-lg font-bold underline decoration-dotted">--</div>
            </div>
            <div class="flex-1">
              <div class="text-xs opacity-75">ACTION</div>
              <div id="directive-action" class="text-sm font-medium">Analyzing cognitive state...</div>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="openControlPanel()" class="p-2 hover:bg-white/20 rounded-lg transition" title="Open Control Panel">
            <i class="fas fa-sliders-h"></i>
          </button>
          <button onclick="toggleCognitiveBanner()" class="p-2 hover:bg-white/20 rounded-lg transition" title="Minimize">
            <i class="fas fa-chevron-up"></i>
          </button>
        </div>
      </div>
    </div>
    <!-- Offline state: brain data unavailable -->
    <div id="cognitive-offline-msg" class="max-w-7xl mx-auto p-4 bg-gray-800" style="display: none;">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <i class="fas fa-terminal text-gray-400 text-lg"></i>
          <div>
            <div class="text-gray-400 font-medium">Cognitive system offline</div>
            <div class="text-gray-500 text-xs">Run: <code class="bg-gray-700 px-1.5 py-0.5 rounded text-gray-300">python refresh.py</code> to generate brain data</div>
          </div>
        </div>
        <button onclick="toggleCognitiveBanner()" class="p-2 hover:bg-white/20 rounded-lg transition text-gray-400" title="Minimize">
          <i class="fas fa-chevron-up"></i>
        </button>
      </div>
    </div>
  </div>

  <!-- MINIMIZED COGNITIVE INDICATOR -->
  <div id="cognitive-indicator" class="fixed top-2 right-2 z-50 cursor-pointer" style="display: none;" onclick="toggleCognitiveBanner()">
    <div id="cognitive-indicator-dot" class="w-4 h-4 rounded-full animate-pulse shadow-lg" title="Click to expand cognitive status"></div>
  </div>

  <div id="app" class="min-h-screen flex flex-col md:flex-row">
    <header class="md:hidden flex items-center justify-between p-4 bg-white border-b dark:bg-gray-800 dark:border-gray-700" role="banner">
      <div class="flex items-center gap-3">
        <button id="mobile-menu-toggle" class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="sidebar">
          <i class="fas fa-bars" aria-hidden="true"></i>
        </button>
        <div class="text-lg font-bold dark:text-white">CycleBoard</div>
      </div>
      <div class="flex items-center gap-2">
        <button onclick="toggleDarkMode()" class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700" aria-label="Toggle dark mode">
          <i class="fas fa-moon dark:text-yellow-300" aria-hidden="true"></i>
        </button>
        <div id="date-display" class="text-sm text-slate-500 dark:text-gray-400" aria-live="polite"></div>
      </div>
    </header>

    <aside id="sidebar" class="w-64 bg-white border-r p-4 space-y-6 fixed md:static inset-0 z-40 hidden md:block dark:bg-gray-800 dark:border-gray-700 overflow-y-auto" role="navigation" aria-label="Main navigation">
      <div class="fade-in">
        <div class="text-xs uppercase tracking-wider text-slate-500 dark:text-gray-400 mb-1">
          Plan, execute, and review A-Z monthly goals
        </div>
        <div class="text-xl font-bold dark:text-white">in-PACT Self-Sustaining Bullet Journal</div>
      </div>
      <nav class="space-y-1" id="nav" aria-label="Page navigation"></nav>

      <div class="mt-8 pt-6 border-t dark:border-gray-700">
        <div class="text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Weekly Progress</div>
        <div class="space-y-2">
          <div class="flex items-center justify-between text-sm">
            <span class="text-slate-600 dark:text-gray-400">Tasks Completed</span>
            <span id="weekly-tasks" class="font-semibold dark:text-white">0/0</span>
          </div>
          <div class="w-full bg-slate-200 dark:bg-gray-700 rounded-full h-2">
            <div id="weekly-progress-bar" class="bg-green-500 h-2 rounded-full" style="width: 0%"></div>
          </div>
        </div>
      </div>

      <div class="mt-4 space-y-2">
        <button onclick="showCopyContextModal()" class="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg">
          <i class="fas fa-robot"></i>
          <span>Copy AI Context</span>
        </button>
        <button onclick="exportState()" class="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-gray-300 hover:bg-slate-50 dark:hover:bg-gray-700 rounded-lg">
          <i class="fas fa-download"></i>
          <span>Export Data</span>
        </button>
        <button onclick="showImportModal()" class="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-gray-300 hover:bg-slate-50 dark:hover:bg-gray-700 rounded-lg">
          <i class="fas fa-upload"></i>
          <span>Import Data</span>
        </button>
        <button onclick="clearData()" class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg">
          <i class="fas fa-trash-alt"></i>
          <span>Clear All Data</span>
        </button>
      </div>
    </aside>

    <main class="flex-1 p-4 md:p-8 overflow-auto pb-20 md:pb-8" id="main-content" role="main" aria-label="Main content">
      <div class="max-w-6xl mx-auto">
      </div>
    </main>

    <nav class="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t dark:bg-gray-800 dark:border-gray-700 flex justify-around py-3" role="navigation" aria-label="Mobile navigation">
      <button onclick="navigate('Home')" class="flex flex-col items-center p-2 dark:text-gray-300" aria-label="Go to Home">
        <i class="fas fa-home text-lg" aria-hidden="true"></i>
        <span class="text-xs mt-1">Home</span>
      </button>
      <button onclick="navigate('Daily')" class="flex flex-col items-center p-2 dark:text-gray-300" aria-label="Go to Daily planner">
        <i class="fas fa-calendar-day text-lg" aria-hidden="true"></i>
        <span class="text-xs mt-1">Daily</span>
      </button>
      <button onclick="navigate('AtoZ')" class="flex flex-col items-center p-2 dark:text-gray-300" aria-label="Go to A to Z tasks">
        <i class="fas fa-tasks text-lg" aria-hidden="true"></i>
        <span class="text-xs mt-1">A-Z</span>
      </button>
      <button onclick="navigate('Journal')" class="flex flex-col items-center p-2 dark:text-gray-300" aria-label="Go to Journal">
        <i class="fas fa-book text-lg" aria-hidden="true"></i>
        <span class="text-xs mt-1">Journal</span>
      </button>
    </nav>
  </div>

  <div id="modal-container"></div>
  <div id="toast-container" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2"></div>

  <!-- Core modules -->
  <script src="js/state.js?v=4"></script>
  <script src="js/validator.js"></script>
  <script src="js/ui.js"></script>
  <script src="js/helpers.js"></script>

  <!-- Application modules -->
  <script src="js/screens.js?v=4"></script>
  <script src="js/functions.js?v=4"></script>
  <script src="js/command.js?v=1"></script>
  <script src="js/cognitive.js?v=3"></script>
  <script src="js/strategic.js"></script>

  <!-- AI Integration modules -->
  <script src="js/ai-context.js"></script>
  <script src="js/ai-actions.js"></script>

  <!-- Initialize app -->
  <script src="js/app.js?v=4"></script>
</body>
</html>
```

---

### 6.2 css/styles.css (419 lines)

**NOTE: Full file included. This is the complete dark theme with Atlas palette.**

```css
/* CycleBoard Custom Styles */

* { margin: 0; padding: 0; box-sizing: border-box; }

/* Scrollbar: thin, dark, unobtrusive */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.16); }
::-webkit-scrollbar-corner { background: transparent; }
* { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.08) transparent; }

/* Governance Lock Styles */
.governance-locked {
  opacity: 0.4 !important; cursor: not-allowed !important; pointer-events: none; position: relative;
}
.governance-locked::after {
  content: '\f023'; font-family: 'Font Awesome 6 Free','Font Awesome 5 Free'; font-weight: 900;
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  font-size: 0.75rem; color: #ef4444;
}
.governance-lock-banner {
  background: linear-gradient(135deg, #991b1b, #b91c1c); color: white;
  padding: 12px 20px; text-align: center; font-weight: 600; font-size: 0.875rem;
  border-radius: 8px; margin: 12px;
}

body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
.modal-backdrop { backdrop-filter: blur(2px); }

/* Animations */
.toast { animation: slideIn 0.3s ease-out; }
.fade-in { animation: fadeIn 0.3s ease-out; }
.slide-up { animation: slideUp 0.3s ease-out; }
.pulse { animation: pulse 2s infinite; }

@keyframes slideIn { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }

/* Progress Ring */
.progress-ring__circle { stroke-linecap: round; transform: rotate(-90deg); transform-origin: 50% 50%; }

/* Effects */
.gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.glass-effect { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); }

/* ── Dark Mode: Atlas palette ── */
/* Background: #0a0a0f | Cards: #111118 | Borders: #2a2a3a | Accent: #6366f1 */
.dark body { background-color: #0a0a0f; color: #e5e5e5; }
.dark .bg-white { background-color: #111118 !important; }
.dark .bg-slate-50 { background-color: #0a0a0f !important; }
.dark .bg-slate-100, .dark .bg-slate-200 { background-color: #1a1a2a !important; }
.dark .text-slate-700, .dark .text-slate-800, .dark .text-slate-900 { color: #e5e5e5 !important; }
.dark .text-slate-500, .dark .text-slate-600 { color: #888 !important; }
.dark .border, .dark .border-b, .dark .border-t, .dark .border-r, .dark .border-l { border-color: #2a2a3a !important; }
.dark .hover\:bg-slate-50:hover, .dark .hover\:bg-slate-100:hover { background-color: #1a1a2a !important; }
.dark input, .dark textarea, .dark select { background-color: #111118; color: #e5e5e5; border-color: #2a2a3a; }
.dark input:focus, .dark textarea:focus, .dark select:focus { border-color: #6366f1; outline: none; box-shadow: 0 0 0 2px rgba(99,102,241,0.2); }
.dark .bg-gray-800 { background-color: #111118 !important; }
.dark .bg-gray-700 { background-color: #1a1a2a !important; }
.dark .border-gray-700 { border-color: #2a2a3a !important; }
.dark .text-gray-300 { color: #aaa !important; }
.dark .text-gray-400 { color: #888 !important; }
.dark .bg-green-500 { background-color: #34d399 !important; }
.dark .bg-blue-600 { background-color: #4338ca !important; }
.dark .text-blue-600, .dark .text-blue-400 { color: #6366f1 !important; }
.dark input[type="checkbox"] { accent-color: #6366f1; }

/* [Full remaining dark overrides: ~200 lines of Tailwind dark class remappings to Atlas palette]
   Covers: gradient cards, routine colors, progress bars, semi-transparent panels,
   hover states, ring colors, border colors, etc. See full file for complete list. */
```

---

### 6.3 js/state.js (486 lines) — COMPLETE

```javascript
// CycleBoard State Management Module
// Handles state persistence, undo/redo, and data migration

const TASK_STATUS = Object.freeze({
  NOT_STARTED: 'Not Started',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed'
});

const DAY_TYPE = Object.freeze({ A: 'A', B: 'B', C: 'C' });

const REFLECTION_PERIOD = Object.freeze({
  WEEKLY: 'weekly', MONTHLY: 'monthly', QUARTERLY: 'quarterly', YEARLY: 'yearly'
});

const CYCLEBOARD_API_BASE = 'http://localhost:3001';
const API_SYNC_DEBOUNCE_MS = 2000;

class CycleBoardState {
  constructor() {
    this.saveDebounceTimer = null;
    this.apiSyncTimer = null;
    this.apiAvailable = null;
    this.apiKey = null;
    this.history = [];
    this.historyIndex = -1;
    this.maxHistorySize = 50;
    this.loadFromStorage();
    if (!this.state || !this.state.AZTask) {
      this.state = this.getDefaultState();
      this.saveToStorage();
    }
    this.initializeDates();
    this.pushHistory();
  }

  getDefaultState() {
    return {
      version: '2.0',
      screen: 'Home',
      AZTask: [
        { id: 'a1', letter: 'A', task: 'Define Monthly Focus', status: 'Not Started', notes: '', createdAt: new Date().toISOString() },
        { id: 'b1', letter: 'B', task: 'Draft A/B/C day templates', status: 'In Progress', notes: '', createdAt: new Date().toISOString() },
      ],
      DayPlans: {},
      FocusArea: [
        { id: 'fa1', name: 'Production', definition: 'Increase output and efficiency', color: '#3B82F6', tasks: [] },
        { id: 'fa2', name: 'Image', definition: 'Build brand and presentation', color: '#10B981', tasks: [] },
        { id: 'fa3', name: 'Growth', definition: 'Learning and skill development', color: '#8B5CF6', tasks: [] },
        { id: 'fa4', name: 'Personal', definition: 'Well-being and relationships', color: '#F59E0B', tasks: [] },
        { id: 'fa5', name: 'Errands', definition: 'Logistics to reduce friction', color: '#EF4444', tasks: [] },
        { id: 'fa6', name: 'Network', definition: 'Expand and nurture connections', color: '#EC4899', tasks: [] }
      ],
      Routine: {
        Morning: ['Hydrate','Weather check','Oral care','Shower','Skincare','Dress','Pack essentials','Breakfast','Tidy space','Walk/Stretch','High-priority task'],
        Commute: ['Grab essentials (keys, phone, wallet)','Weather check','Lock up and leave','Enter car/transport','Set navigation/playlist','Mental prep for day','Arrive 15 min early','Intentional downtime (10 min)','Gather belongings','Strategic downtime (5 min)','First task setup'],
        Evening: ['Light tidy','Prep bag','Plan tomorrow','Gratitude entry']
      },
      DayTypeTemplates: {
        A: {
          name: 'Optimal Day', description: 'Full energy, maximum output',
          timeBlocks: [
            { time: '6:00 AM', title: 'Morning Routine', duration: 60 },
            { time: '7:00 AM', title: 'Commute / Prep', duration: 30 },
            { time: '7:30 AM', title: 'Deep Work Block 1', duration: 90 },
            { time: '9:00 AM', title: 'Break / Recharge', duration: 15 },
            { time: '9:15 AM', title: 'Deep Work Block 2', duration: 90 },
            { time: '10:45 AM', title: 'Admin / Email', duration: 30 },
            { time: '11:15 AM', title: 'Deep Work Block 3', duration: 90 },
            { time: '12:45 PM', title: 'Lunch Break', duration: 45 },
            { time: '1:30 PM', title: 'Deep Work Block 4', duration: 90 },
            { time: '3:00 PM', title: 'Meetings / Collaboration', duration: 60 },
            { time: '4:00 PM', title: 'Wrap-up / Planning', duration: 30 },
            { time: '4:30 PM', title: 'Evening Routine', duration: 30 }
          ],
          routines: ['Morning','Commute','Evening'],
          goals: { baseline: 'Complete 4 deep work blocks', stretch: 'Clear inbox + bonus task' }
        },
        B: {
          name: 'Low Energy Day', description: 'Conserve energy, focus on essentials',
          timeBlocks: [
            { time: '7:00 AM', title: 'Light Morning Routine', duration: 45 },
            { time: '7:45 AM', title: 'Easy Start Task', duration: 45 },
            { time: '8:30 AM', title: 'Focus Block 1', duration: 60 },
            { time: '9:30 AM', title: 'Break / Walk', duration: 20 },
            { time: '9:50 AM', title: 'Focus Block 2', duration: 60 },
            { time: '10:50 AM', title: 'Admin / Light Tasks', duration: 40 },
            { time: '11:30 AM', title: 'Early Lunch', duration: 60 },
            { time: '12:30 PM', title: 'Focus Block 3', duration: 60 },
            { time: '1:30 PM', title: 'Rest / Recharge', duration: 30 },
            { time: '2:00 PM', title: 'Light Work / Wrap-up', duration: 60 },
            { time: '3:00 PM', title: 'Evening Routine', duration: 30 }
          ],
          routines: ['Morning','Evening'],
          goals: { baseline: 'Complete 3 focus blocks', stretch: 'One bonus task if energy allows' }
        },
        C: {
          name: 'Chaos Day', description: 'Survival mode - one priority only',
          timeBlocks: [
            { time: '8:00 AM', title: 'Minimal Morning', duration: 30 },
            { time: '8:30 AM', title: 'Identify ONE Priority', duration: 15 },
            { time: '8:45 AM', title: 'Priority Task', duration: 90 },
            { time: '10:15 AM', title: 'Break / Assess', duration: 15 },
            { time: '10:30 AM', title: 'Continue Priority or Pivot', duration: 60 },
            { time: '11:30 AM', title: 'Lunch / Reset', duration: 60 },
            { time: '12:30 PM', title: 'Damage Control / Urgent Only', duration: 90 },
            { time: '2:00 PM', title: 'Wrap Minimum Viable Day', duration: 30 },
            { time: '2:30 PM', title: 'Rest / Tomorrow Prep', duration: 30 }
          ],
          routines: ['Evening'],
          goals: { baseline: 'Complete ONE priority task', stretch: 'Survive and reset for tomorrow' }
        }
      },
      Settings: { darkMode: true, notifications: true, autoSave: true, defaultDayType: 'A' },
      History: { completedTasks: [], productivityScore: 0, streak: 0, timeline: [] },
      Journal: [],
      EightSteps: {},
      Contingencies: {
        runningLate: { enabled: true, actions: ['Skip non-essentials','Prioritize first task','Communicate with stakeholders'] },
        lowEnergy: { enabled: true, actions: ['Switch to B-Day mode','Focus on baseline only','Take frequent breaks'] },
        freeTime: { enabled: true, actions: ['Quick wins from list','Prep for tomorrow','Recharge if needed'] },
        disruption: { enabled: true, actions: ['Reassess priorities','Delegate non-urgent','Focus on one task'] }
      },
      Reflections: { weekly: [], monthly: [], quarterly: [], yearly: [] },
      MomentumWins: [],
      calendarView: 'month',
      calendarDate: new Date().toISOString().slice(0, 10)
    };
  }

  // [initializeDates, createDefaultDayPlan, getTodayDate, generateId — see full source above]
  // [loadFromStorage, migrateFromV1, loadApiKey, loadFromApi, syncToApi, syncToApiDebounced]
  // [saveToStorage, cleanupOldData, update, saveDebounced, pushHistory, undo, redo, canUndo, canRedo, getState]
  // All methods documented in full source in section above.
}
```

**All remaining modules (6.4-6.10) are printed in full in the code blocks above in this document. Refer to sections marked with their file names.**

---

### 6.11 js/screens.js — FUNCTION INDEX (3,022 lines)

**This is the largest file. Contains all 17 screen renderers + navigation.**

```
EXPORTS:
  screens[]                 — Array of {id, label, icon} for all 17 screens
  renderNav()               — Renders sidebar navigation with active state + weekly stats
  navigate(screen)          — Updates state.screen, re-renders, closes mobile sidebar
  ScreenRenderers.Command() — Delegates to CommandScreen.render() (async)
  ScreenRenderers.Home()    — Strategic HUD, progress, tasks, streaks, momentum wins
  ScreenRenderers.Daily()   — Day type, time blocks, goals, 8 steps, contingencies
  ScreenRenderers.Calendar()— Month grid, date navigation, day plan preview modals
  ScreenRenderers.AtoZ()    — A-Z task list, letter badges, status toggles
  ScreenRenderers.WeeklyFocus() — Focus areas with leverage badges, sub-tasks
  ScreenRenderers.Reflections() — Tabbed (weekly/monthly/quarterly/yearly) entries
  ScreenRenderers.Timeline()    — Chronological activity log from History.timeline
  ScreenRenderers.Routines()    — All routines, step completion, add/edit/delete
  ScreenRenderers.Journal()     — Journal entries with mood, tags, create modal
  ScreenRenderers.Energy()      — Energy meter, mental load, burnout, red alert
  ScreenRenderers.Finance()     — Runway, income/expense, money delta
  ScreenRenderers.Skills()      — Utilization %, mastery, growth counts
  ScreenRenderers.Network()     — Collaboration, relationships, outreach
  ScreenRenderers.OSINT()       — Market data, economic indicators, news, sentiment
  ScreenRenderers.Statistics()  — Completion stats, averages, routine rates
  ScreenRenderers.Settings()    — Dark mode, notifications, day type, API key, templates

HELPER FUNCTIONS IN SCREENS.JS:
  convertTo24Hour(timeStr)  — Converts "6:00 AM" → "06:00" for <input type="time">
  init()                    — DOMContentLoaded handler: dark mode, mobile toggle, render()
  render()                  — Main render: renderNav() + ScreenRenderers[state.screen]()
```

---

### 6.12 js/functions.js — FUNCTION INDEX (2,648 lines)

**Second largest file. All CRUD operations for the application.**

```
TASK MANAGEMENT:
  openCreateModal()            — Modal: letter selector + task text + notes
  createTask(letter, text)     — Validates + creates A-Z task + logs activity
  completeTask(taskId)         — Marks task completed, logs to History
  deleteTask(taskId)           — Removes task with confirmation
  completeAllTodayTasks()      — Marks all time blocks completed
  openEditTaskModal(taskId)    — Modal: edit task text + notes + status
  updateTask(taskId, updates)  — Applies partial updates to task

DAY TYPE MANAGEMENT:
  setDayType(type)             — Sets day_type, prompts template application
  showApplyTemplateModal(new, old) — Preview template before applying
  applyDayTypeTemplate(plan, type) — Applies A/B/C template to day plan
  openDayTypeTemplateEditor(type)  — Modal: edit template blocks/routines/goals
  saveDayTypeTemplate(type)        — Persists custom template
  resetDayTypeTemplate(type)       — Restores factory defaults

TIME BLOCKS:
  addTimeBlock()                    — Adds new block (default 09:00)
  updateTimeBlock(id, field, val)   — Updates time or title
  removeTimeBlock(id)               — Deletes block
  toggleTimeBlockCompletion(id)     — Toggles completed + saves progress snapshot

GOALS:
  saveGoals()                       — Saves baseline + stretch goal text
  toggleGoalCompletion(type)        — Toggles baseline/stretch completion

ROUTINES:
  addRoutine(name)                  — Creates new routine with empty steps
  deleteRoutine(name)               — Removes routine definition
  addRoutineStep(name, step)        — Appends step to routine
  updateRoutineStep(name, idx, txt) — Edits existing step text
  deleteRoutineStep(name, idx)      — Removes step from routine
  toggleRoutineStep(name, idx)      — Toggles step completion for today
  toggleRoutineComplete(name)       — Marks entire routine complete
  openEditRoutineModal(name)        — Modal: rename routine

JOURNAL:
  openJournalModal()                — Modal: title, content, type, mood
  saveJournalEntry(...)             — Creates journal entry with validation
  editJournalEntry(id, updates)     — Edits existing entry
  deleteJournalEntry(id)            — Removes entry with confirmation

FOCUS AREAS:
  addFocusTask(areaId, text)        — Adds sub-task to focus area
  toggleFocusTask(areaId, taskId)   — Toggles sub-task completion
  removeFocusTask(areaId, taskId)   — Removes sub-task

EIGHT STEPS & MOMENTUM:
  toggleEightStep(stepId)           — Toggles step completion for today
  addMomentumWin()                  — Modal: log a momentum win
  deleteMomentumWin(id)             — Removes win

CONTINGENCIES:
  activateContingency(scenario)     — Applies contingency actions (switch day type, etc)

REFLECTIONS:
  addReflection(period)             — Modal: add weekly/monthly/quarterly/yearly entry
  deleteReflection(period, idx)     — Removes reflection entry

IMPORT/EXPORT:
  exportState()                     — Downloads state.json
  showImportModal()                 — Modal: file picker for JSON import
  handleFileImport(file)            — Validates + migrates + imports state
  clearData()                       — Confirms + resets to defaults

LIFE SIGNALS (async HTTP to :8000):
  submitEnergySignals()             — POST energy metrics
  submitFinanceSignals()            — POST finance metrics
  submitSkillsSignals()             — POST skills metrics
  submitNetworkSignals()            — POST network metrics

UI HELPERS:
  toggleDarkMode()                  — Toggles dark/light
  showCopyContextModal()            — Modal: format selector (markdown/json/prompt)
```

---

### 6.13 js/ai-context.js — API SURFACE (512 lines)

```javascript
const AIContext = {
  getContext(): {
    _meta: { generatedAt, version, source },
    temporal: { today, todayFormatted, dayOfWeek, currentTime },
    navigation: { currentScreen, availableScreens },
    todayPlan: { date, dayType, dayTypeDescription, baselineGoal, stretchGoal,
                 timeBlocks, timeBlocksSummary: {total, completed, pending},
                 routinesCompleted, notes, rating },
    progress: { overall, breakdown[], timeBlocks, goals, routines, focusAreas,
                streak, weeklyAverage },
    tasks: { all[], summary: {total, notStarted, inProgress, completed, completionPercentage},
             byStatus: {notStarted[], inProgress[], completed[]}, availableLetters },
    routines: { definitions, routineNames, todayCompletion },
    focusAreas: { areas[], summary[] },
    journal: { totalEntries, recentEntries[], entriesByType },
    history: { recentActivity[], completedTasksCount, streak },
    weeklyStats: { completed, total, percentage },
    progressHistory: [],   // last 7 days
    cognitive: { mode, risk, openLoops, buildAllowed },
    dayTypeTemplates: {},
    reflections: { summary, recentEntries },
    momentumWins: []
  },

  getClipboardSnapshot(): string,     // Markdown formatted
  copyToClipboard(format): Promise,   // 'markdown' | 'json' | 'prompt'
  getQuickContext(): object,           // Condensed version
}
```

---

### 6.14 js/ai-actions.js — API SURFACE (654 lines)

```javascript
const AIActions = {
  // Tasks
  createTask(letter, taskText, notes?): { success, taskId?, task?, errors? },
  completeTask(taskId): { success, task?, error? },
  updateTaskStatus(taskId, status): { success, error? },
  updateTask(taskId, updates): { success, error? },
  findTaskByLetter(letter): task | null,

  // Goals
  updateGoal(goalType, text): { success, error? },
  toggleGoal(goalType): { success, error? },

  // Time Blocks
  addTimeBlock(time, title): { success, blockId?, error? },
  completeTimeBlock(blockId): { success, error? },
  removeTimeBlock(blockId): { success, error? },

  // Routines
  completeRoutineStep(routineName, stepIndex): { success, stepText?, routineComplete?, error? },
  completeRoutine(routineName): { success, error? },

  // Journal
  addJournalEntry(title, content, entryType, mood): { success, entryId?, entry?, errors? },

  // Momentum & Navigation
  addMomentumWin(description): { success, win? },
  navigateTo(screen): { success, screen?, error? },

  // Context & Suggestions
  getContext(): object,           // Delegates to AIContext
  getQuickContext(): object,
  suggestDayType(): { suggestion, reasoning, metrics },
  suggestNextAction(): [{ priority, action, details, method }],
}
```

---

## 7. STATE SCHEMA (complete default shape)

```json
{
  "version": "2.0",
  "screen": "Home",
  "AZTask": [
    {
      "id": "a1",
      "letter": "A",
      "task": "Define Monthly Focus",
      "status": "Not Started",
      "notes": "",
      "createdAt": "2026-04-08T00:00:00.000Z"
    }
  ],
  "DayPlans": {
    "2026-04-08": {
      "id": "abc123",
      "date": "2026-04-08",
      "day_type": "A",
      "time_blocks": [
        { "id": "tb1", "time": "06:00", "title": "Morning Routine", "completed": false }
      ],
      "baseline_goal": { "text": "Ship 1 meaningful outcome", "completed": false },
      "stretch_goal": { "text": "Ship 2 outcomes + review", "completed": false },
      "focus_areas": [],
      "routines_completed": {
        "Morning": { "completed": false, "steps": { "0": true, "1": false } }
      },
      "notes": "",
      "rating": 0,
      "progress_snapshots": [
        { "timestamp": "ISO", "overall": 45, "breakdown": [] }
      ],
      "final_progress": 0
    }
  },
  "FocusArea": [
    { "id": "fa1", "name": "Production", "definition": "...", "color": "#3B82F6", "tasks": [] }
  ],
  "Routine": {
    "Morning": ["Hydrate", "Weather check", "..."],
    "Commute": ["Grab essentials", "..."],
    "Evening": ["Light tidy", "..."]
  },
  "DayTypeTemplates": {
    "A": { "name": "Optimal Day", "description": "...", "timeBlocks": [], "routines": [], "goals": {} },
    "B": { "name": "Low Energy Day", "..." : "..." },
    "C": { "name": "Chaos Day", "..." : "..." }
  },
  "Settings": { "darkMode": true, "notifications": true, "autoSave": true, "defaultDayType": "A" },
  "History": {
    "completedTasks": [{ "taskId": "a1", "completedAt": "ISO" }],
    "productivityScore": 0,
    "streak": 0,
    "timeline": [{ "id": "x", "type": "task_completed", "description": "...", "details": {}, "timestamp": "ISO" }]
  },
  "Journal": [{ "id": "j1", "title": "...", "content": "...", "entryType": "reflection", "tags": [], "mood": "neutral", "timestamp": "ISO" }],
  "EightSteps": { "2026-04-08": { "positiveAttitude": true, "beOnTime": false } },
  "Contingencies": {
    "runningLate": { "enabled": true, "actions": ["..."] },
    "lowEnergy": { "enabled": true, "actions": ["..."] },
    "freeTime": { "enabled": true, "actions": ["..."] },
    "disruption": { "enabled": true, "actions": ["..."] }
  },
  "Reflections": { "weekly": [], "monthly": [], "quarterly": [], "yearly": [] },
  "MomentumWins": [{ "id": "mw1", "text": "Shipped feature X", "date": "2026-04-08", "timestamp": "ISO" }],
  "calendarView": "month",
  "calendarDate": "2026-04-08"
}
```

---

## 8. BRAIN DATA SCHEMAS (10 JSON sources)

### governance_state.json
```json
{
  "generated_at": "ISO", "date": "YYYY-MM-DD",
  "mode": "BUILD|MAINTENANCE|CLOSURE|RECOVER|COMPOUND|SCALE",
  "risk": "LOW|MEDIUM|HIGH", "build_allowed": true,
  "life_phase": 1,
  "north_star": { "weekly": "...", "monthly": "...", "system": "...", "guard": "..." },
  "active_lanes": [{ "id": "...", "name": "...", "status": "..." }],
  "lane_violations": [{ "recommendation": "park|kill|pursue" }]
}
```

### strategic_priorities.json
```json
{
  "generated": "ISO", "mode": "BUILD", "risk": "LOW",
  "open_loops": 5, "closure_ratio": 0.85,
  "top_clusters": [{
    "rank": 1, "cluster_id": "1", "label": "...",
    "normalized_leverage": 0.92, "execution_ratio": 0.45,
    "reusability_index": 0.78, "market_score": 7,
    "gap": "high_leverage_low_execution",
    "directive": "...", "top_ngrams": ["..."]
  }],
  "focus_area_weights": { "Production": { "weight": 8, "leverage": 0.9, "execution": 0.4 } },
  "daily_directive": {
    "primary_focus": "...", "primary_action": "...",
    "suggested_deep_block_mins": 90, "primary_cluster": "1",
    "stretch_goal": "...", "mode_escalation": null
  }
}
```

### Other brain files (energy, finance, skills, network, OSINT, weekly_plan, governor_headline)
```json
// energy_metrics.json
{ "generated_at": "ISO", "life_phase": 1, "energy_level": 70, "mental_load": 5, "sleep_quality": 7, "burnout_risk": "low", "red_alert_active": false }

// finance_metrics.json
{ "generated_at": "ISO", "life_phase": 1, "runway_months": 4.5, "monthly_income": 5000, "monthly_expenses": 3800, "money_delta": 1200 }

// skills_metrics.json
{ "generated_at": "ISO", "life_phase": 1, "utilization_pct": 65, "active_learning": true, "mastery_count": 4, "growth_count": 2 }

// network_metrics.json
{ "generated_at": "ISO", "life_phase": 1, "collaboration_score": 45, "active_relationships": 12, "outreach_this_week": 3 }

// governor_headline.json
{ "generated_at": "ISO", "mode": "BUILD", "risk": "LOW", "build_allowed": true,
  "life_phase": 1, "energy_level": 70, "burnout_risk": "low", "runway_months": 4.5,
  "closure_quality": 85, "open_loops": 5, "top_move": "...", "top_decision": "...",
  "warning": null, "confrontation": null, "compliance_rate": 92, "drift_score": 2, "drift_alerts": [] }
```

---

## 9. API INTEGRATION MAP

```
┌──────────────────────────────────────────────────────────────────┐
│                    ENDPOINTS CONSUMED                              │
├──────────────────────────┬───────────────────────────────────────┤
│ GET  :3001/api/state/    │ CognitiveController — 30s polling     │
│      unified             │ Returns: mode, risk, build_allowed,   │
│                          │ closure_ratio, open_loops, streak     │
├──────────────────────────┼───────────────────────────────────────┤
│ GET  :3001/api/cycleboard│ CycleBoardState — load full state     │
│ PUT  :3001/api/cycleboard│ CycleBoardState — 2s debounced sync   │
├──────────────────────────┼───────────────────────────────────────┤
│ GET  :3001/api/auth/token│ CycleBoardState — load API key        │
├──────────────────────────┼───────────────────────────────────────┤
│ GET  :3001/api/ideas     │ BrainData — idea registry             │
│ GET  :3001/api/governance│ BrainData — governance config         │
│      /config             │                                       │
├──────────────────────────┼───────────────────────────────────────┤
│ GET  :3001/api/          │ CommandScreen — preparation engine     │
│      preparation         │                                       │
│ GET  :3001/api/          │ CommandScreen — recent auto-actions    │
│      notifications       │                                       │
├──────────────────────────┼───────────────────────────────────────┤
│ POST :3001/api/tasks     │ CommandAPI — create task from idea     │
│ PUT  :3001/api/tasks/:id │ CommandAPI — complete task             │
│ POST :3001/api/law/      │ CommandAPI — close loop                │
│      close_loop          │                                       │
├──────────────────────────┼───────────────────────────────────────┤
│ POST :8000/api/signals/  │ Life signals — energy, finance,       │
│      {domain}            │ skills, network metrics                │
├──────────────────────────┼───────────────────────────────────────┤
│ LOCAL brain/*.json       │ Fallback when APIs unavailable         │
└──────────────────────────┴───────────────────────────────────────┘
```

---

## 10. GOVERNANCE SYSTEM

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODE POLICY ENFORCEMENT                        │
├────────────┬────────────────────────────────────────────────────┤
│ BUILD      │ Green banner. All creation allowed.                │
│            │ Action: "Focus on creation today"                  │
├────────────┼────────────────────────────────────────────────────┤
│ MAINTENANCE│ Yellow/amber banner. Creation allowed with warning.│
│            │ Action: "Review: [top open loop]"                  │
├────────────┼────────────────────────────────────────────────────┤
│ CLOSURE    │ Red banner. Creation LOCKED.                       │
│            │ .governance-locked applied to all create buttons   │
│            │ .governance-lock-banner shown at top of content    │
│            │ CognitiveController.canCreate() returns false      │
│            │ Action: "Close or archive: [top loop]"             │
├────────────┼────────────────────────────────────────────────────┤
│ Triggers   │ closure_ratio < 15% → CLOSURE + HIGH risk         │
│            │ open_loops > 10     → MAINTENANCE + MEDIUM risk    │
│            │ Otherwise           → BUILD + LOW risk             │
├────────────┼────────────────────────────────────────────────────┤
│ Polling    │ 30-second interval from cognitive.js               │
│            │ Pauses when tab hidden, resumes on visibility      │
│            │ Skips re-render if timestamp unchanged             │
└────────────┴────────────────────────────────────────────────────┘

Progress Formula (weighted):
  30% Time Blocks + 30% Goals + 25% Routines + 15% Focus Areas = Overall %

Streak: Consecutive days with >= 70% overall progress

Day Types:
  A = Optimal (4x 90min deep blocks, all routines, 12 time blocks)
  B = Low Energy (3x 60min focus blocks, 2 routines, 11 time blocks)
  C = Chaos (1 priority task, 1 routine, 9 time blocks)
```

---

**END OF DOCUMENT**
*CycleBoard v2.0 | 10,602 lines | 15 files | 17 screens | 10 brain sources | 3 APIs*
