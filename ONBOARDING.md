# Pre Atlas — Developer Onboarding

**Read time: 10 minutes**

---

## What is Pre Atlas?

Pre Atlas is a **personal behavioral governance system**. It analyzes your AI conversation history (~94K messages) to answer one question:

> *"What should I be doing right now, and am I allowed to start something new?"*

It detects open loops (things you started but never finished), computes a closure ratio, and forces you into one of 6 operational modes. The mode gates what actions you're allowed to take. No AI decides the mode — it's a deterministic lookup table.

### The 6 Modes

```
RECOVER   → You're sleep-deprived. Rest only. Nothing else allowed.
CLOSURE   → Too many open loops. Close them before starting anything new.
MAINTENANCE → Light admin work. No new projects.
BUILD     → You've earned the right to create. Ship something.
COMPOUND  → Extend what you've built. Stack wins.
SCALE     → Delegate and automate. You're operating well.
```

Mode transitions are computed from 5 signals: `sleep_hours`, `open_loops`, `assets_shipped`, `deep_work_blocks`, `money_delta`. Each signal is bucketed (LOW/OK/HIGH) and fed through a routing table. No randomness. No AI judgment.

---

## Architecture at a Glance

Three services, one shared state directory, connected by REST + file I/O:

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   COGNITIVE SENSOR (Python)                         │
│   Analyzes conversations → computes state & mode    │
│   Port: none (batch pipeline)                       │
│                                                     │
│   reads from: results.db (SQLite, 94K messages)     │
│   writes to:  cognitive_state.json                  │
│               daily_payload.json                    │
│               daily_directive.txt                   │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │ POST /api/ingest/cognitive
                   ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│   DELTA KERNEL (TypeScript)                         │
│   Deterministic state engine + governance daemon    │
│   Port: 3001                                        │
│                                                     │
│   stores:  .delta-fabric/entities.json              │
│            .delta-fabric/deltas.json (hash-chained) │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │ mode & state available via API
                   ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│   AEGIS FABRIC (TypeScript)                         │
│   Policy gate for AI agent actions                  │
│   Port: 3002                                        │
│                                                     │
│   Agent sends action → policy evaluated →           │
│   ALLOW / DENY / REQUIRE_HUMAN                      │
│                                                     │
│   stores:  .aegis-data/ (per-tenant files)          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Key principle:** All state mutations are append-only, hash-chained JSON Patches (RFC 6902). You can reconstruct any entity's state by replaying its deltas from the beginning.

---

## How to Run It

### Prerequisites
- Node.js 18+
- Python 3.10+
- PowerShell (Windows)

### Full Stack (recommended first time)

```powershell
cd "C:\Users\bruke\Pre Atlas"
.\scripts\run_all.ps1
```

This runs a 4-step pipeline:
1. Starts Delta API server (new terminal, port 3001)
2. Runs cognitive-sensor analysis (`python refresh.py`)
3. Builds daily projection (`data/projections/today.json`)
4. Pushes cognitive state to Delta API

### Individual Services

```powershell
# Delta API only
cd services/delta-kernel
npm install
npm run api            # Express on :3001 + governance daemon

# Delta CLI (interactive terminal)
npm run start

# Cognitive Sensor (one-shot analysis)
cd services/cognitive-sensor
pip install -r requirements.txt
python refresh.py

# Aegis Fabric
cd services/aegis-fabric
npm install
npm run api            # Express on :3002
```

### Browser UIs (no server needed)

Open these directly in a browser:
- **CycleBoard** — `services/cognitive-sensor/cycleboard/index.html`
- **Cognitive Atlas** — `services/cognitive-sensor/cognitive_atlas.html`
- **Dashboard** — `services/cognitive-sensor/dashboard.html`

---

## How the Parts Connect

### Data Pipeline (runs daily or on demand)

