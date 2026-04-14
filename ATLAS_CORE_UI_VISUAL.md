# ATLAS CORE — Visual UI System Map

> Pre Atlas v1.0 | 2026-02-22 | Dark Space Military Aesthetic

---

## THE FULL SYSTEM AT A GLANCE

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                           A T L A S   C O R E                                  ║
║                        atlas_boot.html (907 lines)                             ║
║                     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                             ║
║                                                                                ║
║  ┌─── DIRECTIVE BAR ──────────────────────────────────────────────────────────┐ ║
║  │ ◈ ATLAS    MODE     RISK    LOOPS   RATIO    ENFORCE   TODAY    STREAK    │ ║
║  │   CORE    ┌─────┐ ┌─────┐ ┌─────┐ ┌──────┐  ┌─────┐  ┌──────┐ ┌─────┐  │ ║
║  │  #8888aa  │BUILD│ │ LOW │ │  2  │ │ 0.85 │  │CLEAR│  │02-22 │ │  7  │  │ ║
║  │           └──┬──┘ └──┬──┘ └─────┘ └──────┘  └──┬──┘  └──────┘ └─────┘  │ ║
║  │              │       │                          │                         │ ║
║  │          ┌───┴───────┴──────────────────────────┴──────────────────────┐  │ ║
║  │          │  ⚠  PRIMARY ORDER                                          │  │ ║
║  │          │  "Complete delta-kernel integration tests"                  │  │ ║
║  │          │  ░░░░░░░░░░░░░░ red-tinted box ░░░░░░░░░░░░░░░░░░░░░░░░  │  │ ║
║  │          └────────────────────────────────────────────────────────────┘  │ ║
║  └─────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                ║
║  ┌────────────────────────────────────────────────┐ ┌────────────────────────┐ ║
║  │ ▪ CycleBoard  ▫ Control Panel                  │ │ TELEMETRY        [◀]  │ ║
║  ├────────────────────────────────────────────────┤ ├────────────────────────┤ ║
║  │                                                │ │                        │ ║
║  │            ╔══════════════════════╗             │ │  My Cognitive          │ ║
║  │            ║                      ║             │ │  Dashboard             │ ║
║  │            ║    CENTER VIEWPORT   ║             │ │  ──────────            │ ║
║  │            ║                      ║             │ │                        │ ║
║  │            ║   <iframe>           ║             │ │  Latest State:         │ ║
║  │            ║   cycleboard/        ║             │ │  ┌──────────────┐      │ ║
║  │            ║   index.html         ║             │ │  │ word freqs   │      │ ║
║  │            ║                      ║             │ │  │ in monospace │      │ ║
║  │            ║   ── OR ──           ║             │ │  └──────────────┘      │ ║
║  │            ║                      ║             │ │                        │ ║
║  │            ║   control_panel      ║             │ │  Open Loops (10):      │ ║
║  │            ║   .html              ║             │ │  ┌──────────────┐      │ ║
║  │            ║                      ║             │ │  │ • loop 1     │      │ ║
║  │            ╚══════════════════════╝             │ │  │ • loop 2     │      │ ║
║  │               flex: 1                          │ │  │ • loop 3     │      │ ║
║  │                                                │ │  └──────────────┘      │ ║
║  │                                                │ │                        │ ║
║  │                                                │ │  Completion Analytics  │ ║
║  │                                                │ │  Lifetime Anchors      │ ║
║  └────────────────────────────────────────────────┘ └────────────────────────┘ ║
║            flex: 1 (remaining)                              400px              ║
║                                                                                ║
║  ┌─── COMMAND STRIP ─────────────────────────────────────────────────────────┐ ║
║  │ [⚡ Acknowledge] [📦 Archive] [⚙ Control] [↻ Refresh]    [🖥 Desktop] ● ● │ ║
║  │   #ff8888          #aaaacc      #aaaacc     #aaaacc       #88ffaa     ○ ○ │ ║
║  │   red bg          blue-gray    blue-gray   blue-gray      green bg    │ │ │ ║
║  │                                                              Online───┘ │ │ ║
║  │                                                              Daemon─────┘ │ ║
║  └─────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  SHELL COLORS:
  ┌─────────────────────────────────────────────────┐
  │  Body Background    #0a0a0f  ████████████████   │
  │  Panel Background   #0f0f18  ████████████████   │
  │  Directive Bar      #1a1a2e  ████████████████   │
  │  Borders            #2a2a4a  ████████████████   │
  │  Text Primary       #e0e0e0  ████████████████   │
  │  Labels             #666680  ████████████████   │
  │  Title              #8888aa  ████████████████   │
  │  Tab Active         #aaaacc  ████████████████   │
  └─────────────────────────────────────────────────┘
