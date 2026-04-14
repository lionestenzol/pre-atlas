# Pre Atlas Backend Audit

> Generated from codebase analysis on 2026-04-05
> Covers all 7 backend services, 17+ data contracts, and inter-service data flows

---

## 1. Executive Summary

Pre Atlas is a federated monorepo containing 7 microservices that form a personal behavioral governance system. The backend handles cognitive state inference, deterministic mode routing, policy enforcement, work queue management, prediction, and multi-channel notifications.

```
TECH STACK
------------------------------------------------------------
Language        | Services
------------------------------------------------------------
TypeScript/Node | delta-kernel (Express), aegis-fabric (Express)
Python/FastAPI  | mirofish, mosaic-orchestrator, openclaw
Python/CLI      | cognitive-sensor (subprocess-driven)
------------------------------------------------------------
Databases       | SQLite (delta, cognitive, aegis)
                | Neo4j (mirofish graph)
                | PostgreSQL (aegis-fabric optional)
------------------------------------------------------------
Schemas         | JSON Schema draft-07 (17+ contracts)
------------------------------------------------------------
```

```
PORT MAP
+---------+----------------------+------------+
| Port    | Service              | Tech       |
+---------+----------------------+------------+
| 3000    | mosaic-dashboard     | Next.js    |
| 3001    | delta-kernel         | Express/TS |
| 3002    | aegis-fabric         | Express/TS |
| 3003    | mirofish             | FastAPI/Py |
| 3004    | openclaw             | FastAPI/Py |
| 3005    | mosaic-orchestrator  | FastAPI/Py |
| 7687    | Neo4j                | Graph DB   |
| 11434   | Ollama               | LLM        |
+---------+----------------------+------------+
| (none)  | cognitive-sensor     | Python CLI |
+---------+----------------------+------------+
```

---

## 2. System Topology

```
                         +==========================+
                         |    MOSAIC ORCHESTRATOR    |
                         |       :3005 (Hub)        |
                         +==========================+
                          /    |     |     |      \
                HTTP     /     |     |     |       \    HTTP
                        /      |     |     |        \
            +----------+  +----+---+ | +----+----+ +--------+
            | DELTA    |  | AEGIS  | | | MIROFISH| | OPENCLAW|
            | KERNEL   |  | FABRIC | | |  :3003  | |  :3004  |
            |  :3001   |  |  :3002 | | +---------+ +---------+
            +----------+  +--------+ |   |               |
                 |              |     |   |Neo4j          |Telegram
                 | subprocess   |     |   |               |Slack
                 v              |     |   v               |Discord
            +----------+       |     | +--------+        |
            | COGNITIVE |      |     | | Neo4j  |        v
            | SENSOR    |------+     | | :7687  |   [Channels]
            | (Python)  |           |  +--------+
            +----------+           |
                 |                 |
           +-----+------+         |
           | results.db |         |
           | (SQLite)   |    +----+-----+
           +------------+    | Ollama   |
                             | :11434   |
                             +----------+

    +----------------------------------------------------------+
    |                    CONTRACTS/SCHEMAS                       |
    |  DailyPayload.v1 | ModeContract.v1 | AegisAgent.v1 | ... |
    +----------------------------------------------------------+
```

---

## 3. Service Catalog

---

### 3.1 DELTA-KERNEL (State Machine Backbone)

```
Port:        3001
Technology:  TypeScript / Express
Entry Point: services/delta-kernel/src/api/server.ts
Storage:     SQLite (WAL mode) at ~/.delta-fabric/
Auth:        Bearer token from .aegis-tenant-key (dev = no auth)
```

#### Internal Component Tree

```
services/delta-kernel/src/
+-- api/
|   +-- server.ts .................. Express server (1774 lines)
+-- cli/
|   +-- index.ts ................... CLI entry point
|   +-- app.ts ..................... CLI application logic
|   +-- renderer.ts ................ Terminal UI
|   +-- sqlite-storage.ts ......... SQLite storage implementation
+-- core/
|   +-- types.ts ................... Barrel re-export (types-core + extended + sync)
|   +-- types-core.ts .............. Entity, Delta, Mode, Risk, JsonPatch
|   +-- types-extended.ts .......... SystemStateData, TaskData, WorkLedger
|   +-- types-sync.ts .............. Sync protocol types
|   +-- routing.ts ................. Markov mode routing (LOCKED, deterministic)
|   +-- cockpit.ts ................. Risk tier calculation
|   +-- daily-screen.ts ............ Daily UI payload generation
|   +-- preparation.ts ............. Preparation engine
|   +-- templates.ts ............... Template rendering
|   +-- timeline-logger.ts ......... Event timeline (emit/query/getDay/getStats)
|   +-- work-controller.ts ......... Work queue orchestration
|   +-- vector-discovery.ts ........ Vector search for entities
|   +-- ai-design.ts ............... AI design constraints
|   +-- fabric-tests.ts ............ Internal tests
+-- governance/
|   +-- governance_daemon.ts ....... Autonomous scheduler (1142 lines, 9 cron jobs)
+-- ui/
|   +-- control.html ............... Work queue dashboard
|   +-- timeline.html .............. Event timeline dashboard
```

#### Key Modules & Exports

