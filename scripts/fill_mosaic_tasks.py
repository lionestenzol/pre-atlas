"""Fill all task content files for Mosaic festival Phase 002 (MiroFish)."""
import subprocess
import tempfile
import os

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def write_wsl(path, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cp '{wsl_tmp}' '{path}'"],
                   capture_output=True, text=True)
    os.unlink(tmp)
    print(f"  Wrote: {path.split('/')[-1]}")

# ============================================================
# FESTIVAL_GOAL.md
# ============================================================
print("=== FESTIVAL_GOAL.md ===")
write_wsl(f"{FEST_DIR}/FESTIVAL_GOAL.md", """# Festival Goal: Mosaic Integration Platform

## Objective
Unify Pre Atlas systems (Delta-Kernel, Cognitive-Sensor, Aegis-Fabric, Festival) into a single orchestration platform with swarm simulation (MiroFish), multi-channel messaging (OpenClaw), a unified dashboard, and AI task execution with metering.

## Success Criteria
- [ ] All 6 services running and communicating via REST APIs
- [ ] MiroFish: document → knowledge graph → agent swarm → prediction report (< 10min)
- [ ] OpenClaw: daily briefs posted to Telegram, commands work
- [ ] Dashboard: unified view at http://localhost:3000
- [ ] Metering: AI usage tracking with pause/resume
- [ ] One-command deployment via Docker Compose

## Constraints
- All processing local (no data leaves machine)
- Existing code NOT rewritten — new components wrap existing APIs
- Ollama 32b needs ~20GB VRAM; fallback to 7b if unavailable
- Minimum 16GB RAM, 50GB disk

## Port Map
| Service | Port |
|---------|------|
| mosaic-dashboard | 3000 |
| delta-kernel | 3001 (EXISTS) |
| aegis-fabric | 3002 (EXISTS) |
| mirofish | 3003 |
| openclaw | 3004 |
| orchestrator | 3005 (EXISTS) |
| Neo4j | 7474/7687 |
| Ollama | 11434 |
""")

# ============================================================
# Phase 001 PHASE_GOAL.md
# ============================================================
print("=== Phase 001 PHASE_GOAL.md ===")
write_wsl(f"{FEST_DIR}/001_ORCHESTRATOR_CORE/PHASE_GOAL.md", """# Phase Goal: Orchestrator Core + Claude Adapter

## Status: COMPLETE

All deliverables exist at `services/mosaic-orchestrator/src/mosaic/`.

## Deliverables (Done)
- [x] Package scaffold (pyproject.toml, FastAPI on :3005)
- [x] Delta-Kernel client (9 endpoints, retry logic)
- [x] Cognitive-Sensor client (4 CLI commands, 4 file readers)
- [x] Aegis client (actions, approvals, health)
- [x] Festival client (WSL2 fest commands)
- [x] Claude adapter (Anthropic API + Ollama fallback)
- [x] Schema contracts (OrchestratorEvent.v1.json, TaskExecution.v1.json)
""")

# ============================================================
# Phase 002 PHASE_GOAL.md
# ============================================================
print("=== Phase 002 PHASE_GOAL.md ===")
write_wsl(f"{FEST_DIR}/002_MIROFISH/PHASE_GOAL.md", """# Phase Goal: MiroFish Swarm Engine

## Objective
Build a swarm simulation engine that ingests documents into a Neo4j knowledge graph, generates agent personalities, runs tick-based multi-agent simulations via Ollama, and produces prediction reports.

## Deliverables
- [ ] `services/mirofish/` — FastAPI on port 3003
- [ ] Docker Compose with Neo4j (7474/7687) + Ollama (11434)
- [ ] Knowledge graph ingester (chunk → embed → extract → Neo4j)
- [ ] Agent personality generator (100-500 profiles)
- [ ] Simulation runner (10-50 ticks, max 4 parallel Ollama)
- [ ] Report generator (predictions, consensus, actions)
- [ ] REST API (POST /simulations, GET, DELETE, /health)
- [ ] SimulationReport.v1.json schema contract

## Verification
Submit test markdown → Neo4j nodes visible → 10-tick simulation with 20 agents → report validates against schema. Target: < 10min for 5-page doc, 50 agents.

## Risk
Ollama 32b needs ~20GB VRAM → fallback to qwen2.5:7b with quality degradation flag.
""")

