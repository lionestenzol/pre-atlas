# Pre Atlas — Complete File & Connection Map

**Generated:** 2026-01-08
**Updated:** 2026-01-12 (Phase 6C - Timeline Layer, doc sync)
**Phase History:** See `PHASE_ROADMAP.md` for complete implementation timeline

---

## Directory Structure

```
Pre Atlas/
│
├── .claude/                           # Claude Code settings
│   └── settings.local.json
│
├── .delta-fabric/                     # Delta state storage (repo-local)
│   ├── deltas.json                    # Append-only delta log
│   └── entities.json                  # Entity state store
│
├── apps/
│   └── webos-333/                     # Standalone web OS demo
│       ├── web-os-simulator.html      # Complete OS (3,443 lines)
│       └── WEB-OS-DOCUMENTATION.md
│
├── contracts/
│   ├── examples/
│   │   └── daily_payload_example.json
│   └── schemas/                       # JSON Schema contracts
│       ├── CognitiveMetricsComputed.json
│       ├── DailyPayload.v1.json
│       ├── DailyProjection.v1.json
│       ├── DirectiveProposed.json
│       └── Closures.v1.json           # Phase 5B closure registry
│
├── data/
│   └── projections/
│       └── today.json                 # Combined daily artifact
│
├── research/
│   └── uasc-m2m/                      # Symbolic encoding research
│       ├── generic/
│       │   ├── examples.py
│       │   ├── uasc_generic.py
│       │   └── profiles/TEMPLATE.json
│       ├── reference-implementation/
│       │   ├── core/
│       │   │   ├── glyph.py
│       │   │   ├── interpreter.py
│       │   │   ├── registry.py
│       │   │   └── trust.py
│       │   ├── actions/
│       │   │   └── traffic_control.py
│       │   └── mvp/
│       │       ├── auth.py
│       │       ├── cli.py
│       │       ├── executor.py
│       │       └── server.py
│       ├── spec/
│       │   ├── 00-SPECIFICATION-INDEX.md
│       │   ├── 01-REGISTRY-SPECIFICATION.md
│       │   ├── 02-GLYPH-ENCODING-STANDARD.md
│       │   ├── 03-AUTHORITY-MODEL.md
│       │   ├── 04-INTERPRETER-SPECIFICATION.md
│       │   └── 05-REFERENCE-IMPLEMENTATION.md
│       ├── README.md
│       ├── CREATION-GUIDE.md
│       └── LLM-GUIDE.md
│
├── scripts/                           # PowerShell launchers
│   ├── run_all.ps1                    # Full 4-step pipeline
│   ├── run_cognitive.ps1              # Cognitive sensor only
│   ├── run_delta_api.ps1              # Delta REST API
│   └── run_delta_cli.ps1              # Delta interactive CLI
│
├── services/
│   ├── cognitive-sensor/              # Python behavioral analysis
│   │   ├── # === CORE PIPELINE ===
│   │   ├── refresh.py                 # Master orchestrator
│   │   ├── loops.py                   # Open loop detection
│   │   ├── completion_stats.py        # Closure tracking
│   │   ├── cognitive_api.py           # State query API
│   │   ├── export_cognitive_state.py  # Exports cognitive_state.json
│   │   ├── route_today.py             # Daily mode routing
│   │   ├── export_daily_payload.py    # Exports daily_payload.json
│   │   ├── wire_cycleboard.py         # Wires to CycleBoard
│   │   ├── reporter.py                # State history logging
│   │   ├── build_dashboard.py         # Generates dashboard.html
│   │   │
│   │   ├── # === PHASE 2 ADDITIONS ===
│   │   ├── validate.py                # Contract validation
│   │   ├── build_projection.py        # Builds today.json
│   │   ├── push_to_delta.py           # POSTs to Delta API
│   │   │
│   │   ├── # === ANALYSIS SCRIPTS ===
│   │   ├── radar.py                   # Attention drift detection
│   │   ├── semantic_loops.py          # Vectorized loop detection
│   │   ├── cluster_topics.py          # Topic clustering
│   │   ├── cluster_business_topics.py # Business topic clustering
│   │   ├── language_loops.py          # Language pattern detection
│   │   ├── belief_core.py             # Belief system analysis
│   │   ├── belief_grammar.py          # Belief grammar parsing
│   │   ├── brain.py                   # Core brain logic
│   │   ├── decision_engine.py         # Decision logic
│   │   │
│   │   ├── # === INTERACTIVE TOOLS ===
│   │   ├── decide.py                  # Loop closure decisions
│   │   ├── resurfacer.py              # Weekly loop resurfacing
│   │   ├── search_loops.py            # Search conversations
│   │   ├── inject_directive.py        # Inject directives
│   │   │
│   │   ├── # === INIT SCRIPTS ===
│   │   ├── init_results_db.py         # Build messages table
│   │   ├── init_topics.py             # Extract topics
│   │   ├── init_convo_time.py         # Add timestamps
│   │   ├── init_titles.py             # Load titles
│   │   ├── init_embeddings.py         # Generate embeddings
│   │   │
│   │   ├── # === DATA FILES ===
│   │   ├── results.db                 # SQLite (93,898 messages)
│   │   ├── memory_db.json             # Source conversation data
│   │   ├── cognitive_state.json       # Current state snapshot
│   │   ├── loops_latest.json          # Top 15 open loops
│   │   ├── loops_closed.json          # Phase 5B: archived closed loops
│   │   ├── closures.json              # Phase 5B: closure registry
│   │   ├── completion_stats.json      # Completion metrics
│   │   ├── semantic_loops.json        # Vectorized loop data
│   │   ├── topic_clusters.json        # Topic clusters
│   │   │
│   │   ├── # === INTERFACES ===
│   │   ├── dashboard.html             # Analytics dashboard
│   │   ├── control_panel.html         # Master control panel
│   │   ├── cycleboard_app3.html       # CycleBoard planning tool
│   │   └── cycleboard/                # Modular CycleBoard
│   │
│   └── delta-kernel/                  # TypeScript state engine
│       ├── package.json
│       ├── tsconfig.json
│       ├── start.bat
│       ├── src/
│       │   ├── api/
│       │   │   └── server.ts          # REST API (port 3001)
│       │   ├── cli/
│       │   │   ├── index.ts           # CLI entry point
│       │   │   ├── app.ts             # Application logic
│       │   │   ├── input.ts           # Keyboard handling
│       │   │   ├── renderer.ts        # Terminal rendering
│       │   │   └── storage.ts         # Data persistence
│       │   ├── core/
│       │   │   ├── types.ts           # Type definitions
│       │   │   ├── delta.ts           # Delta operations + Law Genesis Layer
│       │   │   ├── routing.ts         # Mode computation
│       │   │   ├── templates.ts       # Mode templates
│       │   │   ├── tasks.ts           # Task management
│       │   │   ├── messaging.ts       # Inbox/messaging
│       │   │   ├── cockpit.ts         # Daily cockpit
│       │   │   ├── preparation.ts     # Draft preparation
│       │   │   ├── dictionary.ts      # Compression
│       │   │   ├── vector-discovery.ts# Semantic search
│       │   │   ├── ai-design.ts       # AI integration
│       │   │   ├── delta-sync.ts      # Multi-node sync
│       │   │   ├── off-grid-node.ts   # Offline support
│       │   │   ├── ui-surface.ts      # UI streaming
│       │   │   ├── camera-surface.ts  # Video streaming
│       │   │   ├── control-surface.ts # Device control
│       │   │   └── actuation.ts       # Remote actuation
│       │   └── governance/
│       │       └── governance_daemon.ts # Phase 5B: autonomous mode daemon
│       ├── specs/                     # 18 specification docs
│       │   ├── v0-schemas.md
│       │   ├── v0-routing.md
│       │   ├── v0-task-lifecycle.md
│       │   ├── v0-inbox-messaging.md
│       │   ├── v0-daily-mode-screen.md
│       │   ├── phase-5b-closure-mechanics.md  # Phase 5B spec
│       │   └── module-1 through module-11
│       └── web/                       # React web UI
│           ├── package.json
│           ├── vite.config.ts
│           └── index.html
│
├── README.md                          # Quick start guide
├── PRE_ATLAS_MAP.md                   # System architecture
├── CONTEXT_PACKET.md                  # LLM handoff context
├── FILE_MAP.md                        # This file
└── PHASE_ROADMAP.md                   # Complete phase history (1 → 5B)
```