| Module | Key Exports | Purpose |
|--------|-------------|---------|
| `routing.ts` | `route()`, `bucketSleepHours()`, `bucketOpenLoops()`, `bucketAssetsShipped()`, `bucketDeepWorkBlocks()` | Deterministic mode transitions via Markov routing |
| `cockpit.ts` | `getEffectiveRiskTier()` | Risk calculation (LOW/MEDIUM/HIGH) |
| `timeline-logger.ts` | `emit()`, `query()`, `getDay()`, `getStats()` | Append-only event log |
| `work-controller.ts` | `requestWork()`, `completeWork()`, `getQueue()` | Work queue with max 1 concurrent job |
| `daily-screen.ts` | `getDailyScreen()` | Render daily cockpit payload |
| `preparation.ts` | `getPreparation()` | Preparation engine results |
| `vector-discovery.ts` | `search()` | Semantic entity search |

#### API Endpoints

```
HEALTH & SYSTEM
  GET  /api/health ........................ { ok, ts, version, service }
  GET  /api/stats ......................... Storage statistics
  GET  /api/daemon/status ................. { running, last_heartbeat, job_history }
  POST /api/daemon/run .................... Manually trigger job (heartbeat|refresh|day_start|day_end)

AUTHENTICATION
  GET  /api/auth/token .................... { ok, token } (localhost CORS-only)

STATE MANAGEMENT
  GET  /api/state ......................... Raw system state
  GET  /api/state/unified ................. Merged delta + cognitive state
  PUT  /api/state ......................... Update system state

ENTITY MANAGEMENT
  POST /api/entity ........................ Create entity { entity_type, initial_state }
  GET  /api/entity/:entity_id ............. Full entity + delta history
  PUT  /api/entity/:entity_id ............. Update entity { patch }

WORK QUEUE
  POST /api/work/request .................. Admit job { type, title, priority, timeout_ms }
  POST /api/work/complete ................. Finish job { job_id, outcome }
  GET  /api/work/queue .................... Active + queued jobs

COGNITIVE INGESTION
  POST /api/ingest/cognitive .............. Push DailyPayload.v1.json

TIMELINE
  GET  /api/timeline ...................... Query events { from, to, type, source, limit }
  GET  /api/timeline/stats ................ Event statistics
  GET  /api/timeline/day/:date ............ All events for YYYY-MM-DD

GOVERNANCE
  GET  /api/governance/config ............. governance_config.json
  GET  /api/ideas ......................... idea_registry.json

OUTPUT FEEDS
  GET  /api/preparation ................... Preparation engine results
  GET  /api/notifications ................. Recent events { since, types }
  GET  /api/cycleboard .................... CycleBoard state
  PUT  /api/cycleboard .................... Update CycleBoard
```

#### Governance Daemon (Cron Schedule)

```
+------------------+----------------+------------------------------------------+
| Job              | Schedule       | What It Does                             |
+------------------+----------------+------------------------------------------+
| heartbeat        | */5 min        | System health check                      |
| refresh          | 0 * * * *      | Spawn: python atlas_cli.py daily (2m TO) |
| day_start        | 0 6 * * *      | Daily startup sequence                   |
| day_end          | 0 22 * * *     | Daily shutdown sequence                  |
| mode_recalc      | */15 min       | Deterministic mode routing               |
| work_queue       | */1 min        | Work queue management                    |
| agent_pipeline   | 0 6 * * 0      | Weekly idea extraction (10m timeout)     |
| preparation      | */5 min        | Preparation engine                       |
| stall_check      | 0 21 * * *     | Stall detection                          |
+------------------+----------------+------------------------------------------+
```

---

### 3.2 COGNITIVE-SENSOR (Analysis Pipeline)

```
Port:        None (subprocess-driven, no HTTP server)
Technology:  Python / SQLite
Entry Point: services/cognitive-sensor/atlas_cli.py
Database:    services/cognitive-sensor/results.db (SQLite)
Invoked By:  delta-kernel daemon, mosaic-orchestrator
```

#### Internal Component Tree