# ============================================================
# Phase 002 TASK FILES
# ============================================================
P2 = f"{FEST_DIR}/002_MIROFISH"

# --- Seq 01: infrastructure ---
print("=== Seq 01: infrastructure ===")

write_wsl(f"{P2}/01_infrastructure/01_create_mirofish_scaffold.md", """# Task: Create MiroFish Package Scaffold

## Objective
Create the `services/mirofish/` Python package with FastAPI on port 3003.

## Requirements
- Mirror mosaic-orchestrator structure (pyproject.toml, src/mirofish/)
- FastAPI with uvicorn entry point
- Config from environment variables (NEO4J_URI, OLLAMA_URL, etc.)
- Health endpoint at GET /api/v1/health

## Implementation Steps
1. Create `services/mirofish/` directory
2. Create `pyproject.toml` with deps: fastapi, uvicorn, neo4j, httpx, pydantic, structlog
3. Create `src/mirofish/__init__.py` (version 0.1.0)
4. Create `src/mirofish/config.py` — MirofishConfig dataclass (neo4j_uri, neo4j_user, neo4j_password, ollama_url, ollama_model, ollama_embed_model, port)
5. Create `src/mirofish/main.py` — uvicorn entrypoint
6. Create `src/mirofish/api.py` — FastAPI app with /api/v1/health endpoint
7. Verify: `cd services/mirofish && pip install -e . && python -m mirofish.main` responds at localhost:3003

## Definition of Done
- [ ] services/mirofish/ exists with pyproject.toml
- [ ] FastAPI starts on port 3003
- [ ] GET /api/v1/health returns 200
- [ ] Config reads from env vars with sensible defaults
""")

write_wsl(f"{P2}/01_infrastructure/01_write_docker_compose.md", """# Task: Write Docker Compose for Neo4j + Ollama

## Objective
Create docker-compose.yml for MiroFish's infrastructure dependencies.

## Requirements
- Neo4j 5 Community Edition on ports 7474 (HTTP) / 7687 (Bolt)
- Ollama with GPU passthrough on port 11434
- Volume persistence for both services
- Health checks

## Implementation Steps
1. Create `services/mirofish/docker-compose.yml`
2. Add neo4j service: image neo4j:5-community, ports 7474:7474 + 7687:7687, volume neo4j_data, env NEO4J_AUTH=neo4j/mirofish123
3. Add ollama service: image ollama/ollama, port 11434:11434, volume ollama_data, deploy.resources.reservations.devices for GPU
4. Add .env.example with all config vars
5. Test: `docker compose up -d` → both services healthy
6. Pull required models: `docker exec ollama ollama pull qwen2.5:32b` and `ollama pull nomic-embed-text`

## Definition of Done
- [ ] docker-compose.yml starts Neo4j and Ollama
- [ ] Neo4j accessible at bolt://localhost:7687
- [ ] Ollama accessible at http://localhost:11434
- [ ] .env.example documents all variables
""")

write_wsl(f"{P2}/01_infrastructure/01_create_simulation_report_schema.md", """# Task: Create SimulationReport Schema Contract

## Objective
Define the JSON Schema for MiroFish simulation reports.

## Requirements
- Follow existing schema patterns (contracts/schemas/*.v1.json, JSON Schema draft-07)
- Include schema_version field
- Cover all report fields from the plan

## Implementation Steps
1. Create `contracts/schemas/SimulationReport.v1.json`
2. Define properties:
   - simulation_id (string, required)
   - schema_version (string, "1.0")
   - topic (string)
   - agent_count (integer)
   - tick_count (integer)
   - duration_seconds (number)
   - summary (string — executive summary)
   - key_insights (array of strings)
   - consensus_points (array of {claim, confidence, supporting_agents})
   - dissent_points (array of {claim, agents_for, agents_against})
   - recommendations (array of {action, priority, rationale})
   - agent_contributions (array of {agent_id, archetype, message_count, influence_score})
   - created_at (string, date-time)
3. Validate with jsonschema library

## Definition of Done
- [ ] SimulationReport.v1.json exists in contracts/schemas/
- [ ] Follows draft-07 format
- [ ] All fields documented with descriptions
""")