---

## Connection Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              run_all.ps1                                 │
│                         (4-step orchestrator)                            │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
    ┌───────────────────────────┼───────────────────────────────┐
    │                           │                               │
    ▼                           ▼                               ▼
┌─────────┐              ┌─────────────┐              ┌─────────────────┐
│ Step 1  │              │   Step 2    │              │    Step 3-4     │
│ Delta   │              │  Cognitive  │              │   Projection    │
│  API    │              │   Sensor    │              │    & Push       │
└────┬────┘              └──────┬──────┘              └────────┬────────┘
     │                          │                              │
     ▼                          ▼                              ▼
┌─────────┐              ┌─────────────┐              ┌─────────────────┐
│server.ts│              │ refresh.py  │              │build_projection │
│ :3001   │              │             │              │ push_to_delta   │
└────┬────┘              └──────┬──────┘              └────────┬────────┘
     │                          │                              │
     ▼                          ▼                              │
┌─────────┐              ┌─────────────┐                       │
│.delta-  │              │   8 scripts │                       │
│fabric/  │              │  in sequence│                       │
│entities │              └──────┬──────┘                       │
│deltas   │                     │                              │
└─────────┘                     ▼                              │
     ▲              ┌───────────────────────┐                  │
     │              │    OUTPUT FILES       │                  │
     │              ├───────────────────────┤                  │
     │              │ cognitive_state.json  │──────────────────┤
     │              │ daily_payload.json    │                  │
     │              │ loops_latest.json     │                  │
     │              │ dashboard.html        │                  │
     │              └───────────────────────┘                  │
     │                                                         │
     │                    ┌────────────────┐                   │
     │                    │ today.json     │◄──────────────────┘
     │                    │ (projection)   │
     │                    └───────┬────────┘
     │                            │
     │                            │ POST /api/ingest/cognitive
     └────────────────────────────┘