```
services/cognitive-sensor/
+-- atlas_cli.py ..................... CLI: daily | weekly | backlog | briefs | status
+-- atlas.py ......................... Main ATLAS engine
+-- atlas_agent.py ................... Claude API agent invocation (retry 2x)
+-- atlas_config.py .................. Configuration + compute_mode() authority
+-- atlas_data.py .................... Data structures
+-- atlas_graph.py ................... Graph representations
+-- atlas_layers.py .................. Cognitive layer analysis
+-- atlas_layout.py .................. Spatial layout algorithms
+-- atlas_projection.py .............. Projection/visualization
+-- atlas_render.py .................. Rendering output
+-- cognitive_api.py ................. Query interface: query(), get_state(), get_open_loops()
+-- refresh.py ....................... Sequential pipeline (11 steps, retry 2x each)
+-- loops.py ......................... Loop evaluation
+-- route_today.py ................... Daily routing decisions
+-- close_loop.py .................... Close specific loops
+-- export_daily_payload.py .......... Generate daily_payload.json
+-- wire_cycleboard.py ............... Copy state files to cycleboard/brain/
+-- directive_engine.py .............. Directive management
+-- drift_detector.py ................ Pattern change detection
+-- behavioral_memory.py ............. Behavioral state tracking
+-- ghost_executor.py ................ Hypothetical action execution
+-- governance_config_api.py ......... Export config to JSON
+--
+-- AGENTS
|   +-- agent_excavator.py ........... Idea excavation
|   +-- agent_synthesizer.py ......... Synthesis engine
|   +-- agent_classifier.py .......... Topic classification
|   +-- agent_classifier_convo.py .... Conversation classification
|   +-- agent_deduplicator.py ........ Duplicate removal
|   +-- agent_reporter.py ............ Report generation
|   +-- agent_orchestrator.py ........ Multi-agent coordination
|   +-- agent_book_miner.py .......... Book insight extraction
+--
+-- EXECUTION
|   +-- run_agents.py ................ Execute agent pipeline
|   +-- run_daily.py ................. Daily execution
|   +-- run_weekly.py ................ Weekly execution
|   +-- run_audit.py ................. Audit trail
|   +-- run_graph_ingest.py .......... Neo4j ingestion
|   +-- run_predictions.py ........... Prediction pipeline
|   +-- governor_daily.py ............ Daily governance
|   +-- governor_weekly.py ........... Weekly governance
+--
+-- GRAPH (shared with mirofish)
|   +-- mirofish/graph/neo4j_client.py
|   +-- mirofish/graph/conversation_chunker.py
|   +-- mirofish/graph/conversation_extractor.py
|   +-- mirofish/graph/embedder.py
|   +-- mirofish/graph/ingester.py
|   +-- mirofish/ingest_state.py
+--
+-- OUTPUT FILES (consumed by other services)
|   +-- daily_payload.json ........... Daily cognitive state (DailyPayload.v1)
|   +-- cognitive_state.json ......... Core cognitive metrics
|   +-- governance_state.json ........ Governance decisions
|   +-- governance_config.json ....... Config export
|   +-- idea_registry.json ........... Excavated ideas (top 10)
|   +-- governor_headline.json ....... Governance summary
|   +-- prediction_results.json ...... ML predictions
|   +-- daily_directive.txt .......... Primary directive text
|   +-- daily_brief.md ............... Human-readable brief
|   +-- strategic_priorities.json .... Priority ranking
|   +-- loops_latest.json ............ Current open loops
|   +-- drift_alerts.json ............ Drift detection alerts
|   +-- closures.json ................ Loop closure log
|   +-- completion_stats.json ........ Completion analytics
```

#### Refresh Pipeline (refresh.py)

```
Step 1:  behavioral_memory_assess ..... Analyze behavioral history
Step 2:  governance_config_api ........ Apply governance rules
Step 3:  loops ........................ Evaluate decision loops
Step 4:  completion_stats ............. Calculate closure ratios
Step 5:  export_cognitive_state ....... Generate cognitive_state.json
Step 6:  run_graph_ingest ............. Push to Neo4j
Step 7:  route_today .................. Route decisions
Step 8:  run_predictions .............. Run predictive models
Step 9:  export_daily_payload ......... Create daily_payload.json
Step 10: wire_cycleboard .............. Copy files to cycleboard/brain/
Step 11: notify_orchestrator .......... POST to mosaic-orchestrator

Each step: retry 2x with 3s delay on failure
```

#### Database Schema (results.db)

```
TABLE convo_time
+----------------+----------+----------------------------------+
| Column         | Type     | Purpose                          |
+----------------+----------+----------------------------------+
| convo_id       | TEXT PK  | Conversation identifier          |
| timestamp      | TEXT     | ISO timestamp                    |
| title          | TEXT     | Conversation title               |
+----------------+----------+----------------------------------+

TABLE loop_decisions
+----------------+----------+----------------------------------+
| Column         | Type     | Purpose                          |
+----------------+----------+----------------------------------+
| loop_id        | TEXT PK  | Loop identifier                  |
| decision       | TEXT     | CLOSE | ARCHIVE                  |
| decided_at     | TEXT     | Decision timestamp               |
| reason         | TEXT     | Decision rationale               |
+----------------+----------+----------------------------------+
```

---

### 3.3 MIROFISH (Prediction Engine)

```
Port:        3003
Technology:  Python / FastAPI / uvicorn
Entry Point: services/mirofish/src/mirofish/main.py
Database:    Neo4j (bolt://localhost:7687)
Embeddings:  Ollama (http://localhost:11434)
```

#### Internal Component Tree

```
services/mirofish/src/mirofish/
+-- main.py .......................... uvicorn server (:3003)
+-- api.py ........................... FastAPI routes
+-- config.py ........................ Neo4j URI, Ollama URL, port config
+-- ingest_state.py .................. Track ingestion progress
+--
+-- graph/
|   +-- neo4j_client.py .............. Neo4j connection & queries
|   +-- conversation_chunker.py ...... Break convos into analyzable chunks
|   +-- conversation_extractor.py .... Extract structure + metadata
|   +-- embedder.py .................. Generate embeddings via Ollama
|   +-- ingester.py .................. Load to Neo4j + build edges
+--
+-- prediction/
|   +-- insight_engine.py ............ Generate insights from patterns
|   +-- loop_predictor.py ............ Predict open loop outcomes
|   +-- pattern_detector.py .......... Find repeating behavior patterns
|   +-- mode_simulator.py ............ Simulate mode transitions
```

#### API Endpoints