# --- Seq 02: knowledge_graph ---
print("=== Seq 02: knowledge_graph ===")

write_wsl(f"{P2}/02_knowledge_graph/01_build_document_chunker_and_embedder.md", """# Task: Build Document Chunker + Ollama Embedder

## Objective
Create the document ingestion pipeline: chunk text documents and generate embeddings via Ollama.

## Requirements
- Chunk documents into ~500 token segments with overlap
- Generate embeddings using Ollama nomic-embed-text model
- Batch embedding support for efficiency
- Reuse Ollama connection pattern from claude_adapter.py

## Implementation Steps
1. Create `src/mirofish/graph/__init__.py`
2. Create `src/mirofish/graph/chunker.py`:
   - `chunk_document(text: str, chunk_size=500, overlap=50) -> list[Chunk]`
   - Chunk dataclass: text, start_pos, end_pos, index
3. Create `src/mirofish/graph/embedder.py`:
   - `OllamaEmbedder` class with async httpx client
   - `embed(text: str) -> list[float]` — POST to /api/embeddings
   - `embed_batch(texts: list[str]) -> list[list[float]]`
   - Config: ollama_url from MirofishConfig, model=nomic-embed-text
4. Add retry logic (2 attempts, exponential backoff) matching mosaic-orchestrator pattern
5. Test with sample text document

## Definition of Done
- [ ] chunker.py splits documents into overlapping chunks
- [ ] embedder.py generates embeddings via Ollama
- [ ] Batch embedding works for 10+ chunks
- [ ] Retry logic handles transient Ollama failures
""")

write_wsl(f"{P2}/02_knowledge_graph/01_build_entity_relation_extractor.md", """# Task: Build Entity/Relation Extractor

## Objective
Extract entities and relationships from document chunks using Ollama qwen2.5:32b.

## Requirements
- Extract 5 node types: Concept, Person, Argument, Evidence, Claim
- Extract 4 edge types: SUPPORTS, CONTRADICTS, RELATED_TO, AUTHORED_BY
- Use structured output prompting with qwen2.5:32b
- Fallback to qwen2.5:7b if 32b unavailable

## Implementation Steps
1. Create `src/mirofish/graph/extractor.py`
2. Define extraction prompt template:
   - System: "Extract entities and relationships from the following text. Return JSON."
   - Expected output: {entities: [{name, type, description}], relationships: [{source, target, type, evidence}]}
3. Implement `EntityExtractor` class:
   - `extract(chunk: str) -> ExtractionResult` — POST to Ollama /api/generate
   - Parse JSON response, validate structure
   - Handle malformed JSON gracefully (retry with simpler prompt)
4. Add model fallback: try qwen2.5:32b → qwen2.5:7b
5. Test with sample document chunk

## Definition of Done
- [ ] Extracts entities with correct types
- [ ] Extracts relationships between entities
- [ ] Handles Ollama model fallback
- [ ] Graceful error handling for malformed responses
""")