```

---

## Data Flow Details

### 1. Cognitive Sensor Pipeline

```
results.db (93,898 messages)
    │
    ▼
loops.py ──────────────────────► loops_latest.json
    │
    ▼
completion_stats.py ───────────► completion_stats.json
    │
    ▼
export_cognitive_state.py ─────► cognitive_state.json
    │                                    │
    │                     ┌──────────────┘
    ▼                     ▼
route_today.py ◄──────────┘
    │
    ▼
daily_directive.txt
    │
    ▼
export_daily_payload.py ───────► ~/Downloads/cycleboard/brain/daily_payload.json
    │
    ▼
wire_cycleboard.py
    │
    ▼
reporter.py ───────────────────► STATE_HISTORY.md
    │
    ▼
build_dashboard.py ────────────► dashboard.html
```

### 2. Phase 2 Bridge (C → D)

```
cognitive_state.json ─────┐
                          │
                          ▼
                   build_projection.py
                          │
                          ├──► validates against DailyProjection.v1.json
                          │
                          ▼
                   data/projections/today.json
                          │
                          ▼
                   push_to_delta.py
                          │
                          │ HTTP POST
                          ▼
              ┌───────────────────────────┐
              │  Delta API                │
              │  POST /api/ingest/cognitive│
              └───────────────┬───────────┘
                              │
                              ▼
                       .delta-fabric/
                       entities.json
                       (system_state updated)