```
HEALTH
  GET  /api/v1/health ................. { status, timestamp, version, service }

INGESTION
  POST /api/v1/ingest ................ Async batch ingest (batch_size, force, build_edges)
  GET  /api/v1/ingest/status ......... { running, progress_percent }
  POST /api/v1/edges/build ........... Build similarity + temporal edges

PREDICTION
  POST /api/v1/predict/actions ....... Predict next actions
  POST /api/v1/predict/patterns ...... Find repeating patterns
  POST /api/v1/predict/mode .......... Forecast mode change
  POST /api/v1/simulate/:mode ........ Simulate mode outcome

INSIGHTS
  GET  /api/v1/insights .............. Top insights
  POST /api/v1/insights/refresh ...... Regenerate insights

STATUS
  GET  /api/v1/status ................ Neo4j + overall status
```

#### Neo4j Graph Model

```
    (Conversation)---[:CONTAINS]--->(Message)
         |                              |
         |[:TEMPORAL_NEXT]         [:MENTIONS]
         |                              |
         v                              v
    (Conversation)                  (Concept)
         |
    [:SIMILAR_TO]  (cosine similarity edges)
         |
         v
    (Conversation)

    (Person)---[:PARTICIPATES_IN]--->(Conversation)
    (Pattern)---[:DETECTED_IN]----->(Conversation)
```

---

### 3.4 MOSAIC-ORCHESTRATOR (Central Hub)

```
Port:        3005
Technology:  Python / FastAPI / uvicorn
Entry Point: services/mosaic-orchestrator/src/mosaic/main.py
Config:      services/mosaic-orchestrator/src/mosaic/config.py
```

#### Internal Component Tree

```
services/mosaic-orchestrator/src/mosaic/
+-- main.py .......................... uvicorn server (:3005)
+-- config.py ........................ Service URLs, API keys, metering config
+--
+-- clients/
|   +-- delta_client.py .............. Delta-Kernel HTTP client (:3001)
|   +-- cognitive_client.py .......... Cognitive-Sensor subprocess client
|   +-- mirofish_client.py ........... MiroFish HTTP client (:3003)
|   +-- aegis_client.py .............. Aegis-Fabric HTTP client (:3002)
|   +-- openclaw_client.py ........... OpenClaw HTTP client (:3004)
|   +-- festival_client.py ........... Festival workflow integration
+--
+-- adapters/
|   +-- claude_adapter.py ............ Execute tasks via Claude API
+--
+-- metering/
|   +-- metering.py .................. Token/cost usage tracking
```

#### Client Methods

```
DELTA CLIENT (delta_client.py -> :3001)
  get_unified_state()      GET  /api/state/unified
  ingest_cognitive(payload) POST /api/ingest/cognitive
  request_work(job)         POST /api/work/request
  complete_work(id, out)    POST /api/work/complete
  get_daemon_status()       GET  /api/daemon/status
  Retry: 2 attempts, exponential backoff

COGNITIVE CLIENT (cognitive_client.py -> subprocess)
  run_daily()              Spawn: python atlas_cli.py daily (120s timeout)
  run_weekly()             Spawn: python atlas_cli.py weekly
  read_daily_payload()     Read: daily_payload.json
  read_governance_state()  Read: governance_state.json
  read_daily_brief()       Read: daily_brief.md

MIROFISH CLIENT (mirofish_client.py -> :3003)
  predict_actions()        POST /api/v1/predict/actions
  detect_patterns()        POST /api/v1/predict/patterns
  forecast_mode()          POST /api/v1/predict/mode
  simulate_mode(mode)      POST /api/v1/simulate/:mode

AEGIS CLIENT (aegis_client.py -> :3002)
  register_agent(spec)     POST /api/v1/agents
  submit_action(action)    POST /api/v1/agent/action
  get_approval_status(id)  GET  /api/v1/approvals/:id
  list_policies()          GET  /api/v1/policies

OPENCLAW CLIENT (openclaw_client.py -> :3004)
  notify(text, channel)    POST /api/v1/notify
  list_channels()          GET  /api/v1/channels
  get_skill(name)          GET  /api/v1/skills/:name
```

#### API Endpoints

```
HEALTH & STATUS
  GET  /api/v1/health ................. { status, timestamp, version }
  GET  /api/v1/status ................. { mode, risk, build_allowed, open_loops, festival }

TASK EXECUTION
  POST /api/v1/tasks/execute .......... Execute task via Claude API
       Body: { task_id, instructions, files_context, timeout_seconds, priority }
       Returns: { task_id, success, output, duration_seconds, tokens_used, provider }

METERING
  GET  /api/v1/metering/usage ......... Token/cost tracking
  POST /api/v1/metering/pause ......... Pause AI execution

FESTIVAL
  GET  /api/v1/festival/status ........ Festival workflow status
  POST /api/v1/festival/advance ....... Advance phase

WORKFLOWS
  POST /api/v1/workflows/daily_loop ... Execute full daily cycle
  POST /api/v1/workflows/stall_check .. Check for stalls
  POST /api/v1/workflows/idea_to_simulation .. Simulate idea outcome
```

---

### 3.5 OPENCLAW (Messaging Gateway)

```
Port:        3004
Technology:  Python / FastAPI / uvicorn
Entry Point: services/openclaw/src/openclaw/main.py
Channels:    Telegram, Slack, Discord
```

#### Internal Component Tree