```
results.db (94K messages)
    │
    ├── loops.py ──────────→ Detect open loops (intent vs completion scoring)
    ├── completion_stats.py → Compute closure ratio
    ├── route_today.py ────→ Determine mode (CLOSURE/BUILD/etc)
    │
    ▼
cognitive_state.json ──→ export_daily_payload.py ──→ daily_payload.json
    │
    ▼
build_projection.py ──→ data/projections/today.json
    │
    ▼
push_to_delta.py ─────→ POST /api/ingest/cognitive → Delta Kernel
    │
    ▼
routing.ts ───────────→ Bucket signals → LUT lookup → Mode update
    │
    ▼
.delta-fabric/entities.json (persisted)
.delta-fabric/deltas.json   (append-only audit log)
```

### Governance Daemon (background, always running with Delta API)

| Schedule | Job | What it does |
|----------|-----|-------------|
| Every 5 min | heartbeat | Health check |
| Every 15 min | mode_recalc | Re-evaluate mode from signals |
| Every 1 hour | refresh | Re-run cognitive-sensor pipeline |
| Every 1 min | work_queue | Process work admission requests |
| 06:00 | day_start | Reset daily counters |
| 22:00 | day_end | Reset streaks |

### Aegis Agent Flow

```
AI Agent (Claude/OpenAI/custom)
    │
    │  POST /api/v1/agent/action
    ▼
Agent Adapter ──→ Normalize to CanonicalAgentAction
    │
    ▼
Policy Engine ──→ Evaluate rules (first match wins)
    │
    ├── ALLOW ──────→ Execute action → create Delta → audit log
    ├── DENY ───────→ Return 403 + reason
    └── REQUIRE_HUMAN → Queue for approval → human reviews
```

---

## Important Files

### You'll touch these most often

| File | What it is |
|------|-----------|
| `services/delta-kernel/src/core/types.ts` | **Start here.** All type definitions — 24 entity types, 6 modes, Delta/Entity interfaces. 1,162 lines. |
| `services/delta-kernel/src/core/routing.ts` | Mode computation. Signals → buckets → LUT → mode. The behavioral spine. |
| `services/delta-kernel/src/core/delta.ts` | Hash-chained delta creation & application (RFC 6902 JSON Patch). |
| `services/delta-kernel/src/api/server.ts` | REST API (port 3001). 15+ endpoints for state, tasks, law, daemon. |
| `services/delta-kernel/src/governance/governance_daemon.ts` | Cron-scheduled autonomous governance (mode recalc, daily reset). |
| `services/cognitive-sensor/refresh.py` | Master pipeline — runs the full analysis chain. |
| `services/cognitive-sensor/loops.py` | Open loop detection (intent + completion scoring). |
| `services/cognitive-sensor/route_today.py` | Python-side mode routing. |
| `services/cognitive-sensor/atlas_config.py` | North Star, targets, strengths/weaknesses, autonomy levels. |
| `services/aegis-fabric/src/policies/policy-engine.ts` | Declarative rule evaluation. 9 operators, 3 effects. |
| `services/aegis-fabric/src/agents/agent-adapter.ts` | Normalizes Claude/OpenAI/custom → CanonicalAgentAction. |

### State files you'll read/debug

| File | What it holds |
|------|-------------|
| `.delta-fabric/entities.json` | Current entity state (all types). |
| `.delta-fabric/deltas.json` | Append-only hash-chained audit log. |
| `services/cognitive-sensor/cognitive_state.json` | Current cognitive metrics (closure ratio, open loops, topics). |
| `services/cognitive-sensor/cycleboard/brain/daily_payload.json` | Mode, risk level, primary action — consumed by CycleBoard UI. |
| `services/cognitive-sensor/loops_latest.json` | Top open loops by score. |
| `services/cognitive-sensor/idea_registry.json` | Prioritized ideas (tiers: execute_now, next_up, backlog). |

### Contracts (data validation at service boundaries)

All in `contracts/schemas/` — JSON Schema draft-07:

| Schema | Validates |
|--------|----------|
| `CognitiveMetricsComputed.json` | Cognitive state export |
| `DailyPayload.v1.json` | CycleBoard UI payload |
| `DailyProjection.v1.json` | Combined daily projection |
| `Closures.v1.json` | Closure registry + streaks |
| `Aegis*.v1.json` (7 schemas) | Agent, Policy, Tenant, Approval, Action, Decision, Webhook |

### Documentation (read if you need deeper context)

