# Pre Atlas - System Map & Specification

**Version:** 1.1
**Date:** 2026-01-09
**Total Size:** ~306 MB (excluding node_modules)
**Phase History:** See `PHASE_ROADMAP.md` for complete implementation timeline (Phase 1 → 5B)

---

## Overview

Pre Atlas is a personal operating system stack consisting of 5 interconnected projects that form a behavioral governance and productivity system. The architecture flows from low-level state synchronization up through cognitive analysis to interface enforcement.

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRE ATLAS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ .delta-fabric│───▶│delta-kernel  │───▶│cognitive-sensor  │  │
│  │  (state sync)│    │  (OS engine) │    │ (behavior gov.)  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                                                  │               │
│                                                  ▼               │
│  ┌──────────────┐                      ┌──────────────────┐     │
│  │  webos-333   │                      │    Interfaces    │     │
│  │  (Web OS UI) │                      │ CycleBoard/Dash  │     │
│  └──────────────┘                      └──────────────────┘     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      uasc-m2m                             │   │
│  │            (Symbolic Encoding Research)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
Pre Atlas/
│
├── .claude/                    # Claude Code IDE settings
│   └── settings.local.json
│
├── .delta-fabric/              # State synchronization layer (repo-local)
│   ├── deltas.json             # Delta operation log
│   └── entities.json           # Entity state store
│
├── services/
│   │
│   ├── delta-kernel/           # Delta-State Fabric v0 (TypeScript)
│   │   ├── package.json        # Node.js project config
│   │   ├── tsconfig.json       # TypeScript config
│   │   ├── ARCHITECTURE_MAP.md # System design doc
│   │   ├── start.bat           # Windows launcher
│   │   ├── specs/              # 18 specification documents
│   │   │   ├── module-1-daily-cockpit.md
│   │   │   ├── module-2-preparation-engine.md
│   │   │   ├── module-3-matryoshka-dictionary.md
│   │   │   ├── module-4-vector-discovery.md
│   │   │   ├── module-5-ai-design.md
│   │   │   ├── module-6-delta-sync.md
│   │   │   ├── module-7-off-grid-nodes.md
│   │   │   ├── module-8-ui-surface-streaming.md
│   │   │   ├── module-9-camera-tile-streaming.md
│   │   │   ├── module-10-remote-control.md
│   │   │   ├── module-11-audio-streaming.md
│   │   │   ├── ultra-low-streaming-sdk.md
│   │   │   ├── v0-daily-mode-screen.md
│   │   │   ├── v0-inbox-messaging.md
│   │   │   ├── v0-routing.md
│   │   │   ├── v0-schemas.md
│   │   │   ├── v0-task-lifecycle.md
│   │   │   ├── phase-5b-closure-mechanics.md
│   │   │   └── phase-6a-work-admission-control.md
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   └── server.ts   # REST API server (respects DELTA_DATA_DIR)
│   │   │   ├── cli/
│   │   │   │   ├── index.ts    # CLI entry point
│   │   │   │   ├── app.ts      # Application logic
│   │   │   │   ├── input.ts    # Input handling
│   │   │   │   ├── renderer.ts # Terminal rendering
│   │   │   │   └── storage.ts  # Data persistence
│   │   │   └── core/           # 35 TypeScript modules
│   │   │       ├── types.ts    # Entity type definitions (1130+ lines)
│   │   │       ├── delta.ts    # Delta operations
│   │   │       ├── routing.ts  # Mode computation
│   │   │       └── ...
│   │   └── web/                # React web UI (Vite)
│   │       ├── package.json
│   │       ├── vite.config.ts
│   │       └── src/
│   │
│   └── cognitive-sensor/       # Cognitive Operating System (Python)
│       ├── results.db          # SQLite: 93,898 messages
│       │
│       ├── # Core Pipeline
│       ├── refresh.py          # Master refresh script (CWD-safe)
│       ├── brain.py            # Core brain logic
│       ├── loops.py            # Open loop detection
│       ├── radar.py            # Attention drift detection
│       ├── completion_stats.py # Closure tracking
│       ├── decision_engine.py  # Decision logic
│       ├── route_today.py      # Daily routing
│       │
│       ├── # State Files
│       ├── cognitive_state.json    # Current cognitive state
│       ├── daily_directive.txt     # Today's directive
│       ├── daily_payload.json      # CycleBoard payload
│       ├── completion_stats.json   # Completion metrics
│       ├── loops_latest.json       # Current open loops
│       ├── closures.json           # Phase 5B closure registry
│       ├── loops_closed.json       # Archived closed loops
│       │
│       ├── # Interfaces
│       ├── dashboard.html          # Analytics dashboard
│       ├── control_panel.html      # Master control panel
│       ├── cycleboard_app3.html    # CycleBoard planning tool
│       ├── cycleboard/             # Modular CycleBoard
│       │
│       ├── # Analysis Scripts
│       ├── semantic_loops.py       # Vectorized semantic analysis
│       ├── cluster_topics.py       # Topic clustering
│       ├── language_loops.py       # Language pattern detection
│       ├── belief_core.py          # Belief system analysis
│       ├── belief_grammar.py       # Belief grammar parsing
│       │
│       ├── # Self-Analysis Profiles
│       ├── DEEP_PSYCHOLOGICAL_PROFILE.md
│       ├── EMOTIONAL_PROFILE.md
│       ├── CONVERSATION_PATTERNS.md
│       └── ...
│
├── apps/
│   └── webos-333/              # Web OS Simulator (HTML)
│       ├── web-os-simulator.html   # Complete OS (3,443 lines)
│       ├── WEB-OS-DOCUMENTATION.md # API reference
│       └── SKELETON-MAP.txt        # Code structure map
│
├── research/
│   └── uasc-m2m/               # Symbolic Encoding Research (Python/JS)
│       ├── README.md           # System overview
│       ├── CREATION-GUIDE.md   # Glyph creation guide
│       ├── LLM-GUIDE.md        # LLM integration guide
│       ├── generic/            # Generic framework
│       ├── reference-implementation/
│       └── spec/               # Specifications
│
├── contracts/
│   └── schemas/                # Shared JSON Schema definitions
│       ├── DailyPayload.v1.json
│       ├── CognitiveMetricsComputed.json
│       ├── DirectiveProposed.json
│       ├── DailyProjection.v1.json
│       └── Closures.v1.json    # Phase 5B closure registry schema
│
├── data/
│   └── projections/            # Daily projection artifacts
│       └── today.json          # Combined daily output
│
├── scripts/                    # Launcher scripts
│   ├── run_all.ps1             # Full stack launcher
│   ├── run_cognitive.ps1       # Cognitive sensor only
│   ├── run_delta_api.ps1       # Delta API server
│   └── run_delta_cli.ps1       # Delta CLI
│
├── README.md                   # Repo documentation
├── PRE_ATLAS_MAP.md            # This file
└── CONTEXT_PACKET.md           # LLM handoff context
```

---

## Project Specifications

### 1. .delta-fabric

**Purpose:** Persistent state synchronization layer
**Technology:** JSON files
**Size:** 128 KB

**Files:**
| File | Description |
|------|-------------|
| `entities.json` | Entity store with versioning and hash chains |
| `deltas.json` | Append-only delta operation log |

**Data Model:**
- Entities have: `entity_id`, `entity_type`, `created_at`, `current_version`, `current_hash`, `is_archived`
- System state tracks: `mode`, `sleep_hours`, `open_loops`, `leverage_balance`, `streak_days`

---

### 2. webos-333 (Web OS Simulator)

**Location:** `apps/webos-333/`
**Purpose:** Browser-based operating system demo
**Technology:** Single HTML file (vanilla JS/CSS)
**Size:** 192 KB
**Lines of Code:** 3,443

**Features:**
- 3 themes: Windows 95, XP, Dark
- 12 built-in applications
- Virtual file system with localStorage
- Draggable, resizable, snappable windows
- Terminal with shell commands
- Sound system and notifications

**Applications:**
1. Notepad
2. Calculator
3. Terminal
4. Browser
5. Paint
6. Music Player
7. Minesweeper
8. Solitaire
9. File Explorer
10. Settings
11. Task Manager
12. Image Viewer

**Run:** Open `apps/webos-333/web-os-simulator.html` in browser

---

### 3. delta-kernel (Delta-State Fabric v0)

**Location:** `services/delta-kernel/`
**Purpose:** Deterministic, delta-driven personal operating system engine
**Technology:** TypeScript, Node.js, Express
**Size:** ~148 MB (with node_modules)
**Data Directory:** `.delta-fabric/` (repo-local, configurable via `DELTA_DATA_DIR` env var)

**Architecture:**
```
┌────────────────────────────────────────┐
│              Delta Core                 │
├────────────────────────────────────────┤
│  Entity Framework (types.ts)           │
│    ↓                                   │
│  Delta Operations (delta.ts)           │
│    ↓                                   │
│  State Reconstruction                  │
│    ↓                                   │
│  Routing Engine (routing.ts)           │
│    ↓                                   │
│  Mode Governance (templates.ts)        │
└────────────────────────────────────────┘
```

**11 Modules:**
1. Daily Cockpit - Main UI display
2. Preparation Engine - Draft generation
3. Matryoshka Dictionary - Compression
4. Vector Discovery - Semantic search
5. AI Design - AI integration
6. Delta Sync - Multi-node sync
7. Off-Grid Nodes - Offline support
8. UI Surface Streaming - Remote UI
9. Camera Tile Streaming - Video
10. Remote Control - Device actuation
11. Audio Streaming - Voice/audio

**Modes:**
| Mode | Description | Restrictions |
|------|-------------|--------------|
| RECOVER | Rest and recovery | BUILD/COMPOUND/SCALE blocked |
| CLOSE_LOOPS | Clear pending items | BUILD blocked |
| BUILD | Create new things | None |
| COMPOUND | Extend existing work | None |
| SCALE | Delegate and automate | None |

**Commands:**
```bash
cd services/delta-kernel
npm run start    # Launch CLI
npm run api      # Start REST API (uses DELTA_DATA_DIR env var)
npm run test     # Run tests
npm run build    # Compile TypeScript