```

---

## MODE STATE INDICATORS

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    MODE COLOR SYSTEM                             │
  │                                                                  │
  │  RECOVER     ●  #ff4444  ████  Red pulse                       │
  │  CLOSURE     ●  #ff4444  ████  Red solid                       │
  │  MAINTENANCE ●  #ffaa00  ████  Amber solid                     │
  │  BUILD       ●  #44ff88  ████  Green solid                     │
  │  COMPOUND    ●  #44ff88  ████  Green bright                    │
  │  SCALE       ●  #44ff88  ████  Green + glow                    │
  │                                                                  │
  │  ENFORCEMENT LEVELS:                                             │
  │  ┌────────────────────────────────────────────────┐             │
  │  │ 0  CLEAR      #44ff88  ████  All clear         │             │
  │  │ 1  WARN       #ffaa00  ████  Approaching limit  │             │
  │  │ 2  LOCKED     #ff8844  ████  Build restricted   │             │
  │  │ 3  HARD LOCK  #ff4444  ████  ◉ Pulsing alarm   │             │
  │  └────────────────────────────────────────────────┘             │
  │                                                                  │
  │  RISK LEVELS:                                                    │
  │  LOW       #44ff88  ████                                        │
  │  MODERATE  #ffaa00  ████                                        │
  │  HIGH      #ff4444  ████                                        │
  │  CRITICAL  #ff4444  ████  + pulsing                             │
  └──────────────────────────────────────────────────────────────────┘
```

---

## TAB 1: CYCLEBOARD (in-PACT Bullet Journal)

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║  cycleboard/index.html · 161L + 10 JS modules · Tailwind 3.4.1 ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║                                                                  ║
  ║  ┌── COGNITIVE DIRECTIVE BANNER (sticky, dynamic color) ──────┐ ║
  ║  │ 🧠 Cognitive Routing    MODE: BUILD  RISK: LOW  LOOPS: 2   │ ║
  ║  │                         ACTION: Focus on primary task ▲ ⚙  │ ║
  ║  └────────────────────────────────────────────────────────────┘ ║
  ║                                                                  ║
  ║  ┌──────────┐ ┌──────────────────────────────────────────────┐  ║
  ║  │ SIDEBAR  │ │          MAIN CONTENT                        │  ║
  ║  │ w: 256px │ │          flex: 1                             │  ║
  ║  │          │ │                                              │  ║
  ║  │ ┌──────┐ │ │  ┌────────────────────────────────────────┐  │  ║
  ║  │ │in-PACT│ │ │  │  📋 HOME SCREEN                       │  │  ║
  ║  │ │Self-  │ │ │  │                                        │  │  ║
  ║  │ │Sustain│ │ │  │  Today's Focus                         │  │  ║
  ║  │ │Bullet │ │ │  │  ┌──────────────────────────────┐      │  │  ║
  ║  │ │Journal│ │ │  │  │  Priority tasks for today     │      │  │  ║
  ║  │ └──────┘ │ │  │  │  ☐ Task 1                      │      │  │  ║
  ║  │          │ │  │  │  ☑ Task 2                      │      │  │  ║
  ║  │  ☰ NAV  │ │  │  │  ☐ Task 3                      │      │  │  ║
  ║  │ ┌──────┐ │ │  │  └──────────────────────────────┘      │  │  ║
  ║  │ │🏠Home│ │ │  │                                        │  │  ║
  ║  │ │📅Daily│ │ │  │  Quick Stats                           │  │  ║
  ║  │ │🔤 A-Z │ │ │  │  ┌─────────┐ ┌─────────┐ ┌────────┐  │  │  ║
  ║  │ │📝Jrnl │ │ │  │  │Completed│ │Pending  │ │Streak  │  │  │  ║
  ║  │ └──────┘ │ │  │  │  12/15   │ │   3     │ │  7 day │  │  │  ║
  ║  │          │ │  │  └─────────┘ └─────────┘ └────────┘  │  │  ║
  ║  │ ──────── │ │  │                                        │  │  ║
  ║  │ Weekly   │ │  └────────────────────────────────────────┘  │  ║
  ║  │ Progress │ │                                              │  ║
  ║  │ ████░░ 80%│ │                                              │  ║
  ║  │          │ │                                              │  ║
  ║  │ ──────── │ │  ── OR: DAILY SCREEN ──                     │  ║
  ║  │ [🤖 AI ] │ │  ┌────────────────────────────────────────┐  │  ║
  ║  │ [📤 Exp] │ │  │  📅 February 22, 2026                  │  │  ║
  ║  │ [📥 Imp] │ │  │  Morning │ Afternoon │ Evening          │  │  ║
  ║  │ [🗑 Clr] │ │  │  ☐ ───────────────────────────         │  │  ║
  ║  │          │ │  │  ☐ ───────────────────────────         │  │  ║
  ║  └──────────┘ │  └────────────────────────────────────────┘  │  ║
  ║               └──────────────────────────────────────────────┘  ║
  ║                                                                  ║
  ║  ┌── MOBILE BOTTOM NAV (hidden on desktop) ──────────────────┐  ║
  ║  │  [🏠 Home]  [📅 Daily]  [🔤 A-Z]  [📝 Journal]          │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ╚══════════════════════════════════════════════════════════════════╝

  LIGHT MODE                      DARK MODE (toggle)
  ┌──────────────────┐            ┌──────────────────┐
  │  bg     #f8fafc  │            │  bg     #111827  │
  │  card   #ffffff  │            │  card   #1f2937  │
  │  text   #1e293b  │            │  text   #f9fafb  │
  │  border #e2e8f0  │            │  border #374151  │
  │  accent #667eea  │            │  accent #667eea  │
  └──────────────────┘            └──────────────────┘

  ★ ONLY file with ARIA accessibility (role, aria-label, aria-live)
  ★ ONLY file with semantic HTML (<header>, <nav>, <main>, <aside>)
