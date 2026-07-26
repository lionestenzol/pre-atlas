# Mosaic Platform

Unified behavioral governance platform — 6 federated services coordinated by a single orchestrator.

## Architecture

```
                      ┌──────────────┐
                      │   Dashboard  │ :3000  (Next.js)
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ Orchestrator │ :3005  (FastAPI)
                      └──┬──┬──┬──┬──┘
           ┌─────────────┘  │  │  └─────────────┐
    ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
    │ Delta Kernel│  │Aegis Fabric │  │  MiroFish  │  │  OpenClaw   │
    │    :3001    │  │    :3002    │  │    :3003   │  │    :3004    │
    │  (Express)  │  │  (Express)  │  │  (FastAPI) │  │  (FastAPI)  │
    └─────────────┘  └──────┬──────┘  └─────┬──────┘  └─────────────┘
                     ┌──────┴──────┐  ┌─────┴──────┐
                     │  Postgres   │  │   Neo4j    │
                     │   + Redis   │  │  + Ollama  │
                     └─────────────┘  └────────────┘
```

Cognitive Sensor (Python CLI) runs as a subprocess via the Orchestrator.

## Services

| Port | Service | Language | Purpose |
|------|---------|----------|---------|
| 3000 | mosaic-dashboard | TypeScript/Next.js | Web UI with 5 panels |
| 3001 | delta-kernel | TypeScript/Express | Deterministic state engine + governance daemon |
| 3002 | aegis-fabric | TypeScript/Express | Policy engine + agent approval |
| 3003 | mirofish | Python/FastAPI | Swarm simulation (20-agent debates) |
| 3004 | openclaw | Python/FastAPI | Multi-channel messaging gateway |
| 3005 | mosaic-orchestrator | Python/FastAPI | Coordination, workflows, metering |

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# 2. Start everything
docker compose up -d

# 3. Seed demo data
./seed-mosaic.sh

# 4. Open dashboard
open http://localhost:3000
```

Or use the automated installer:
```bash
./installer.sh
```

## Workflows

- **Daily Loop** — `POST /api/v1/workflows/daily` — Runs cognitive pipeline, pushes state to delta-kernel
- **Stall Detector** — `POST /api/v1/workflows/stall-check` — Detects 48h task stalls, notifies via OpenClaw
- **Idea Simulation** — `POST /api/v1/workflows/idea-simulation` — Routes high-alignment ideas to MiroFish

## Metering

- **Usage** — `GET /api/v1/metering/usage` — AI seconds consumed, free tier remaining
- **Pause** — `POST /api/v1/metering/pause` — Toggle AI processing pause

Free tier: 3600 seconds (1 hour). Tracks Claude API and Ollama usage.

## Development

```bash
# Run individual services
cd services/delta-kernel && npx tsx src/cli/index.ts
cd services/mosaic-orchestrator && python -m mosaic.main
cd services/mosaic-dashboard && npm run dev

# Run tests
cd services/mosaic-orchestrator && pytest tests/ -v
cd services/mosaic-dashboard && npm test
```

## Schemas

19 JSON Schema (draft-07) contracts in `contracts/schemas/`:
- MeteringUsage.v1.json, WorkflowEvent.v1.json (metering)
- ModeContract.v1.json, DailyPayload.v1.json (state)
- OrchestratorEvent.v1.json, TaskExecution.v1.json (orchestration)
- SimulationReport.v1.json (MiroFish)
- Aegis*.v1.json (7 policy schemas)