# Or use launcher scripts from repo root:
.\scripts\run_delta_cli.ps1   # CLI with repo-local data
.\scripts\run_delta_api.ps1   # API with repo-local data
```

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Get system state |
| `/api/state` | PUT | Update system state |
| `/api/state/unified` | GET | Merged Delta + Cognitive state |
| `/api/ingest/cognitive` | POST | Ingest cognitive metrics |
| `/api/tasks` | GET | List tasks |
| `/api/tasks` | POST | Create task |
| `/api/tasks/:id` | PUT | Update task |
| `/api/stats` | GET | Get statistics |
| `/api/law/close_loop` | POST | Canonical closure event (Phase 5B) |
| `/api/law/acknowledge` | POST | Acknowledge daily order |
| `/api/law/violation` | POST | Log build violation |
| `/api/daemon/status` | GET | Governance daemon status |
| `/api/daemon/run` | POST | Manually trigger daemon job |

---

### 4. cognitive-sensor (Cognitive Operating System)

**Location:** `services/cognitive-sensor/`
**Purpose:** Behavioral governance through conversation analysis
**Technology:** Python, SQLite, HTML/JS
**Size:** ~156 MB

**Architecture (6 Layers):**

```
┌─────────────────────────────────────────┐
│  Layer 6: INTERFACE GOVERNANCE          │
│  CycleBoard, Dashboard, Control Panel   │
├─────────────────────────────────────────┤
│  Layer 5: LAW GENERATION                │
│  daily_directive.txt, daily_payload     │
├─────────────────────────────────────────┤
│  Layer 4: NERVOUS SYSTEM                │
│  cognitive_state.json                   │
├─────────────────────────────────────────┤
│  Layer 3: INTELLIGENCE                  │
│  radar.py, loops.py, completion_stats   │
├─────────────────────────────────────────┤
│  Layer 2: DECISION TRACKING             │
│  loop_decisions table                   │
├─────────────────────────────────────────┤
│  Layer 1: MEMORY                        │
│  results.db (93,898 messages)           │
└─────────────────────────────────────────┘
```

**Routing Rules:**
| Mode | Condition | Color |
|------|-----------|-------|
| CLOSURE | closure_ratio < 15% OR open_loops > 20 | RED |
| MAINTENANCE | open_loops > 10 AND closure_ratio >= 15% | YELLOW |
| BUILD | open_loops <= 10 AND closure_ratio >= 15% | GREEN |

**Key Commands:**
```bash
# From repo root (recommended - CWD-safe):
python services/cognitive-sensor/refresh.py