```
services/openclaw/src/openclaw/
+-- main.py .......................... uvicorn server (:3004)
+-- api.py ........................... FastAPI routes
+-- config.py ........................ Channel tokens, schedule times
+--
+-- channels/
|   +-- base.py ...................... Channel interface (abstract)
|   +-- telegram.py .................. Telegram bot (webhook inbound)
|   +-- slack.py ..................... Slack integration (app tokens)
|   +-- discord.py ................... Discord bot (WebSocket events)
+--
+-- skills/
|   +-- status.py .................... /status command handler
|   +-- brief.py ..................... /brief command handler
|   +-- fest.py ...................... /fest command handler
|   +-- simulate.py .................. /simulate command handler
|   +-- approve.py ................... /approve command handler
+--
+-- scheduler.py ..................... Daily scheduled notifications
```

#### API Endpoints

```
HEALTH
  GET  /api/v1/health ................. { status, timestamp, version }

CHANNELS
  GET  /api/v1/channels ............... List active channels
  POST /api/v1/channels/:name/connect . Connect channel
  POST /api/v1/channels/:name/disconnect

MESSAGING
  POST /api/v1/notify ................. Send message { text, channel?, chat_id }
  GET  /api/v1/messages ............... Message history

SKILLS
  GET  /api/v1/skills ................. List available skills
  POST /api/v1/skills/:name/invoke .... Execute skill command

SCHEDULING
  GET  /api/v1/schedule ............... Daily scheduled messages
  PUT  /api/v1/schedule ............... Update schedule

WEBHOOKS
  POST /api/v1/webhooks/:channel ...... Inbound message webhook
```

---

### 3.6 AEGIS-FABRIC (Policy Engine)

```
Port:        3002
Technology:  TypeScript / Express
Entry Point: services/aegis-fabric/src/api/server.ts
Storage:     SQLite (local) or PostgreSQL
Auth:        X-Aegis-Key header per tenant
```

#### Internal Component Tree

```
services/aegis-fabric/src/
+-- api/
|   +-- server.ts .................... Express server (:3002)
+-- routes/
|   +-- tenant-routes.ts ............. Tenant CRUD
|   +-- agent-routes.ts .............. Agent registration + action submission
|   +-- policy-routes.ts ............. Policy CRUD + evaluation
|   +-- approval-routes.ts ........... Approval queue
|   +-- state-routes.ts .............. Entity state + snapshots
|   +-- webhook-routes.ts ............ Webhook management
|   +-- metrics-routes.ts ............ Usage metrics
|   +-- delta-routes.ts .............. Delta history
+-- storage/
|   +-- aegis-storage.ts ............. Entity CRUD + snapshots
+-- tenants/
|   +-- tenant-registry.ts ........... Tenant management
|   +-- tenant-isolation.ts .......... Multi-tenant isolation
+-- agents/
|   +-- agent-registry.ts ............ Agent lifecycle
|   +-- agent-adapter.ts ............. Action normalization
|   +-- action-processor.ts .......... Action execution pipeline
+-- policies/
|   +-- policy-store.ts .............. Policy CRUD
|   +-- policy-engine.ts ............. Policy evaluation (APPROVED|DENIED|PENDING)
|   +-- decision-cache.ts ............ Decision caching
+-- approval/
|   +-- approval-queue.ts ............ Approval workflows
+-- events/
|   +-- event-bus.ts ................. Event routing
|   +-- webhook-dispatcher.ts ........ Webhook delivery
|   +-- audit-log.ts ................. Audit trail
+-- cost/
|   +-- usage-tracker.ts ............. Token/cost accounting
+-- observability/
|   +-- logger.ts .................... Structured logging
|   +-- metrics.ts ................... Prometheus-style metrics
|   +-- health.ts .................... Health endpoint
+-- gateway/
|   +-- api-middleware.ts ............ Request ID, auth, rate limiting, logging
```

#### API Endpoints

```
TENANTS
  POST   /api/v1/tenants .............. Register tenant
  GET    /api/v1/tenants .............. List tenants
  GET    /api/v1/tenant/:id ........... Tenant details
  PUT    /api/v1/tenant/:id ........... Update tenant
  DELETE /api/v1/tenant/:id ........... Deactivate tenant

AGENTS
  POST /api/v1/agents ................. Register agent
  GET  /api/v1/agents ................. List agents (per tenant)
  POST /api/v1/agent/action ........... Submit action (PRIMARY ENDPOINT)
       Body: { agent_id, action_type, parameters }
       Flow: normalize -> policy evaluate -> route (approve/deny/queue)

POLICIES
  POST   /api/v1/policies ............. Create policy
  GET    /api/v1/policies ............. List policies
  PUT    /api/v1/policy/:id ........... Update policy
  DELETE /api/v1/policy/:id ........... Delete policy
  POST   /api/v1/policy/:id/decision .. Evaluate policy

STATE
  GET  /api/v1/state/:entity_id ....... Entity state + delta history
  POST /api/v1/snapshot ............... Create snapshot
  GET  /api/v1/snapshots .............. List snapshots
  POST /api/v1/snapshot/:id/restore ... Restore from snapshot

APPROVALS
  GET  /api/v1/approvals .............. Pending approvals
  POST /api/v1/approval/:id/approve ... Approve action
  POST /api/v1/approval/:id/deny ...... Deny action

WEBHOOKS
  POST   /api/v1/webhook .............. Register webhook
  GET    /api/v1/webhooks .............. List webhooks
  DELETE /api/v1/webhook/:id .......... Unregister

METRICS
  GET /api/v1/metrics ................. Usage statistics
  GET /api/v1/metrics/tenant/:id ...... Per-tenant usage

DELTAS
  GET  /api/v1/deltas/:entity_id ...... Entity delta history
  POST /api/v1/delta .................. Create delta manually
```