write_wsl(f"{P2}/02_knowledge_graph/01_build_neo4j_writer.md", """# Task: Build Neo4j Writer

## Objective
Write extracted entities and relationships to Neo4j graph database.

## Requirements
- Async Neo4j driver with connection pool
- Create/merge nodes: Concept, Person, Argument, Evidence, Claim
- Create/merge edges: SUPPORTS, CONTRADICTS, RELATED_TO, AUTHORED_BY
- Store embeddings as node properties for vector search
- Idempotent: re-ingesting same doc updates rather than duplicates

## Implementation Steps
1. Create `src/mirofish/graph/neo4j_client.py`
2. Implement `Neo4jClient` class:
   - `__init__(uri, user, password)` — async driver
   - `ensure_schema()` — create constraints (unique name+type), vector index on embeddings
   - `upsert_node(name, type, description, embedding) -> node_id`
   - `upsert_edge(source_id, target_id, type, evidence)`
   - `search_similar(embedding, limit=10) -> list[Node]` — vector similarity search
   - `get_neighbors(node_id, depth=1) -> Subgraph`
3. Create `src/mirofish/graph/ingester.py` — full pipeline:
   - `ingest_document(text: str)` — chunk → embed → extract → write to Neo4j
4. Add retry logic for Neo4j connection failures
5. Test: ingest sample doc, verify nodes/edges in Neo4j browser

## Definition of Done
- [ ] Nodes created with correct labels and properties
- [ ] Edges connect related entities
- [ ] Embeddings stored for vector search
- [ ] Re-ingestion is idempotent (MERGE not CREATE)
- [ ] Vector similarity search returns relevant nodes
""")

# --- Seq 03: swarm ---
print("=== Seq 03: swarm ===")

write_wsl(f"{P2}/03_swarm/01_build_agent_personality_generator.md", """# Task: Build Agent Personality Generator

## Objective
Generate diverse agent personalities for swarm simulations using Ollama.

## Requirements
- 100-500 agent profiles per simulation
- Each profile: archetype, knowledge_subset, behavior_weights, communication_style
- Seeded randomness for reproducibility
- Minimum diversity (no duplicate archetypes in same simulation)

## Implementation Steps
1. Create `src/mirofish/swarm/__init__.py`
2. Create `src/mirofish/swarm/personality.py`
3. Define `AgentProfile` dataclass:
   - agent_id, name, archetype (str), knowledge_focus (list[str])
   - traits: {openness, agreeableness, assertiveness} (0.0-1.0)
   - communication_style: "academic" | "casual" | "provocative" | "analytical" | "skeptical"
   - goal: str (what this agent optimizes for)
4. Define base archetypes: Expert, Devil's Advocate, Synthesizer, Pragmatist, Visionary, Skeptic, Moderator
5. Implement `PersonalityGenerator`:
   - `generate(topic: str, count: int, seed: int) -> list[AgentProfile]`
   - Use Ollama to create varied personalities based on topic context
   - Ensure archetype diversity within a simulation
6. Test: generate 20 agents for "climate policy", verify diversity

## Definition of Done
- [ ] Generates agent profiles with all required fields
- [ ] Archetype diversity enforced
- [ ] Seeded generation produces reproducible results
- [ ] Profiles are contextually relevant to simulation topic
""")

write_wsl(f"{P2}/03_swarm/01_build_simulation_runner.md", """# Task: Build Simulation Runner

## Objective
Build the tick-based swarm simulation engine.

## Requirements
- Twitter/Reddit-like platform simulation
- 10-50 ticks per simulation
- Max 4 parallel Ollama requests per tick
- Hard caps: 500 agents, 50 ticks
- Each agent gets graph context + conversation history per tick

## Implementation Steps
1. Create `src/mirofish/swarm/simulator.py`
2. Define `SimulationConfig`: topic, agents (list[AgentProfile]), tick_count, parallel_factor=4
3. Define `Tick` dataclass: tick_number, messages (list[AgentMessage]), timestamp
4. Define `AgentMessage`: agent_id, content, reply_to (optional), sentiment, stance
5. Implement `SimulationRunner`:
   - `__init__(config, neo4j_client, ollama_url)`
   - `run() -> SimulationResult` — main loop
   - Per tick:
     a. Select active agents (not all agents post every tick)
     b. For each active agent, build prompt: personality + graph context + recent messages
     c. Call Ollama in parallel (asyncio.Semaphore(4))
     d. Parse responses into AgentMessages
     e. Track conversation thread
   - Store tick data incrementally
6. Create `src/mirofish/swarm/store.py` — SQLite persistence:
   - Tables: simulations, ticks, messages
   - `save_tick(sim_id, tick)`, `load_simulation(sim_id)`
7. Test: 10 agents, 5 ticks, verify messages generated

## Definition of Done
- [ ] Simulation runs for configured number of ticks
- [ ] Agents produce contextually relevant messages
- [ ] Parallel Ollama calls respect semaphore limit
- [ ] All tick data persisted to SQLite
- [ ] Hard caps enforced (500 agents, 50 ticks)
""")

