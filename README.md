# Atlas

A personal behavioral governance system built as a federated monorepo. Atlas ingests 5 life signals (sleep, open loops, assets shipped, deep work, money delta), routes you through 6 deterministic modes, and enforces execution discipline through conversation analysis, cron-driven governance, and a CLI that both humans and AI agents can operate.

## Services

| Service | Stack | Port | Purpose |
|---------|-------|------|---------|
| **delta-kernel** | TypeScript / Express / SQLite | 3001 | Deterministic Markov routing engine. 6 modes, governance daemon (9 cron jobs), Atlas AI CLI (50+ commands), REST API + SSE streaming |
| **cognitive-sensor** | Python / SQLite | -- | 16-script refresh pipeline. Conversation analysis, CycleBoard brain wiring, governance config as code (`atlas_config.py`), prediction engine |
| **inPACT** | HTML / JS | 3006 | Personal methodology product (today / method / followup) |
| **code-converter** | Python / FastAPI | 3007 | Python-to-C++ transpiler with AST engine and execution verifier |
| **blueprint-generator** | Next.js | 3030 | Project blueprint generation |
| **aegis-fabric** | -- | -- | Security and policy fabric |
| **mosaic-orchestrator** | Python / FastAPI | 3005 | Multi-service orchestration layer |
| **UASC executor** | Python / HTTP | 3008 | Deterministic command execution engine (7 commands, HMAC auth) |
| **cortex** | Python / FastAPI | 3009 | Autonomous execution layer (planner / executor / reviewer) |
| **mirofish** | Python / FastAPI | 3003 | Prediction engine (pending merge into cognitive-sensor) |
| **openclaw** | Python / FastAPI | 3004 | Utility service (25 tests) |

## Modes

The routing engine cycles through 6 modes based on signal thresholds:

```
RECOVER -> CLOSURE -> MAINTENANCE -> BUILD -> COMPOUND -> SCALE
```

Each mode gates what kind of work is permitted. CLOSURE blocks new projects until open loops drop. BUILD unlocks creation. COMPOUND and SCALE require sustained output before activating.

## Repo Structure

```
Pre Atlas/
  services/
    delta-kernel/          # Core engine (TypeScript)
    cognitive-sensor/      # Analysis pipeline (Python)
    crucix/                # Submodule
  apps/
    inpact/                # Methodology product
    code-converter/        # Transpiler
  contracts/
    schemas/               # JSON Schema (draft-07) data contracts
  scripts/                 # PowerShell launchers
  .delta-fabric/           # Local state data
```

## Quickstart

```powershell
# Start the full stack
.\scripts\run_all.ps1

# Or run services individually
cd services/delta-kernel
npm install
npm run api                # REST API on :3001

# Cognitive sensor refresh
python services/cognitive-sensor/refresh.py

# Atlas CLI (human)
npx ts-node services/delta-kernel/src/cli/atlas.ts

# Atlas AI CLI (agent-native, JSON output)
npx ts-node services/delta-kernel/src/cli/atlas-ai.ts
```

## Key API Endpoints

```
GET  /api/state                  Current system state
PUT  /api/state                  Update state
POST /api/ingest/cognitive       Ingest cognitive metrics
GET  /api/governance/config      Governance config (from atlas_config.py)
GET  /api/tasks                  List tasks
POST /api/tasks                  Create task
```

## Documentation

- `PRE_ATLAS_MAP.md` -- Full system architecture
- `services/delta-kernel/specs/` -- 19 specification documents
- `contracts/schemas/` -- 17 JSON Schema contracts