```

---

## TAB 2: CONTROL PANEL

```
  ╔═══════════════════════════════════════════════════════════╗
  ║  control_panel.html · 201L · Tailwind 3.4.1 · bg:#111827 ║
  ╠═══════════════════════════════════════════════════════════╣
  ║                                                           ║
  ║       🧠  Cognitive Control Panel                         ║
  ║       Master controls for your personal OS                ║
  ║                                                           ║
  ║  ┌─── SYSTEM STATUS ──── bg:#1f2937 ──────────────────┐  ║
  ║  │                                                     │  ║
  ║  │   ┌─────────────┐  ┌─────────────┐                 │  ║
  ║  │   │ Current Mode│  │ Risk Level  │   bg: #374151   │  ║
  ║  │   │   BUILD     │  │    LOW      │                  │  ║
  ║  │   │  #44ff88    │  │   #44ff88   │                  │  ║
  ║  │   └─────────────┘  └─────────────┘                  │  ║
  ║  │   ┌─────────────┐  ┌─────────────┐                 │  ║
  ║  │   │ Open Loops  │  │Closure Ratio│                  │  ║
  ║  │   │     2       │  │   0.85      │                  │  ║
  ║  │   └─────────────┘  └─────────────┘                  │  ║
  ║  └─────────────────────────────────────────────────────┘  ║
  ║                                                           ║
  ║  ┌─── PRIMARY ACTION ──── border: red/amber/green ────┐  ║
  ║  │ ⚠ Required Action                                   │  ║
  ║  │ "Close or archive: <highest priority loop>"         │  ║
  ║  │                                                     │  ║
  ║  │ [ 🎯 I'll Do This Now ]  bg: mode-color-600        │  ║
  ║  └─────────────────────────────────────────────────────┘  ║
  ║                                                           ║
  ║  ┌─── OPEN LOOPS ─────────────────────────────────────┐  ║
  ║  │ • delta-kernel test suite         [ Close ✓ ]      │  ║
  ║  │ • cognitive map refactor          [ Close ✓ ]      │  ║
  ║  └─────────────────────────────────────────────────────┘  ║
  ║                                                           ║
  ║  ┌─── QUICK ACTIONS ──── 2x2 grid ───────────────────┐  ║
  ║  │  ┌──────────────┐  ┌──────────────┐               │  ║
  ║  │  │ ↻ Refresh    │  │ 📊 Dashboard │               │  ║
  ║  │  │  bg:#2563eb  │  │  bg:#9333ea  │               │  ║
  ║  │  └──────────────┘  └──────────────┘               │  ║
  ║  │  ┌──────────────┐  ┌──────────────┐               │  ║
  ║  │  │ ✓ Close Loop │  │ 📋 CycleBoard│               │  ║
  ║  │  │  bg:#16a34a  │  │  bg:#4f46e5  │               │  ║
  ║  │  └──────────────┘  └──────────────┘               │  ║
  ║  └─────────────────────────────────────────────────────┘  ║
  ║                                                           ║
  ║        Last updated: 2026-02-22 14:30:00                  ║
  ╚═══════════════════════════════════════════════════════════╝
```

---

## IDEA INTELLIGENCE DASHBOARD

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║  idea_dashboard.html · 493L · Tailwind 3.4.1 · bg: near-black  ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║                                                                  ║
  ║  ┌── HEADER (sticky) ────────────────────────────────────────┐  ║
  ║  │  🧠 Idea Intelligence              [🔍 Search...] [↻]    │  ║
  ║  │  527 ideas | Generated 2026-02-22                          │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ║                                                                  ║
  ║  ┌── STATS BAR (5 columns) ──────────────────────────────────┐  ║
  ║  │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │  ║
  ║  │ │ Total  │ │Execute │ │Next Up │ │Backlog │ │Archive │  │  ║
  ║  │ │  527   │ │   42   │ │   89   │ │  312   │ │   84   │  │  ║
  ║  │ │ purple │ │ green  │ │  blue  │ │ amber  │ │  gray  │  │  ║
  ║  │ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ║                                                                  ║
  ║  ┌── TABS ───────────────────────────────────────────────────┐  ║
  ║  │ [Overview] [Execute] [Next Up] [Clusters] [Time] [All] [BL]│ ║
  ║  │  ████████                                                   │  ║
  ║  │  purple                     inactive: #9ca3af               │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ║                                                                  ║
  ║  ┌── OVERVIEW (2x2 grid) ────────────────────────────────────┐  ║
  ║  │ ┌─────────────────────┐  ┌─────────────────────┐         │  ║
  ║  │ │ Top 5 Priority      │  │ Gateway Ideas        │         │  ║
  ║  │ │ purple-300 header   │  │ blue-300 header      │         │  ║
  ║  │ │ • Idea A   ██ 9.2  │  │ • Gateway 1          │         │  ║
  ║  │ │ • Idea B   ██ 8.7  │  │ • Gateway 2          │         │  ║
  ║  │ │ • Idea C   ██ 8.1  │  │ • Gateway 3          │         │  ║
  ║  │ └─────────────────────┘  └─────────────────────┘         │  ║
  ║  │ ┌─────────────────────┐  ┌─────────────────────┐         │  ║
  ║  │ │ Categories          │  │ Status Breakdown     │         │  ║
  ║  │ │ yellow-300 header   │  │ green-300 header     │         │  ║
  ║  │ │ Tech  ████████░ 67% │  │ idea    ████░░ #8b5cf6│        │  ║
  ║  │ │ Biz   █████░░░ 45% │  │ started ███░░░ #3b82f6│        │  ║
  ║  │ │ Life  ███░░░░░ 28% │  │ stalled ██░░░░ #f59e0b│        │  ║
  ║  │ └─────────────────────┘  └─────────────────────┘         │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ║                                                                  ║
  ║  ┌── DETAIL MODAL (on click) ── max-w-2xl ──────────────────┐  ║
  ║  │  ┌────────────────────────────────────────┐               │  ║
  ║  │  │ Idea Title                        [X]  │               │  ║
  ║  │  │ ┌──────┐ ┌──────┐ ┌──────┐            │               │  ║
  ║  │  │ │ tag1 │ │ tag2 │ │ tag3 │  Score: 9.2│               │  ║
  ║  │  │ └──────┘ └──────┘ └──────┘            │               │  ║
  ║  │  │                                        │               │  ║
  ║  │  │ Timeline:                              │               │  ║
  ║  │  │ ● Created 2025-06-15                   │               │  ║
  ║  │  │ │                                      │               │  ║
  ║  │  │ ● Updated 2025-12-01                   │               │  ║
  ║  │  └────────────────────────────────────────┘               │  ║
  ║  └────────────────────────────────────────────────────────────┘  ║
  ╚══════════════════════════════════════════════════════════════════╝
```

---

## DELTA-KERNEL UI PAIR

```
  ╔═══════════════════════════════════╗  ╔═══════════════════════════════════╗
  ║  control.html · 96L · Dark Term   ║  ║  timeline.html · 289L · Dark Term ║
  ╠═══════════════════════════════════╣  ╠═══════════════════════════════════╣
  ║                                   ║  ║                                   ║
  ║  Pre-Atlas Control Panel          ║  ║  Pre-Atlas Timeline               ║
  ║  ─────────────────────            ║  ║  ─────────────────                 ║
  ║                                   ║  ║                                   ║
  ║  ┌─ System State ──────────┐     ║  ║  ┌─ Filters ─────────────────┐   ║
  ║  │ Mode: BUILD             │     ║  ║  │ Type: [All ▼]  Limit: [50]│   ║
  ║  │ Build Allowed: true     │     ║  ║  └────────────────────────────┘   ║
  ║  │ Closure Ratio: 0.85    │     ║  ║                                   ║
  ║  │ Capacity: 3/5          │     ║  ║  ┌─ Stats ─────────────────────┐  ║
  ║  └─────────────────────────┘     ║  ║  │ Total: 1,247  Today: 23    │  ║
  ║                                   ║  ║  └────────────────────────────┘  ║
  ║  ┌─ Active Jobs ───────────┐     ║  ║                                   ║
  ║  │ #1 test-suite  TTL: 45m │     ║  ║  ┌─ Events ───────────────────┐  ║
  ║  │ #2 refactor    TTL: 20m │     ║  ║  │ 14:30 MODE_CHANGED  green  │  ║
  ║  └─────────────────────────┘     ║  ║  │ 14:15 WORK_APPROVED blue   │  ║
  ║                                   ║  ║  │ 13:45 LOOP_CLOSED  green  │  ║
  ║  ┌─ Queue ─────────────────┐     ║  ║  │ 13:30 WORK_DENIED   red   │  ║
  ║  │ (empty)                 │     ║  ║  │ 13:00 LAW_VIOLATED  red   │  ║
  ║  └─────────────────────────┘     ║  ║  │ 12:30 WORK_APPROVED blue   │  ║
  ║                                   ║  ║  └────────────────────────────┘  ║
  ║  ┌─ Recent Completions ────┐     ║  ║                                   ║
  ║  │ ✓ audit-fix  12:30     │     ║  ║  Polls: /api/timeline      10s   ║
  ║  │ ✓ schema     11:45     │     ║  ║         /api/timeline/stats 10s   ║
  ║  └─────────────────────────┘     ║  ║                                   ║
  ║                                   ║  ║  [→ Control Panel]               ║
  ║  Polls: /api/work/status  5s     ║  ║                                   ║
  ╚═══════════════════════════════════╝  ╚═══════════════════════════════════╝
                    ↕ linked ↕
```

---

## HARDWARE TEST PAGES (Green Terminal Cluster)

```
  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
  │ camera-live-test.html │ │ audio-live-test.html  │ │ voice-live-test.html  │
  │ 444L                  │ │ 410L                  │ │ 655L                  │
  ├───────────────────────┤ ├───────────────────────┤ ├───────────────────────┤
  │                       │ │                       │ │                       │
  │  ░░░░░░░░░░░░░░░░░░  │ │  Band 1: ████████░░  │ │  ┌── Waveform ─────┐ │
  │  ░░░░ CAMERA ░░░░░░  │ │  Band 2: ██████░░░░  │ │  │ ∿∿∿∿∿∿∿∿∿∿∿∿∿  │ │
  │  ░░░░ 16x12  ░░░░░░  │ │  Band 3: ████░░░░░░  │ │  │ ∿∿∿∿∿∿∿∿∿∿∿∿∿  │ │
  │  ░░░░ TILES  ░░░░░░  │ │  Band 4: ██░░░░░░░░  │ │  └─────────────────┘ │
  │  ░░░░░░░░░░░░░░░░░░  │ │                       │ │                       │
  │  ░░░░░░░░░░░░░░░░░░  │ │  Sender  ──→  Recv   │ │  Codec: LPC-14       │
  │                       │ │  [wave]       [wave]  │ │  Rate:  3200 bps     │
  │  Baseline │ Delta     │ │                       │ │  BW:    ████░░ 67%   │
  │  [grid]   │ [grid]    │ │  Delta sync stats     │ │                       │
  │                       │ │                       │ │  [3200][1300][700C]   │
  │  WebRTC getUserMedia  │ │  Web Audio API        │ │  Pure JS LPC impl    │
  │  ES module script     │ │                       │ │                       │
  ├───────────────────────┤ ├───────────────────────┤ ├───────────────────────┤
  │ bg: #000  text: #0f0  │ │ bg: #000  text: #0f0  │ │ bg: #000  text: #0f0  │
  │ Green-on-black term   │ │ Green-on-black term   │ │ Green-on-black term   │
  └───────────────────────┘ └───────────────────────┘ └───────────────────────┘
```

---

## DESKTOP OVERLAY: WEB OS SIMULATOR

```
  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  web-os-simulator.html · 3,442L · Self-Contained · 3 Themes           ║
  ╠══════════════════════════════════════════════════════════════════════════╣
  ║                                                                        ║
  ║   BOOT SEQUENCE:  ████████████████████████░░░░  Loading Web OS...     ║
  ║   LOGIN SCREEN:   gradient #667eea → #764ba2                          ║
  ║                    [ avatar ] [ password ] [ Sign In ]                 ║
  ║                                                                        ║
  ║   ┌── DESKTOP (calc(100vh - 40px)) ─────────────────────────────────┐ ║
  ║   │                                                                  │ ║
  ║   │   🗂         📝         🖩         💻         🎨                │ ║
  ║   │  Files    Notepad     Calc     Terminal    Paint               │ ║
  ║   │                                                                  │ ║
  ║   │      ┌──── WINDOW (draggable, resizable) ────────────────┐      │ ║
  ║   │      │ 📝 Notepad                         [_] [□] [✕]    │      │ ║
  ║   │      ├── File │ Edit │ View ──────────────────────────────┤      │ ║
  ║   │      │                                                    │      │ ║
  ║   │      │  Hello world...                                    │      │ ║
  ║   │      │  █                                                 │      │ ║
  ║   │      │                                                    │      │ ║
  ║   │      │                                                    │      │ ║
  ║   │      ├────────────────────────────────────────────────────┤      │ ║
  ║   │      │ Ln 1, Col 14                                    ◢ │      │ ║
  ║   │      └────────────────────────────────────────────────────┘      │ ║
  ║   │                                                                  │ ║
  ║   └──────────────────────────────────────────────────────────────────┘ ║
  ║   ┌── TASKBAR (40px) ───────────────────────────────────────────────┐ ║
  ║   │ [▶Start]  │ [📝 Notepad]                      🔊 🔔  2:30 PM │ ║
  ║   └─────────────────────────────────────────────────────────────────┘ ║
  ║                                                                        ║
  ║   START MENU (280px):        3 THEMES:                                ║
  ║   ┌────────────────┐        ┌──────────────────────────────────────┐  ║
  ║   │ 🌐 Web OS      │        │                                      │  ║
  ║   ├────────────────┤        │  WIN 95         XP           DARK    │  ║
  ║   │ 📁 File Explr  │        │  ┌──────┐    ┌──────┐    ┌──────┐  │  ║
  ║   │ 📝 Notepad     │        │  │ ████ │    │ ████ │    │ ████ │  │  ║
  ║   │ 🖩  Calculator  │        │  │ desk │    │ desk │    │ desk │  │  ║
  ║   │ 💻 Terminal    │        │  │#008080│    │#3a6ea5│    │#1a1a2e│  │  ║
  ║   │ 🌍 Browser     │        │  ├──────┤    ├──────┤    ├──────┤  │  ║
  ║   │ 🎨 Paint       │        │  │taskbr│    │taskbr│    │taskbr│  │  ║
  ║   │ 🎵 Music       │        │  │#c0c0c0│    │#3168d5│    │#16213e│  │  ║
  ║   ├────────────────┤        │  │ gray │    │ blue │    │ navy │  │  ║
  ║   │ 💣 Minesweeper │        │  └──────┘    └──────┘    └──────┘  │  ║
  ║   │ 🃏 Solitaire   │        │                                      │  ║
  ║   ├────────────────┤        │  title:      title:      title:     │  ║
  ║   │ ⚙ Settings     │        │  #000080     gradient    #0f3460    │  ║
  ║   │ 📊 Task Mgr    │        │  navy        blue        dark navy  │  ║
  ║   ├────────────────┤        │                                      │  ║
  ║   │ ⏻  Shut Down   │        │  accent:     accent:     accent:    │  ║
  ║   └────────────────┘        │  #008080     #39b54a     #e94560    │  ║
  ║                              │  teal        green       coral      │  ║
  ║                              └──────────────────────────────────────┘  ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  [🔴 Exit Desktop] ← fixed top-right, returns to Atlas Core shell
```

---

## GENERATED VISUALIZATIONS (Python Pipeline)

```
  ╔════════════════════════════════════════════════════════════════════════╗
  ║  COGNITIVE ATLAS (atlas_template.html → cognitive_atlas.html)        ║
  ║  612L template · Plotly 2.27.0 + Sigma.js 2.4.0 · GITIGNORED       ║
  ╠════════════════════════════════════════════════════════════════════════╣
  ║                                                                      ║
  ║  ┌── 5 LAYER BUTTONS ────────────────────────────────────────────┐  ║
  ║  │  [Cluster] [Role] [Time] [Conversation] [Leverage]            │  ║
  ║  │  [Analytics Mode ◉]  [Graph Mode ○]                          │  ║
  ║  └──────────────────────────────────────────────────────────────┘  ║
  ║                                                                      ║
  ║  ┌── PLOTLY SCATTER / SIGMA GRAPH ──────────────────────────────┐  ║
  ║  │                                                              │  ║
  ║  │        ·  · ·                    ·                           │  ║
  ║  │      ·  ·· ·  ·              · ·  ·                         │  ║
  ║  │    ·  CLUSTER 1  ·       · CLUSTER 3 ·                     │  ║
  ║  │      ·  ·· ·  ·              · ·  ·                         │  ║
  ║  │        ·  · ·          ·  · ·                               │  ║
  ║  │                      ·  ·· ·  ·                             │  ║
  ║  │                    · CLUSTER 2  ·                           │  ║
  ║  │                      ·  ·· ·  ·                             │  ║
  ║  │                        ·  · ·                               │  ║
  ║  └──────────────────────────────────────────────────────────────┘  ║
  ║                                                                      ║
  ║  ┌── SIDE PANELS ──────────────────────────────────────────────┐  ║
  ║  │  Leverage Rankings │ Cluster Inspector │ Cognitive ROI      │  ║
  ║  │  Asset Vectors     │                                        │  ║
  ║  └──────────────────────────────────────────────────────────────┘  ║
  ╚════════════════════════════════════════════════════════════════════════╝

  ╔════════════════════════════════════════════════════════════════════════╗
  ║  COGNITIVE MAP (cognitive_map.html) · 218L/378KB · GITIGNORED        ║
  ╠════════════════════════════════════════════════════════════════════════╣
  ║                                                                      ║
  ║  ┌────────────────────┐  ┌────────────────────┐                     ║
  ║  │  PCA 2D Topology   │  │ Similarity Network │                     ║
  ║  │  (Plotly scatter)  │  │ (Plotly network)   │                     ║
  ║  └────────────────────┘  └────────────────────┘                     ║
  ║  ┌────────────────────┐  ┌────────────────────┐                     ║
  ║  │  Temporal Drift    │  │ Recurrence Scanner │                     ║
  ║  │  (Plotly line)     │  │ (Plotly heatmap)   │                     ║
  ║  └────────────────────┘  └────────────────────┘                     ║
  ╚════════════════════════════════════════════════════════════════════════╝
```

---

## NAVIGATION FLOW MAP

```
                              USER OPENS
                                  │
                                  ▼
                    ╔═════════════════════════╗
                    ║     atlas_boot.html     ║
                    ║      ATLAS CORE         ║
                    ╚════════════╤════════════╝
                                 │
              ┌──────────┬───────┼───────┬──────────┐
              │          │       │       │          │
              ▼          ▼       ▼       ▼          ▼
         ┌─────────┐ ┌──────┐ ┌────┐ ┌──────┐ ┌────────┐
         │Cycle    │ │Ctrl  │ │Dash│ │WebOS │ │ API    │
         │Board    │ │Panel │ │    │ │      │ │:3001   │
         │ iframe  │ │iframe│ │ R  │ │fullsc│ │        │
         └────┬────┘ └──┬───┘ └────┘ └──────┘ └───┬────┘
              │         │                          │
              │    ┌────┴────┐               ┌─────┴──────┐
              │    │         │               │            │
              │    ▼         ▼               ▼            ▼
              │  ┌────┐  ┌──────┐      ┌─────────┐ ┌──────────┐
              │  │Dash│  │Cycle │      │control  │ │timeline  │
              │  │open│  │Board │      │.html    │ │.html     │
              │  └────┘  │open  │      │(dk/ui)  │ │(dk/ui)   │
              │          └──────┘      └────┬────┘ └─────┬────┘
              │                             │            │
              │                             └──────┬─────┘
              ▼                                    │
         ┌─────────┐                               ▼
         │ctrl     │                        ┌────────────┐
         │panel    │                        │ Linked     │
         │open via │                        │ to each    │
         │cogntv.js│                        │ other      │
         └─────────┘                        └────────────┘


  STANDALONE (no parent navigation):
  ┌──────────────────┐  ┌───────────────┐  ┌───────────────┐
  │ idea_dashboard   │  │ pattern-map   │  │ hardware      │
  │ .html            │  │ .html         │  │ tests (×3)    │
  │ ORPHANED         │  │ ORPHANED      │  │ ORPHANED      │
  └──────────────────┘  └───────────────┘  └───────────────┘

  FRAMEWORK SPAs (served by dev servers):
  ┌──────────────────────┐  ┌──────────────────────┐
  │ delta-kernel/web/    │  │ blueprint-generator/  │
  │ index.html           │  │ out/index.html        │
  │ Vite :5173           │  │ Next.js :3000         │
  └──────────────────────┘  └──────────────────────┘
```

---

## DATA FLOW VISUAL

```
  ╔═══════════════════╗          ╔═══════════════════╗
  ║  PYTHON PIPELINE  ║          ║  DELTA-KERNEL API  ║
  ║  (cognitive-sensor)║          ║  localhost:3001    ║
  ╚════════╤══════════╝          ╚═════════╤═════════╝
           │                               │
    ┌──────┴──────┐                 ┌──────┴──────────────┐
    │ writes JSON │                 │  REST endpoints     │
    │ to disk     │                 │                     │
    ▼             ▼                 ▼          ▼          ▼
┌────────┐  ┌──────────┐    ┌──────────┐ ┌────────┐ ┌────────┐
│cogntvie│  │idea_     │    │/api/state│ │/api/   │ │/api/   │
│_state  │  │registry  │    │/unified  │ │work/*  │ │timeline│
│.json   │  │.json     │    │/api/law/*│ │        │ │        │
└───┬────┘  └────┬─────┘    │/api/     │ └───┬────┘ └───┬────┘
    │            │           │daemon    │     │          │
    │            │           └────┬─────┘     │          │
    ▼            ▼                │           ▼          ▼
┌────────┐ ┌──────────┐    ┌─────┴─────┐ ┌──────┐ ┌────────┐
│control │ │idea_dash-│    │atlas_boot │ │contrl│ │timeline│
│_panel  │ │board     │    │.html      │ │.html │ │.html   │
│.html   │ │.html     │    │(30s poll) │ │(5s)  │ │(10s)   │
└───┬────┘ └──────────┘    └───────────┘ └──────┘ └────────┘
    │
    ▼
┌────────┐
│cycle   │
│board/  │
│index   │
│.html   │
│(via    │
│cogntv  │
│.js)    │
└────────┘

  localStorage (browser-only, no server):
  ┌────────────────┐     ┌────────────────┐
  │ CycleBoard     │     │ WebOS          │
  │ cycleboard-    │     │ webos-         │
  │  state         │     │  filesystem    │
  │  milestones-*  │     │  username      │
  │  export-count  │     │  theme         │
  │  last-export   │     │  wallpaper     │
  │  last-import   │     │  sound         │
  └────────────────┘     └────────────────┘
```

---

## TECHNOLOGY STACK VISUAL

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    FRONTEND TECHNOLOGY MAP                      │
  │                                                                 │
  │  ┌─────────── TAILWIND + FONT AWESOME ──────────────────────┐  │
  │  │                                                           │  │
  │  │   cycleboard/         control_panel      idea_dashboard   │  │
  │  │   index.html          .html              .html            │  │
  │  │   ┌─────────┐        ┌─────────┐        ┌─────────┐     │  │
  │  │   │ TW 3.4.1│        │ TW 3.4.1│        │ TW 3.4.1│     │  │
  │  │   │ FA 6.4.0│        │ FA 6.4.0│        │ FA 6.4.0│     │  │
  │  │   │ +custom │        │ inline  │        │ inline  │     │  │
  │  │   │  CSS    │        │ script  │        │ script  │     │  │
  │  │   │ +10 JS  │        │         │        │         │     │  │
  │  │   │ modules │        │         │        │         │     │  │
  │  │   └─────────┘        └─────────┘        └─────────┘     │  │
  │  └───────────────────────────────────────────────────────────┘  │
  │                                                                 │
  │  ┌─────────── PLOTLY + SIGMA.JS ────────────────────────────┐  │
  │  │                                                           │  │
  │  │   atlas_template      cognitive_atlas    cognitive_map    │  │
  │  │   ┌─────────┐        ┌─────────┐       ┌─────────┐     │  │
  │  │   │Plotly   │        │(generated│       │Plotly   │     │  │
  │  │   │2.27.0   │        │ from     │       │2.27.0   │     │  │
  │  │   │Sigma 2.4│        │ template)│       │         │     │  │
  │  │   │Graph    │        │         │       │ 378KB!  │     │  │
  │  │   │0.25.4   │        │         │       │         │     │  │
  │  │   └─────────┘        └─────────┘       └─────────┘     │  │
  │  └───────────────────────────────────────────────────────────┘  │
  │                                                                 │
  │  ┌─── VANILLA (Dark Terminal) ─┐  ┌─── VANILLA (Green) ──────┐ │
  │  │ atlas_boot   907L           │  │ camera-test   444L        │ │
  │  │ control      96L            │  │ audio-test    410L        │ │
  │  │ timeline     289L           │  │ voice-test    655L        │ │
  │  │ dashboard    58L            │  │ #000 bg / #0f0 text      │ │
  │  │ #0a0a0f bg / #e0e0e0 text  │  │ WebRTC / Web Audio       │ │
  │  └─────────────────────────────┘  └───────────────────────────┘ │
  │                                                                 │
  │  ┌─── FRAMEWORK SPAs ────────────────────────────────────────┐  │
  │  │  Vite + React + TS          Next.js SSG                   │  │
  │  │  delta-kernel/web/          blueprint-generator/out/      │  │
  │  │  :5173                      :3000                         │  │
  │  └───────────────────────────────────────────────────────────┘  │
  │                                                                 │
  │  ┌─── SELF-CONTAINED MEGA-FILES ─────────────────────────────┐  │
  │  │  web-os-simulator  3,442L  (CSS vars, 3 themes, 12 apps) │  │
  │  │  pattern-map        1,167L  (standalone report)           │  │
  │  └───────────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────────┘
```

---

## SYSTEM HEALTH LEGEND

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║                     SYSTEM STATUS LEGEND                        ║
  ║                                                                  ║
  ║  CONNECTION STATUS:                                              ║
  ║  ● Online     #44ff88 (green, pulsing)   API responding         ║
  ║  ● Offline    #ff4444 (red, static)      API unreachable        ║
  ║  ● Working    #ffaa00 (amber)            Daemon running job     ║
  ║                                                                  ║
  ║  NOTIFICATION TYPES:                                             ║
  ║  ┌──────────────────────────┐                                   ║
  ║  │ ✓  Success   green      │  Action completed                  ║
  ║  │ ✕  Error     red        │  Action failed                     ║
  ║  │ ℹ  Info      blue-gray  │  System information                ║
  ║  └──────────────────────────┘                                   ║
  ║                                                                  ║
  ║  POLLING INTERVALS:                                              ║
  ║  atlas_boot.html    → /api/state/unified     every 30s          ║
  ║  atlas_boot.html    → /api/daemon/status     every 30s          ║
  ║  control_panel.html → cognitive_state.json   every 30s          ║
  ║  control.html       → /api/work/status       every  5s          ║
  ║  timeline.html      → /api/timeline          every 10s          ║
  ║                                                                  ║
  ║  FILE SIZES:                                                     ║
  ║  ████████████████████████████████████  web-os-sim    3,442L     ║
  ║  ██████████████████████████████        pattern-map   1,167L     ║
  ║  ████████████████████                  atlas_boot      907L     ║
  ║  █████████████████                     voice-test      655L     ║
  ║  ████████████████                      atlas_template  612L     ║
  ║  ██████████████                        idea_dashboard  493L     ║
  ║  █████████████                         camera-test     444L     ║
  ║  ████████████                          audio-test      410L     ║
  ║  ████████                              timeline        289L     ║
  ║  ██████                                control_panel   201L     ║
  ║  █████                                 cycleboard      161L     ║
  ║  ███                                   control          96L     ║
  ║  ██                                    dashboard        58L     ║
  ║  █                                     vite index       13L     ║
  ╚══════════════════════════════════════════════════════════════════╝
```

---

*20 HTML files | 3-layer iframe architecture | 7 technology clusters | 2 data paths (API + JSON) | 1 file with accessibility*
