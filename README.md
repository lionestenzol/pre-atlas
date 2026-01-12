# Pre Atlas

A personal operating system stack for behavioral governance through conversation analysis and deterministic state management.

## Quick Start

```powershell
# Run full stack (Delta API + Cognitive Sensor + Daily Projection)
.\scripts\run_all.ps1

# Individual services
.\scripts\run_cognitive.ps1    # Cognitive analysis only
.\scripts\run_delta_api.ps1    # Delta API on :3001
.\scripts\run_delta_cli.ps1    # Interactive CLI
```

## What It Does

1. **Analyzes** your conversation history (93k+ messages)
2. **Detects** open loops (unfinished projects/conversations)
3. **Computes** a daily mode based on cognitive load
4. **Routes** you to close loops before starting new things

### Modes

| Mode | Trigger | Effect |
|------|---------|--------|
| `CLOSURE` | closure ratio < 15% or > 20 loops | Blocks new projects |
| `MAINTENANCE` | 10-20 open loops | Can build, review first |
| `BUILD` | ≤ 10 loops, healthy closure | Create freely |

## Structure

```
Pre-Atlas/
├── services/
│   ├── delta-kernel/        # Deterministic state engine (TypeScript)
│   └── cognitive-sensor/    # Conversation analysis & routing (Python)
├── apps/
│   └── webos-333/           # Browser-based OS simulator (HTML)
├── research/
│   └── uasc-m2m/            # Symbolic encoding research
├── contracts/
│   └── schemas/             # Shared JSON Schema contracts
├── data/
│   └── projections/         # Daily projection artifacts
├── scripts/                 # PowerShell launchers
└── .delta-fabric/           # Local state data (repo-local)
```

## Pipeline (`run_all.ps1`)

```
[1/4] Delta API        → http://localhost:3001
[2/4] Cognitive Sensor → cognitive_state.json
[3/4] Daily Projection → data/projections/today.json
[4/4] Push to Delta    → POST /api/ingest/cognitive
```

## Services

### Delta Kernel (`services/delta-kernel`)

Deterministic state engine with hash-chain verification.

```bash
cd services/delta-kernel
npm install      # First time
npm run start    # Interactive CLI
npm run api      # REST API on :3001
```

**API Endpoints:**
- `GET /api/state` — Current system state
- `PUT /api/state` — Update state
- `POST /api/ingest/cognitive` — Ingest cognitive metrics
- `GET /api/tasks` — List tasks
- `POST /api/tasks` — Create task

### Cognitive Sensor (`services/cognitive-sensor`)

Analyzes conversation history to detect patterns and compute directives.

```bash
python services/cognitive-sensor/refresh.py
```

**Outputs:**
- `cognitive_state.json` — Metrics snapshot
- `daily_directive.txt` — Mode and action
- `cycleboard/brain/daily_payload.json` — CycleBoard data

## Contracts

JSON Schema definitions in `/contracts/schemas/`:

| Schema | Purpose |
|--------|---------|
| `DailyPayload.v1.json` | CycleBoard UI consumption |
| `CognitiveMetricsComputed.json` | Analysis output format |
| `DirectiveProposed.json` | Routing decision format |
| `DailyProjection.v1.json` | Combined daily artifact |

All exports are **contract-validated** before writing.

## Data Locations

| Data | Location |
|------|----------|
| Delta state | `.delta-fabric/` (repo-local) |
| Conversation DB | `services/cognitive-sensor/results.db` |
| Daily projection | `data/projections/today.json` |
| CycleBoard payload | `services/cognitive-sensor/cycleboard/brain/daily_payload.json` |

## Documentation

- `PRE_ATLAS_MAP.md` — Full system architecture
- `CONTEXT_PACKET.md` — LLM handoff context
- `services/delta-kernel/specs/` — 18 specification documents