```

### 3. Contract Validation

```
┌──────────────────────────┐     ┌─────────────────────────────────┐
│ export_cognitive_state.py│────►│ CognitiveMetricsComputed.json   │
└──────────────────────────┘     └─────────────────────────────────┘

┌──────────────────────────┐     ┌─────────────────────────────────┐
│ export_daily_payload.py  │────►│ DailyPayload.v1.json            │
└──────────────────────────┘     └─────────────────────────────────┘

┌──────────────────────────┐     ┌─────────────────────────────────┐
│ build_projection.py      │────►│ DailyProjection.v1.json         │
└──────────────────────────┘     └─────────────────────────────────┘

┌──────────────────────────┐     ┌─────────────────────────────────┐
│ closures.json            │────►│ Closures.v1.json (Phase 5B)     │
└──────────────────────────┘     └─────────────────────────────────┘
```

### 4. Phase 5B — Closure Mechanics Flow

```
                      ┌─────────────────────────────────────┐
                      │  POST /api/law/close_loop           │
                      │  { loop_id, title, outcome }        │
                      └─────────────────┬───────────────────┘
                                        │
                      ┌─────────────────┼─────────────────┐
                      │                 │                 │
                      ▼                 ▼                 ▼
               ┌──────────┐     ┌────────────┐    ┌────────────┐
               │closures. │     │ Atomic     │    │ Physical   │
               │json      │     │ Delta      │    │ Loop       │
               │(registry)│     │ (system_   │    │ Removal    │
               └──────────┘     │  state)    │    └────────────┘
                      │         └────────────┘           │
                      │                │                 │
                      │                ▼                 ▼
                      │    ┌─────────────────────────────────┐
                      │    │ loops_latest.json (filtered)    │
                      │    │ loops_closed.json (appended)    │
                      │    └─────────────────────────────────┘
                      │
                      ▼
     ┌───────────────────────────────────────────────────┐
     │ Governance Daemon (autonomous, every 15 min)      │
     │  ┌──────────────┐  ┌──────────────┐              │
     │  │ mode_recalc  │  │ day_start    │              │
     │  │ (ratio→mode) │  │ day_end      │              │
     │  └──────────────┘  └──────────────┘              │
     │        │                  │                       │
     │        ▼                  ▼                       │
     │  ┌──────────────────────────────────────┐        │
     │  │ streak_reset (if no BUILD closure)   │        │
     │  └──────────────────────────────────────┘        │
     └───────────────────────────────────────────────────┘