# Or use launcher script:
.\scripts\run_cognitive.ps1

# Individual scripts (run from services/cognitive-sensor/):
python loops.py             # Detect open loops
python route_today.py       # Generate daily directive
python build_dashboard.py   # Rebuild dashboard
python wire_cycleboard.py   # Wire cognitive state to UI
```

**Output Files:**
| File | Description | Location |
|------|-------------|----------|
| `cognitive_state.json` | Current state snapshot | `services/cognitive-sensor/` |
| `daily_directive.txt` | Today's mode and action | `services/cognitive-sensor/` |
| `loops_latest.json` | Current open loops | `services/cognitive-sensor/` |
| `completion_stats.json` | Completion metrics | `services/cognitive-sensor/` |
| `daily_payload.json` | CycleBoard payload | `~/Downloads/cycleboard/brain/` |
| `today.json` | Combined daily projection | `data/projections/` |

**Contract Validation:**
All exports are validated against JSON Schema before writing:
- `export_cognitive_state.py` → `CognitiveMetricsComputed.json`
- `export_daily_payload.py` → `DailyPayload.v1.json`
- `build_projection.py` → `DailyProjection.v1.json`
- `closures.json` → `Closures.v1.json` (Phase 5B)

---

### 5. Phase 5B — Closure Mechanics Core

**Location:** Spans `delta-kernel` and `cognitive-sensor`
**Specification:** `services/delta-kernel/specs/phase-5b-closure-mechanics.md`
**Status:** IMPLEMENTED (2026-01-09)

**Purpose:** Establishes closure as a real state-transition event with automatic mode flips and streak compounding.

**Components:**

| Component | Location | Description |
|-----------|----------|-------------|
| Law Genesis Layer | `delta.ts:89-104` | Auto-creates constitutional state branches |
| Closure Endpoint | `server.ts:718-1029` | `POST /api/law/close_loop` |
| Closure Registry | `closures.json` | Persistent closure history + stats |
| Mode Engine | `governance_daemon.ts` | Autonomous 15-minute recalculation |
| Streak Engine | `server.ts` + `daemon` | BUILD-only increment, day-end reset |

**Mode Transition Rules:**

| closure_ratio | Mode | build_allowed |
|---------------|------|---------------|
| ≥ 0.80 | SCALE | true |
| ≥ 0.60 | BUILD | true |
| ≥ 0.40 | MAINTENANCE | false |
| < 0.40 | CLOSURE | false |

**Governance Daemon Jobs:**

| Job | Schedule | Description |
|-----|----------|-------------|
| heartbeat | */5 * * * * | Update daemon status |
| refresh | 0 * * * * | Run cognitive refresh |
| day_start | 0 6 * * * | Reset daily counters, recalc mode |
| day_end | 0 22 * * * | Streak reset if no BUILD closure |
| mode_recalc | */15 * * * * | Autonomous mode governance |

---

### 6. uasc-m2m (Ultra-Compressed Symbolic Encoding)

**Location:** `research/uasc-m2m/`
**Purpose:** Research framework for extreme information compression
**Technology:** Python, JavaScript
**Size:** 1.8 MB

**Concept:**
- Encodes applications/workflows into single Chinese-inspired glyphs
- Stroke patterns = logical operations
- Context-sensitive execution

**Compression Levels:**
| Level | Compression |
|-------|-------------|
| 1 | One sentence → One glyph |
| 4 | City's conversations → One glyph |
| 7 | All human knowledge → One glyph (theoretical) |

**Key Commands:**
```bash
cd research/uasc-m2m/generic
python examples.py              # Run examples
python uasc_generic.py --server 8420  # Start HTTP server
```

**API Endpoints (when server running):**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/commands` | GET | List available commands |
| `/exec` | POST | Execute a command |
| `/health` | GET | Health check |

