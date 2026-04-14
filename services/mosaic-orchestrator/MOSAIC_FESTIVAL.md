# Mosaic Festival — Execution Blueprint

## For Next Session

Run this sequence:
1. `/fest create` with the structure below
2. `/weapon services/mosaic-orchestrator` — weapon reads the festival, picks up at Phase 2

Phase 1 is ALREADY COMPLETE. All files exist at `services/mosaic-orchestrator/src/mosaic/`. Mark Phase 1 tasks as done when creating.

---

## Festival Structure

```
Festival: mosaic-platform
Goal: Unify Pre Atlas systems into a single orchestration platform with swarm simulation, multi-channel messaging, unified dashboard, and AI task execution.

PHASE 001_ORCHESTRATOR_CORE (implementation) — ALREADY COMPLETE
  Sequence 01_scaffold
    Task 01: Create package scaffold (pyproject.toml, __init__.py, config.py, main.py, api.py)
    Task 02: Build delta-kernel client (delta_client.py)
    Task 03: Build cognitive-sensor client (cognitive_client.py)
    Task 04: Build aegis client (aegis_client.py)
    Task 05: Build festival client (festival_client.py)
    Task 06: Build claude adapter (claude_adapter.py)
    Task 07: Add schema contracts (OrchestratorEvent.v1.json, TaskExecution.v1.json)

PHASE 002_MIROFISH (implementation)
  Sequence 01_infrastructure
    Task 01: Create mirofish package scaffold (services/mirofish/, pyproject.toml, FastAPI on :3003)
    Task 02: Write docker-compose.yml for Neo4j + Ollama
    Task 03: Create SimulationReport.v1.json schema contract
  Sequence 02_knowledge_graph
    Task 01: Build document chunker + Ollama embedder (graph/ingester.py)
    Task 02: Build entity/relation extractor using qwen2.5:32b
    Task 03: Build Neo4j writer (nodes: Concept/Person/Argument/Evidence/Claim, edges: SUPPORTS/CONTRADICTS/RELATED_TO/AUTHORED_BY)
  Sequence 03_swarm
    Task 01: Build agent personality generator (swarm/personality.py) — 100-500 profiles with archetypes
    Task 02: Build simulation runner (swarm/simulator.py) — Twitter/Reddit platform, 10-50 ticks, max 4 parallel Ollama calls
    Task 03: Build report generator (reports/generator.py) — predictions, consensus map, recommended actions
  Sequence 04_api
    Task 01: Build REST API (api.py) — POST /simulations, GET /simulations/{id}, GET .../report, DELETE, GET /health
    Task 02: Verify end-to-end: submit test doc → Neo4j nodes → simulation → report validates against schema

PHASE 003_OPENCLAW (implementation)
  Sequence 01_channels
    Task 01: Create openclaw package scaffold (services/openclaw/, FastAPI on :3004)
    Task 02: Build channel abstraction (channels/base.py — send_message, register_command, start, stop)
    Task 03: Build Telegram channel implementation
    Task 04: Build Slack channel implementation
    Task 05: Build Discord channel implementation
  Sequence 02_skills
    Task 01: Build /status skill (calls orchestrator → returns mode + lanes + festival)
    Task 02: Build /brief skill (reads daily_brief.md, formats for channel)
    Task 03: Build /fest skill (proxy to festival CLI)
    Task 04: Build /simulate skill (triggers MiroFish)
    Task 05: Build /approve skill (Aegis approval queue)
  Sequence 03_scheduler
    Task 01: Build daily cron (9:30 AM post brief, CLOSURE stall detection)
    Task 02: Build REST API (POST /notify, GET /channels, GET /health)
    Task 03: Create config.yaml template (env var tokens, channel IDs)

PHASE 004_DASHBOARD (implementation)
  Sequence 01_scaffold
    Task 01: Create Next.js app (services/mosaic-dashboard/, TypeScript + Tailwind, port 3000)
    Task 02: Build API proxy layer (Next.js routes → :3001, :3003, :3005)
  Sequence 02_panels
    Task 01: Build Mode & Governance Panel (color-coded mode, lanes, countdown, poll 30s)
    Task 02: Build Festival Manager Panel (progress, task list, Execute Next button, cut list)
    Task 03: Build Simulation Panel (upload doc, progress bar, D3.js consensus viz)
    Task 04: Build Atlas Clusters View (Plotly scatter — alignment vs effort)
    Task 05: Build AI Usage Counter (live seconds, pause button)

PHASE 005_WORKFLOWS_METERING (implementation)
  Sequence 01_workflows
    Task 01: Build idea-to-simulation workflow (alignment > 0.7 → MiroFish → confidence routing)
    Task 02: Build stall detector (48h no completion → cut list → OpenClaw)
    Task 03: Build daily automation loop (6AM state → 6:05 atlas daily → 6:15 push → 9:30 brief → continuous dispatch → 10PM summary)
  Sequence 02_metering
    Task 01: Build metering module (SQLite ~/.mosaic/metering.db, usage_log table)
    Task 02: Wire metering into Claude adapter and MiroFish calls
    Task 03: Build metering endpoints (GET /usage, POST /pause)
    Task 04: Add MeteringUsage.v1.json + WorkflowEvent.v1.json schemas

PHASE 006_INSTALLER (implementation)
  Sequence 01_docker
    Task 01: Write root docker-compose.yml (10 services, mosaic-net, health checks)
    Task 02: Write Dockerfiles for all 6 app services
    Task 03: Write .env.example with all tokens/keys/passwords
  Sequence 02_installer
    Task 01: Write installer.sh (detect OS, Docker, Ollama models, .env, compose up, health wait, print URL)
    Task 02: Write Aegis seed script (seed-mosaic.sh — tenant, agents, policies)
    Task 03: Write MOSAIC_README.md + update PRE_ATLAS_MAP.md
```

---

## Existing Files (Phase 1 — DO NOT REBUILD)

```
services/mosaic-orchestrator/
  pyproject.toml
  src/mosaic/
    __init__.py
    main.py           — uvicorn entry point on :3005
    api.py            — FastAPI (health, status, tasks, metering, workflows)
    config.py         — env-based config (all URLs, keys, paths)
    clients/
      delta_client.py      — 9 endpoints wrapped, retry logic
      cognitive_client.py  — 4 CLI commands + 4 file readers
      aegis_client.py      — actions, approvals, health
      festival_client.py   — WSL2 fest commands
    adapters/
      claude_adapter.py    — Claude API + Ollama fallback
    workflows/             — empty (Phase 5)
    metering/              — empty (Phase 5)

contracts/schemas/
  OrchestratorEvent.v1.json
  TaskExecution.v1.json
```

---

## Port Map

| Service | Port |
|---------|------|
| mosaic-dashboard | 3000 |
| delta-kernel | 3001 (EXISTS) |
| aegis-fabric | 3002 (EXISTS) |
| mirofish | 3003 |
| openclaw | 3004 |
| orchestrator | 3005 |
| delta-web | 5173 (EXISTS) |
| PostgreSQL | 5432 (EXISTS) |
| Redis | 6379 (EXISTS) |
| Neo4j | 7474/7687 |
| Ollama | 11434 |

---

## Constraints
- All processing local (no data leaves machine)
- Docker Compose for MiroFish (Neo4j, Ollama) and OpenClaw
- Existing code NOT rewritten — new components wrap existing APIs
- delta-kernel POST /api/ingest/cognitive is the Python→TypeScript bridge
- Ollama 32b needs ~20GB VRAM; fallback to 7b if unavailable
- Minimum 16GB RAM, 50GB disk