#### Agent Action Processing Flow

```
  Client POST /api/v1/agent/action
          |
          v
  +------------------+
  | normalizeAction() |  (agent-adapter.ts)
  +------------------+
          |
          v
  +------------------+
  | policyEngine     |  (policy-engine.ts)
  | .evaluate()      |  Check rules, cache decision
  +------------------+
          |
     +----+----+----+
     |         |    |
     v         v    v
  APPROVED  DENIED  PENDING_APPROVAL
     |         |         |
     v         v         v
  Execute   Return    Queue in
  action    403       approval-queue.ts
     |                   |
     v                   v
  Record in          Send to OpenClaw
  audit-log.ts       Wait for human
  usage-tracker.ts   POST /approval/:id/approve
  event-bus.emit()
```

---

### 3.7 CONTRACTS/SCHEMAS

```
Location: contracts/schemas/
Format:   JSON Schema draft-07
```

#### Schema Catalog

```
+-------------------------------+---------------------------------------------+
| Schema File                   | Purpose                                     |
+-------------------------------+---------------------------------------------+
| DailyPayload.v1.json          | Daily cognitive state (mode, loops, risk)    |
| CognitiveMetricsComputed.json | Computed cognitive metrics                   |
| ModeContract.v1.json          | Mode definition + routing contract           |
| WorkLedger.v1.json            | Work queue state (active/queued/completed)   |
| IdeaRegistry.v1.json          | Central idea catalog                         |
| ExcavatedIdeas.v1.json        | Raw idea extraction output                   |
| OrchestratorEvent.v1.json     | Orchestration event schema                   |
| TaskExecution.v1.json         | Task execution record                        |
| SimulationReport.v1.json      | Simulation outcome                           |
| AegisAgent.v1.json            | Agent registration contract                  |
| AegisAgentAction.v1.json      | Agent action submission                      |
| AegisPolicy.v1.json           | Policy rule definition                       |
| AegisPolicyDecision.v1.json   | Policy evaluation result                     |
| AegisApproval.v1.json         | Approval queue item                          |
| AegisTenant.v1.json           | Tenant configuration                         |
| AegisWebhook.v1.json          | Webhook registration                         |
| TimelineEvents.v1.json        | Timeline event structure                     |
+-------------------------------+---------------------------------------------+
```

#### Key Schema: DailyPayload.v1

```
{
  "schema_version": "1.0.0",
  "mode_source":    "cognitive-sensor | governance-daemon",
  "mode":           "BUILD | MAINTENANCE | CLOSURE",
  "build_allowed":  boolean,
  "primary_action": "string",
  "open_loops":     ["string"],
  "open_loop_count": integer,
  "closure_ratio":  0-100,
  "risk":           "LOW | MEDIUM | HIGH",
  "generated_at":   "YYYY-MM-DD",
  "predictions": {
    "status":        "ok | unavailable",
    "top_actions":   [{ action, confidence, reason }],
    "pattern_count": integer,
    "mode_forecast": { mode, confidence, exit_path } | null
  }
}
```

#### Key Schema: WorkLedger.v1

```
{
  "active":    [{ job_id, type, title, started_at, timeout_at }],
  "queued":    [{ job_id, type, title, queued_at, position, reason }],
  "completed": [{ job_id, outcome, started_at, completed_at, duration_ms, error? }],
  "stats": {
    "total_completed":  integer,
    "total_failed":     integer,
    "avg_duration_ms":  number,
    "total_cost_usd":   number
  },
  "config": {
    "max_concurrent_jobs":  1,
    "max_queue_depth":      5,
    "default_timeout_ms":   600000,
    "allow_ai_in_closure_mode": boolean
  }
}
```

---

## 4. Inter-Service Communication Map

```
+=======================================================================+
|                    HTTP CALL MAP (who calls whom)                       |
+=======================================================================+

MOSAIC-ORCHESTRATOR (:3005) -----> DELTA-KERNEL (:3001)
  |  GET  /api/state/unified
  |  POST /api/ingest/cognitive
  |  POST /api/work/request
  |  POST /api/work/complete
  |  GET  /api/daemon/status
  |  GET  /api/health

MOSAIC-ORCHESTRATOR (:3005) -----> AEGIS-FABRIC (:3002)
  |  POST /api/v1/agent/action
  |  GET  /api/v1/approvals
  |  POST /api/v1/approvals/:id

MOSAIC-ORCHESTRATOR (:3005) -----> MIROFISH (:3003)
  |  POST /api/v1/predict/actions
  |  POST /api/v1/predict/patterns
  |  POST /api/v1/predict/mode
  |  GET  /api/v1/health

MOSAIC-ORCHESTRATOR (:3005) -----> OPENCLAW (:3004)
  |  POST /api/v1/notify
  |  POST /api/v1/skills/:name/invoke

COGNITIVE-SENSOR (subprocess) ---> DELTA-KERNEL (:3001)
  |  POST /api/law/close_loop
  |  POST /api/law/refresh

DELTA-KERNEL DAEMON ------------> COGNITIVE-SENSOR (subprocess)
  |  Spawn: python atlas_cli.py daily|weekly
  |  Timeout: 120 seconds

MIROFISH (:3003) ----------------> NEO4J (:7687)
  |  Cypher queries (read/write)

MIROFISH (:3003) ----------------> OLLAMA (:11434)
  |  POST /api/embeddings
  |  POST /api/generate
```