write_wsl(f"{P2}/03_swarm/01_build_report_generator.md", """# Task: Build Report Generator

## Objective
Generate structured prediction reports from completed simulations.

## Requirements
- Use Ollama to synthesize simulation results
- Output validates against SimulationReport.v1.json schema
- Export as JSON and markdown
- Include consensus analysis, dissent mapping, recommendations

## Implementation Steps
1. Create `src/mirofish/reports/__init__.py`
2. Create `src/mirofish/reports/builder.py`
3. Implement `ReportBuilder`:
   - `build(simulation_result: SimulationResult) -> Report`
   - Analyze messages across all ticks for:
     a. Consensus points (claims most agents agree on)
     b. Dissent points (claims with strong disagreement)
     c. Key insights (novel or surprising contributions)
     d. Agent influence scores (who shifted the conversation)
   - Use Ollama to generate executive summary and recommendations
4. Create `src/mirofish/reports/export.py`:
   - `to_json(report) -> dict` — validates against SimulationReport.v1.json
   - `to_markdown(report) -> str` — human-readable format
5. Add CLI command: `python -m mirofish.cli report --simulation-id X`
6. Test: build report from test simulation, validate against schema

## Definition of Done
- [ ] Report generated from simulation data
- [ ] JSON output validates against SimulationReport.v1.json
- [ ] Markdown export is readable
- [ ] Consensus and dissent correctly identified
""")

# --- Seq 04: api ---
print("=== Seq 04: api ===")

write_wsl(f"{P2}/04_api/01_build_rest_api.md", """# Task: Build MiroFish REST API

## Objective
Implement FastAPI endpoints for MiroFish simulation management.

## Requirements
- POST /api/v1/simulations — start a new simulation
- GET /api/v1/simulations — list all simulations
- GET /api/v1/simulations/{id} — get simulation detail with tick data (incremental)
- GET /api/v1/simulations/{id}/report — get generated report
- DELETE /api/v1/simulations/{id} — delete simulation
- GET /api/v1/health — health check (already exists)

## Implementation Steps
1. Update `src/mirofish/api.py` with new routes
2. POST /api/v1/simulations:
   - Body: {topic, agent_count, tick_count, document_text (optional)}
   - If document_text: ingest into Neo4j first
   - Start simulation in background (asyncio.create_task)
   - Return {simulation_id, status: "running"}
3. GET /api/v1/simulations:
   - Return list of {simulation_id, topic, status, agent_count, tick_count, created_at}
4. GET /api/v1/simulations/{id}:
   - Return full simulation with tick data
   - Support ?from_tick=N for incremental polling
5. GET /api/v1/simulations/{id}/report:
   - Return SimulationReport.v1.json validated report
   - 404 if simulation not complete
6. DELETE /api/v1/simulations/{id}:
   - Remove from SQLite store
7. Add CORS middleware (allow all origins, matching orchestrator pattern)

## Definition of Done
- [ ] All 6 endpoints implemented and responding
- [ ] POST starts simulation in background
- [ ] GET returns incremental tick data
- [ ] Report validates against schema
- [ ] CORS enabled
""")