| Doc | When to read it |
|-----|----------------|
| `PRE_ATLAS_MAP.md` | Master architecture reference (19 specs linked). |
| `CONTEXT_PACKET.md` | Full system context with all assumptions. |
| `services/delta-kernel/ARCHITECTURE_MAP.md` | Delta lifecycle, routing lifecycle, sync lifecycle. |
| `services/delta-kernel/specs/` | 19 module specifications (cockpit, preparation, sync, camera, etc). |
| `services/cognitive-sensor/SYSTEM_MAP.md` | Cognitive sensor data flow and layer architecture. |
| `services/cognitive-sensor/AGENTS.md` | Agent pipeline documentation. |

---

## Key API Endpoints

### Delta Kernel (port 3001)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/state` | Current system state |
| PUT | `/api/state` | Update system state |
| GET | `/api/state/unified` | Merged Delta + Cognitive state |
| POST | `/api/ingest/cognitive` | Ingest cognitive metrics |
| GET | `/api/tasks` | List tasks |
| POST | `/api/tasks` | Create task |
| POST | `/api/law/close_loop` | Record a closure event |
| GET | `/api/daemon/status` | Daemon state + job history |
| POST | `/api/daemon/run` | Manually trigger a daemon job |

### Aegis Fabric (port 3002)

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/v1/agent/action` | **Main endpoint** — submit agent action |
| GET | `/api/v1/policies` | Get policy rules |
| POST | `/api/v1/policies/simulate` | Test a policy without side effects |
| GET | `/api/v1/approvals` | List pending human approvals |
| POST | `/api/v1/approvals/:id/approve` | Approve a queued action |
| GET | `/api/v1/state/entities` | List entities by type |
| GET | `/health` | Health check |

---

## Things to Know Before You Touch the Code

1. **`tsc` will fail.** There are pre-existing type errors in `server.ts`, `renderer.ts`, `ai-design.ts`, `camera-extractor.ts`. Runtime works fine via `tsx` which bypasses strict type checking. Don't try to fix these unless specifically asked.

2. **Hash chain forks exist.** There are 10 documented fork points in `.delta-fabric/deltas.json` caused by concurrent writes without file locking. See `HASH_CHAIN_FORKS.md`.

3. **Modules 6-11 are stubs.** Delta Sync, Off-Grid, UI Streaming, Camera, Audio, and Actuation modules have full code and specs but are deterministic simulations only. No real LoRa radios or hardware.

4. **Aegis storage is file-based despite docker-compose.** The `docker-compose.yml` defines PostgreSQL + Redis, but the actual runtime uses JSON files in `.aegis-data/`. The database migrations in `db/` exist but aren't actively used.

5. **Mode thresholds differ between services.** Cognitive Sensor uses `open_loops > 20` for CLOSURE. Delta Kernel uses `open_loops >= 4`. Both are "correct" for their contexts — be aware of the divergence.

6. **Windows-only automation.** All scripts are `.ps1` / `.bat`. No Unix equivalents exist.

7. **`results.db` is 107 MB and git-ignored.** It contains all conversation data and embeddings. You need this file for the cognitive pipeline to work. It won't exist on a fresh clone.

---

## Running Tests

```powershell
# Delta Kernel — 4 proof tests
cd services/delta-kernel
npm run test

# Cognitive Sensor
cd services/cognitive-sensor
python -m pytest tests/

# Aegis Fabric
cd services/aegis-fabric
npm run test
```

---

## Repo Layout (quick reference)

```
Pre Atlas/
├── services/
│   ├── delta-kernel/        # TypeScript state engine (port 3001)
│   ├── cognitive-sensor/    # Python analysis pipeline
│   └── aegis-fabric/        # TypeScript policy gate (port 3002)
├── contracts/schemas/       # 16 JSON Schema data contracts
├── scripts/                 # PowerShell launchers
├── data/                    # Runtime artifacts (projections)
├── .delta-fabric/           # Shared state (entities + deltas)
├── apps/                    # WebOS-333, Blueprint Generator (peripheral)
└── research/                # UASC-M2M symbolic encoding (research)
```

The three services under `services/` are the system. Everything else is supporting infrastructure, documentation, or peripheral projects.