---

## 5. Data Flow Diagrams

### 5.1 Daily Automation Flow (6 AM)

```
  06:00  DELTA-KERNEL DAEMON triggers day_start
           |
           v
  06:01  Spawn: python atlas_cli.py daily
           |
           v
         COGNITIVE-SENSOR refresh.py pipeline
           |
           +-- Step 1: behavioral_memory_assess
           +-- Step 2: governance_config_api
           +-- Step 3: loops (evaluate open loops)
           +-- Step 4: completion_stats
           +-- Step 5: export cognitive_state.json
           +-- Step 6: run_graph_ingest (push to Neo4j)
           +-- Step 7: route_today (determine mode)
           +-- Step 8: run_predictions
           +-- Step 9: export daily_payload.json
           +-- Step 10: wire_cycleboard (copy to brain/)
           +-- Step 11: notify orchestrator
           |
           v
         MOSAIC-ORCHESTRATOR daily_loop workflow
           |
           +-- Check daemon status (skip if busy)
           +-- Read daily_payload.json
           +-- POST /api/ingest/cognitive to delta-kernel
           +-- Fetch predictions from MiroFish
           +-- Generate brief
           |
           v
         DELTA-KERNEL updates unified state
           |
           +-- Recalculate mode + risk tier
           +-- Emit timeline events
           +-- Update CycleBoard state
           |
           v
         OPENCLAW (if scheduled)
           |
           +-- Send daily brief to Telegram/Slack/Discord
```

### 5.2 Mode Recalculation (Every 15 Minutes)

```
  DELTA-KERNEL DAEMON (mode_recalc cron)
           |
           v
  Fetch current signals:
    +-- sleep_hours      (last 7 days average)
    +-- open_loops       (from cognitive state)
    +-- assets_shipped   (from work ledger)
    +-- deep_work_blocks (from timeline events)
    +-- money_delta      (from financial data)
           |
           v
  Bucket each signal:
    +-- bucketSleepHours(h) ------> LOW | OK | HIGH
    +-- bucketOpenLoops(n) -------> (inverted: fewer = better)
    +-- bucketAssetsShipped(n) ---> LOW | OK | HIGH
    +-- bucketDeepWorkBlocks(n) --> LOW | OK | HIGH
    +-- bucketMoneyDelta(usd) ----> LOW | OK | HIGH
           |
           v
  Markov transition: current_mode + signals --> next_mode
    No AI. No heuristics. Pure lookup table.
           |
           v
  If mode changed:
    +-- Create delta (hash chain entry)
    +-- Emit MODE_CHANGED timeline event
    +-- Update unified state
    +-- Notify Aegis webhooks
```

### 5.3 Work Queue Lifecycle

```
  Client -----> POST /api/work/request
                  { type, title, priority, timeout_ms }
                         |
                         v
                  WorkController checks capacity
                         |
              +----------+-----------+
              |                      |
         Capacity OK            Capacity Full
              |                      |
              v                      v
         Add to ACTIVE          Add to QUEUED
         Start timeout          Set position + reason
         Emit WORK_REQUESTED    Wait for slot
              |
              v
         Job executes...
              |
              v
  Client -----> POST /api/work/complete
                  { job_id, outcome }
                         |
                         v
                  Move ACTIVE -> COMPLETED
                  Update stats (duration, cost)
                  Emit WORK_COMPLETED
                         |
                         v
                  Check QUEUED for next job
                  Promote if slot available
```

### 5.4 Agent Action Approval Flow

```
  External Client (Mosaic, CLI, etc.)
           |
           v
  POST /api/v1/agent/action (Aegis-Fabric :3002)
    { agent_id, action_type, parameters }
           |
           v
  ActionProcessor
    +-- Normalize action
    +-- Look up agent + tenant
           |
           v
  PolicyEngine.evaluate()
    +-- Match against policy rules
    +-- Cache decision
           |
      +----+----+--------+
      |         |        |
      v         v        v
  APPROVED   DENIED   PENDING
      |         |        |
      v         v        v
  Execute    403 err  ApprovalQueue
  action               |
      |                 v
      v           Send to OpenClaw
  AuditLog       (Telegram/Slack/Discord)
  UsageTracker         |
  EventBus.emit()      v
                  Human approves/denies
                  POST /approval/:id/approve
                         |
                         v
                  Execute or reject action
```

### 5.5 Prediction Pipeline

```
  Cognitive-Sensor run_predictions.py
           |
           v
  MIROFISH (:3003)
    +-- Query Neo4j for conversation patterns
    +-- loop_predictor: predict open loop outcomes
    +-- pattern_detector: find repeating behaviors
    +-- mode_simulator: forecast mode transitions
    +-- insight_engine: generate top insights
           |
           v
  Write prediction_results.json
    {
      "top_actions": [...],
      "pattern_count": N,
      "mode_forecast": { mode, confidence },
      "exit_path": { ... }
    }
           |
           v
  wire_cycleboard copies to cycleboard/brain/
           |
           v
  CycleBoard displays predictions in UI
```

---

## 6. Database Map