write_wsl(f"{P2}/04_api/01_verify_end_to_end.md", """# Task: Verify MiroFish End-to-End

## Objective
Run a complete end-to-end test: document → knowledge graph → simulation → report.

## Requirements
- Use a real test document (5+ paragraphs)
- Verify each stage independently
- Target: < 10 minutes for 5-page doc, 50 agents
- Report must validate against SimulationReport.v1.json

## Implementation Steps
1. Ensure Docker Compose is running (Neo4j + Ollama)
2. Start MiroFish: `python -m mirofish.main`
3. Submit test document via API:
   ```
   POST http://localhost:3003/api/v1/simulations
   {topic: "test topic", agent_count: 20, tick_count: 10, document_text: "..."}
   ```
4. Verify Neo4j nodes: open http://localhost:7474, run MATCH (n) RETURN n LIMIT 25
5. Poll simulation progress: GET /api/v1/simulations/{id}?from_tick=0
6. Wait for completion, then fetch report: GET /api/v1/simulations/{id}/report
7. Validate report JSON against SimulationReport.v1.json schema
8. Check timing: entire pipeline should complete in < 10 minutes
9. Wire orchestrator integration:
   - Add MirofishClient to mosaic-orchestrator/src/mosaic/clients/
   - Test: orchestrator can start and poll simulations

## Definition of Done
- [ ] Document ingested, Neo4j nodes visible
- [ ] Simulation completes with 20 agents, 10 ticks
- [ ] Report validates against schema
- [ ] Total time < 10 minutes
- [ ] Orchestrator can reach MiroFish API
""")

# ============================================================
# Phase 003-006 PHASE_GOAL.md files
# ============================================================
print("=== Phase 003-006 PHASE_GOAL.md files ===")

write_wsl(f"{FEST_DIR}/003_OPENCLAW/PHASE_GOAL.md", """# Phase Goal: OpenClaw Multi-Channel Gateway

## Objective
Build multi-channel messaging gateway for daily briefs and commands via Telegram, Slack, Discord.

## Deliverables
- [ ] `services/openclaw/` — FastAPI on port 3004
- [ ] Channel abstraction (base.py — send_message, register_command, start, stop)
- [ ] Telegram, Slack, Discord channel implementations
- [ ] Skill system: /status, /brief, /fest, /simulate, /approve
- [ ] Daily cron (9:30 AM brief, CLOSURE stall detection)
- [ ] REST API (POST /notify, GET /channels, GET /health)
- [ ] Config template (env var tokens)
""")

write_wsl(f"{FEST_DIR}/004_DASHBOARD/PHASE_GOAL.md", """# Phase Goal: Mosaic Web Dashboard

## Objective
Build unified Next.js + Tailwind dashboard on port 3000.

## Deliverables
- [ ] `services/mosaic-dashboard/` — Next.js + TypeScript + Tailwind
- [ ] API proxy layer (routes to :3001, :3003, :3005)
- [ ] Mode & Governance Panel (color-coded, lanes, countdown, poll 30s)
- [ ] Festival Manager Panel (progress, task list, Execute Next, cut list)
- [ ] Simulation Panel (upload doc, progress bar, D3.js consensus viz)
- [ ] Atlas Clusters View (Plotly scatter — alignment vs effort)
- [ ] AI Usage Counter (live seconds, pause button)
""")

write_wsl(f"{FEST_DIR}/005_WORKFLOWS_METERING/PHASE_GOAL.md", """# Phase Goal: Orchestrator Workflows + Metering

## Objective
Wire end-to-end automation and pay-as-you-go metering into the orchestrator.

## Deliverables
- [ ] Idea-to-simulation workflow (alignment > 0.7 → MiroFish → confidence routing)
- [ ] Stall detector (48h no completion → cut list → OpenClaw)
- [ ] Daily loop (6AM→10PM automation cycle)
- [ ] Metering module (SQLite, usage_log, free tier 3600s, pause/resume)
- [ ] Metering endpoints (GET /usage, POST /pause)
- [ ] MeteringUsage.v1.json + WorkflowEvent.v1.json schemas
""")

write_wsl(f"{FEST_DIR}/006_INSTALLER/PHASE_GOAL.md", """# Phase Goal: Installer + Hardening

## Objective
One-command deployment for the entire Mosaic platform.

## Deliverables
- [ ] Root docker-compose.yml (10 services, mosaic-net, health checks)
- [ ] Dockerfiles for 6 app services
- [ ] .env.example with all tokens/keys/passwords
- [ ] installer.sh (detect OS, Docker, Ollama models, compose up, health wait)
- [ ] Aegis seed script (seed-mosaic.sh — tenant, agents, policies)
- [ ] MOSAIC_README.md + updated PRE_ATLAS_MAP.md
""")

print("\n=== ALL TASK CONTENT WRITTEN ===")