---

## Inter-Project Dependencies

```
.delta-fabric/
    │
    └──▶ services/delta-kernel (reads/writes entities.json, deltas.json)
              │
              └──▶ services/cognitive-sensor (conceptual alignment, separate data)
                        │
                        └──▶ CycleBoard/Dashboard (reads cognitive_state.json)
                        │
                        └──▶ ~/Downloads/cycleboard/brain/ (daily_payload.json)

apps/webos-333 ──── Standalone (no dependencies)

research/uasc-m2m ──── Standalone research (no dependencies)

contracts/schemas/ ──── Shared data contracts (consumed by all services)
```

---

## Quick Start

### Run Everything (Recommended)
```powershell
# From repo root:
.\scripts\run_all.ps1
```

**Pipeline Steps:**
```
[1/4] Delta API        → http://localhost:3001
[2/4] Cognitive Sensor → cognitive_state.json
[3/4] Daily Projection → data/projections/today.json
[4/4] Push to Delta    → POST /api/ingest/cognitive
```

### Individual Services
```powershell
# Delta Kernel (requires Node.js)
.\scripts\run_delta_api.ps1   # REST API on :3001
.\scripts\run_delta_cli.ps1   # Interactive CLI

# Cognitive Sensor (requires Python)
.\scripts\run_cognitive.ps1   # Full analysis pipeline

# Web OS
# Just open: apps/webos-333/web-os-simulator.html

# UASC-M2M Research
cd research/uasc-m2m/generic
python examples.py
```