```
+==================================================================+
|                       DATABASE TOPOLOGY                           |
+==================================================================+

  ~/.delta-fabric/
  +-- entities.db ............. SQLite (WAL mode)
  |     Tables: entities, deltas, timeline_events
  |     Used by: delta-kernel server.ts
  |
  +-- deltas.log .............. Append-only delta log
        Used by: delta-kernel (backup/audit)

  services/cognitive-sensor/
  +-- results.db .............. SQLite
  |     Tables: convo_time, loop_decisions
  |     Used by: cognitive_api.py, loops.py, close_loop.py

  Neo4j (bolt://localhost:7687)
  +-- Nodes: Conversation, Message, Person, Concept, Pattern
  +-- Edges: TEMPORAL_NEXT, SIMILAR_TO, CONTAINS,
  |          MENTIONS, PARTICIPATES_IN, DETECTED_IN
  +-- Used by: mirofish (graph/), cognitive-sensor (mirofish/)

  services/aegis-fabric/
  +-- .aegis-data/ ............ SQLite or PostgreSQL
        Tables: tenants, agents, policies, decisions,
                approvals, webhooks, audit_log, snapshots
        Used by: aegis-fabric storage.ts
```

---

## 7. Configuration & Environment Variables

```
DELTA-KERNEL (:3001)
  DELTA_DATA_DIR .............. State directory (default: ~/.delta-fabric)
  DELTA_REPO_ROOT ............. Pre Atlas root (auto-detected)
  COGNITIVE_SENSOR_DIR ........ cognitive-sensor path (auto-detected)

COGNITIVE-SENSOR (CLI)
  RESULTS_DB .................. results.db path
  ANTHROPIC_API_KEY ........... Claude API key
  OLLAMA_URL .................. Embeddings endpoint

MIROFISH (:3003)
  NEO4J_URI ................... Neo4j bolt connection
  OLLAMA_URL .................. Embeddings endpoint
  PORT ........................ Listen port (default: 3003)

MOSAIC-ORCHESTRATOR (:3005)
  DELTA_KERNEL_URL ............ http://localhost:3001
  COGNITIVE_SENSOR_DIR ........ Path to cognitive-sensor
  AEGIS_URL ................... http://localhost:3002
  MIROFISH_URL ................ http://localhost:3003
  OPENCLAW_URL ................ http://localhost:3004
  ANTHROPIC_API_KEY ........... Claude API key
  OLLAMA_URL / OLLAMA_MODEL ... Fallback LLM
  METERING_DB_PATH ............ Cost tracking database
  FREE_TIER_SECONDS ........... Usage limit

AEGIS-FABRIC (:3002)
  AEGIS_PORT .................. Listen port (default: 3002)
  AEGIS_DATA_DIR .............. Storage directory (.aegis-data)

OPENCLAW (:3004)
  TELEGRAM_BOT_TOKEN .......... Telegram bot API token
  TELEGRAM_WEBHOOK_URL ........ Inbound webhook URL
  SLACK_BOT_TOKEN ............. Slack bot token
  SLACK_APP_TOKEN ............. Slack app token
  DISCORD_TOKEN ............... Discord bot token
  DISCORD_WEBHOOK_URL ......... Discord webhook URL
```

---

## 8. Startup & Health Checks

### Boot All Services

```
# Terminal 1: Delta-Kernel (:3001)
cd services/delta-kernel && npm run dev

# Terminal 2: Aegis-Fabric (:3002)
cd services/aegis-fabric && npm run dev

# Terminal 3: MiroFish (:3003)
cd services/mirofish && python -m mirofish.main

# Terminal 4: OpenClaw (:3004)
cd services/openclaw && python -m openclaw.main

# Terminal 5: Mosaic-Orchestrator (:3005)
cd services/mosaic-orchestrator && python -m mosaic.main

# Cognitive-Sensor runs automatically via delta-kernel daemon subprocess
```

### Or use the all-in-one script:

```powershell
.\scripts\start_all_services.ps1
```

### Health Check Endpoints

```
curl http://localhost:3001/api/health          # Delta-Kernel
curl http://localhost:3002/health              # Aegis-Fabric
curl http://localhost:3003/api/v1/health       # MiroFish
curl http://localhost:3004/api/v1/health       # OpenClaw
curl http://localhost:3005/api/v1/health       # Mosaic-Orchestrator
curl http://localhost:3001/api/daemon/status    # Governance Daemon
```

### CORS Configuration (Delta-Kernel)

```
Allowed Origins:
  http://localhost:3000    (Mosaic Dashboard)
  http://localhost:3001    (Self)
  http://localhost:5500    (Live Server)
  http://localhost:5501    (Live Server alt)
  http://localhost:8765    (Atlas Shell)
  http://localhost:8888    (Atlas Shell alt)
  http://localhost:8889    (CycleBoard)
  file://                  (Local files)
```

---

## 9. Authentication

```
+-- .aegis-tenant-key (repo root)
|     Contains: Bearer token for Delta-Kernel API
|     Dev mode: No auth if file missing
|
+-- X-Aegis-Key header
|     Used by: Aegis-Fabric per-tenant auth
|     Mosaic Dashboard passes via proxy
|
+-- ANTHROPIC_API_KEY
|     Used by: cognitive-sensor agents, mosaic-orchestrator Claude adapter
|
+-- Channel tokens (OpenClaw)
      TELEGRAM_BOT_TOKEN, SLACK_BOT_TOKEN, DISCORD_TOKEN
```