```

---

## API Endpoints (Delta Kernel)

### State & Tasks
| Endpoint | Method | Description | Connected To |
|----------|--------|-------------|--------------|
| `/api/state` | GET | Get system state | CLI, Web UI |
| `/api/state` | PUT | Update state | CLI, Web UI |
| `/api/state/unified` | GET | Merged Delta + Cognitive state | atlas_boot.html |
| `/api/ingest/cognitive` | POST | Ingest from cognitive-sensor | push_to_delta.py |
| `/api/tasks` | GET | List tasks | CLI, Web UI |
| `/api/tasks` | POST | Create task | CLI, Web UI |
| `/api/tasks/:id` | PUT | Update task | CLI, Web UI |
| `/api/tasks/:id` | DELETE | Archive task | CLI, Web UI |
| `/api/stats` | GET | Get statistics | Web UI |
| `/api/health` | GET | Health check | Monitoring |

### Law & Enforcement (Phase 4-5B)
| Endpoint | Method | Description | Connected To |
|----------|--------|-------------|--------------|
| `/api/law/close_loop` | POST | Canonical closure event | atlas_boot.html |
| `/api/law/acknowledge` | POST | Acknowledge daily order | atlas_boot.html |
| `/api/law/violation` | POST | Log build violation | Enforcement |
| `/api/law/override` | POST | Emergency override with reason | Enforcement |
| `/api/law/archive` | POST | Archive loop without closure | Admin |
| `/api/law/refresh` | POST | Trigger cognitive refresh | Admin |

### Governance Daemon (Phase 3)
| Endpoint | Method | Description | Connected To |
|----------|--------|-------------|--------------|
| `/api/daemon/status` | GET | Governance daemon status | atlas_boot.html |
| `/api/daemon/run` | POST | Manually trigger daemon job | Admin |

### Work Admission Control (Phase 6A)
| Endpoint | Method | Description | Connected To |
|----------|--------|-------------|--------------|
| `/api/work/request` | POST | Request permission to start a job | AI agents, gate CLI |
| `/api/work/complete` | POST | Report job completion | AI agents, gate CLI |
| `/api/work/status` | GET | Query current work state | Control panel |
| `/api/work/cancel` | POST | Cancel a job | Admin |
| `/api/work/history` | GET | Get job history | Control panel |

### Timeline (Phase 6C)
| Endpoint | Method | Description | Connected To |
|----------|--------|-------------|--------------|
| `/api/timeline` | GET | Query events with filters | Timeline viewer |
| `/api/timeline/stats` | GET | Event statistics | Timeline viewer |
| `/api/timeline/day/:date` | GET | All events for a specific day | Timeline viewer |

---

## File Categories

### Authoritative Data (Source of Truth)
- `.delta-fabric/entities.json` — Delta state
- `.delta-fabric/deltas.json` — Delta audit log
- `services/cognitive-sensor/results.db` — Conversation history

### Derived Projections (Computed)
- `cognitive_state.json` — Current cognitive metrics
- `loops_latest.json` — Open loops list
- `loops_closed.json` — Phase 5B: archived closed loops *(created on first closure)*
- `closures.json` — Phase 5B: closure registry with stats
- `completion_stats.json` — Closure statistics
- `daily_payload.json` — CycleBoard data
- `data/projections/today.json` — Combined daily artifact
- `work_ledger.json` — Phase 6A: work admission ledger
- `timeline_events.json` — Phase 6C: event log *(created on first system start)*

### Contracts (Schema Definitions)
- `contracts/schemas/*.json` — JSON Schema definitions

### Configuration
- `.claude/settings.local.json` — Claude Code permissions
- `package.json` — Node.js dependencies
- `tsconfig.json` — TypeScript config

### Documentation
- `README.md` — Quick start
- `PRE_ATLAS_MAP.md` — Architecture
- `CONTEXT_PACKET.md` — LLM context
- `FILE_MAP.md` — This file
- `services/delta-kernel/specs/*.md` — 18 spec documents
- `services/cognitive-sensor/*.md` — Profile analysis docs

### Interfaces
- `dashboard.html` — Analytics
- `control_panel.html` — Master control
- `cycleboard_app3.html` — Planning tool
- `web-os-simulator.html` — OS demo

---

## Standalone Projects (No Dependencies)

| Project | Location | Purpose |
|---------|----------|---------|
| webos-333 | `apps/webos-333/` | Browser OS demo |
| uasc-m2m | `research/uasc-m2m/` | Symbolic encoding research |

These have no connections to the main system.

---

## Key Scripts by Purpose

### Launcher Scripts
| Script | Runs |
|--------|------|
| `run_all.ps1` | Delta API + refresh + projection + push |
| `run_cognitive.ps1` | refresh.py only |
| `run_delta_api.ps1` | server.ts only |
| `run_delta_cli.ps1` | CLI only |

### Analysis Scripts
| Script | Output |
|--------|--------|
| `loops.py` | loops_latest.json |
| `completion_stats.py` | completion_stats.json |
| `radar.py` | Attention drift report |
| `semantic_loops.py` | semantic_loops.json |

### Export Scripts
| Script | Output | Validates Against |
|--------|--------|-------------------|
| `export_cognitive_state.py` | cognitive_state.json | CognitiveMetricsComputed.json |
| `export_daily_payload.py` | daily_payload.json | DailyPayload.v1.json |
| `build_projection.py` | today.json | DailyProjection.v1.json |

---

*End of File Map*