### First-Time Setup
```powershell
# Install Delta dependencies
cd services/delta-kernel
npm install
```

---

## File Statistics

| Project | Location | Files | Lines of Code (est.) |
|---------|----------|-------|---------------------|
| .delta-fabric | `.delta-fabric/` | 2 | ~500 (JSON) |
| webos-333 | `apps/webos-333/` | 3 | ~4,000 |
| delta-kernel | `services/delta-kernel/` | ~70 | ~15,000 |
| cognitive-sensor | `services/cognitive-sensor/` | ~80 | ~12,000 |
| uasc-m2m | `research/uasc-m2m/` | ~60 | ~8,000 |
| contracts | `contracts/` | 4 | ~100 |
| scripts | `scripts/` | 4 | ~150 |
| **Total** | | **~223** | **~39,750** |

---

## Notes

1. **Path Configuration:** All Python scripts use relative paths via `Path(__file__).parent` or `Path.home()` for portability. Scripts are CWD-safe and can be run from any directory.

2. **Delta Data Directory:** Delta uses `.delta-fabric/` (repo-local) by default. This can be overridden via `DELTA_DATA_DIR` environment variable. The launcher scripts automatically configure this.

3. **Database:** `results.db` in `services/cognitive-sensor/` contains conversation history (~93,898 messages). Back this up separately if needed.

4. **Node Modules:** The `services/delta-kernel/node_modules` folder (~148MB) can be regenerated with `npm install`.

5. **Contracts:** Shared JSON Schema definitions live in `contracts/schemas/`. These define the data formats exchanged between services.

6. **Problematic File:** There's a `nul` file in `research/uasc-m2m/reference-implementation/` that caused zip issues on Windows. Can be safely deleted.

---

*Generated: 2026-01-08*
*Updated: 2026-01-08 (Phase 2 - contracts, projections, C→D bridge)*
*Updated: 2026-01-09 (Phase 5B - closure mechanics, autonomous mode governance)*
