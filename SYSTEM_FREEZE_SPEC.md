# Pre Atlas — Complete System Freeze Specification

> Generated: 2026-03-09
> Purpose: Complete structural and behavioral map for external AI reconstruction.
> This document contains everything needed to understand the Pre Atlas system without repository access.

---

## 1. System Purpose

### Core Problem
Pre Atlas is a **personal behavioral governance system**. It solves the problem of self-management for a solo operator who cycles between recovery, closure, building, and scaling phases. The system enforces behavioral discipline by:
- Detecting operational mode from real signals (sleep, open loops, assets shipped, deep work blocks, money delta)
- Routing the operator to the correct behavioral mode via deterministic lookup (no AI, no heuristics)
- Preventing mode-inappropriate actions (e.g., blocking new task creation during CLOSURE mode)
- Tracking open loops across 1,397 historical conversations and enforcing closure before forward progress

### Main Workflow
1. **Conversation Analysis** (Python/cognitive-sensor): Analyze 93,898 messages from 1,397 conversations to detect open loops, compute closure ratios, classify conversations, extract ideas
2. **State Computation** (Python → JSON → TypeScript): Export cognitive metrics (open loops, closure ratio, topic drift) as validated JSON
3. **Mode Routing** (TypeScript/delta-kernel): Compute operational mode (RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE) via deterministic Markov lookup table
4. **Governance Enforcement** (TypeScript/aegis-fabric): AI agent actions pass through a policy gate that evaluates declarative rules against current mode
5. **Human Interface** (HTML/JS dashboards): Display mode, signals, prepared actions, and strategic priorities through atlas_boot.html master shell

### Intended Outputs
- **Daily directive**: Mode + risk level + primary action + open loops (daily_payload.json)
- **Governance state**: Lane status, violations, leverage moves (governance_state.json)
- **Idea registry**: Priority-ranked ideas with execution sequence (idea_registry.json)
- **Behavioral audit**: 30-question audit across 6 psychological layers (BEHAVIORAL_AUDIT.md)
- **Cognitive atlas**: Interactive 84K-point visualization of conversation clusters (cognitive_atlas.html)
- **Policy decisions**: ALLOW/DENY/REQUIRE_HUMAN for every AI agent action

### 6 Operational Modes
```
RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE
```
- **RECOVER**: Sleep deficit or burnout. Only rest + light admin allowed.
- **CLOSURE**: Too many open loops (≥4). Must close loops before building.
- **MAINTENANCE**: Routine upkeep. No new projects.
- **BUILD**: Active creation. Shipping assets.
- **COMPOUND**: Extending shipped assets. Deep work.
- **SCALE**: Delegating, systemizing. Leverage phase.

---

## 2. Full Repository Tree

```
Pre Atlas/                              # Root (federated monorepo)
├── .claude/                            # Claude Code IDE configuration
│   ├── settings.local.json             # Workspace permissions
│   └── plans/                          # Plan mode artifacts
├── .delta-fabric/                      # Delta state store (git-ignored, runtime-generated)
│   ├── entities.json                   # Entity state map
│   ├── deltas.json                     # Append-only hash-chained delta log
│   └── dictionary.json                 # 3-tier compression dictionary
├── .git/                               # Version control
├── apps/
│   ├── blueprint-generator/            # Next.js constraint-based blueprint generator
│   │   ├── app/                        # Next.js app router (page.tsx, layout.tsx, globals.css)
│   │   ├── lib/                        # Core logic (types, parse, generate, scope, format, storage)
│   │   ├── package.json                # Next.js 15 + React 19
│   │   └── tsconfig.json
│   └── webos-333/                      # Web OS simulator (3,443 lines, standalone)
├── contracts/
│   └── schemas/                        # JSON Schema (draft-07) data contracts
│       ├── AegisAgent.v1.json          # Agent registration
│       ├── AegisAgentAction.v1.json    # Canonical agent action
│       ├── AegisApproval.v1.json       # Human-in-the-loop approval
│       ├── AegisPolicy.v1.json         # Declarative policy rules
│       ├── AegisPolicyDecision.v1.json # Policy evaluation result
│       ├── AegisTenant.v1.json         # Multi-tenant configuration
│       ├── AegisWebhook.v1.json        # Event subscriptions
│       ├── Closures.v1.json            # Closure registry + streaks
│       ├── CognitiveMetricsComputed.json # Cognitive metrics export
│       ├── DailyPayload.v1.json        # CycleBoard UI payload
│       ├── DailyProjection.v1.json     # Combined daily snapshot
│       ├── ExcavatedIdeas.v1.json      # Raw extracted ideas
│       ├── IdeaRegistry.v1.json        # Prioritized idea master list
│       ├── TimelineEvents.v1.json      # Append-only event log (Phase 6C)
│       └── WorkLedger.v1.json          # Work admission ledger (Phase 6B)
├── data/
│   ├── build_pdf.py                    # PDF builder (fpdf2) for book chapter
│   ├── ch1_top20_passages.json         # Top 20 book passages
│   ├── chapter_01_draft.md             # Book chapter draft
│   ├── chapter_01_final.md             # Book chapter final
│   └── projections/
│       └── today.json                  # Daily projection artifact
├── research/
│   └── uasc-m2m/                       # Symbolic encoding research (peripheral)
├── scripts/
│   ├── run_all.ps1                     # Master orchestrator (PowerShell)
│   ├── run_delta_api.ps1               # Delta API launcher
│   └── run_cognitive.ps1               # Cognitive refresh launcher
├── services/
│   ├── aegis-fabric/                   # Policy gate for AI agents (TypeScript/Express, port 3002)
│   │   ├── .aegis-data/                # File-based state (git-ignored)
│   │   │   ├── tenants.json
│   │   │   ├── usage.json
│   │   │   └── tenants/<uuid>/         # Per-tenant entity + delta storage
│   │   ├── src/
│   │   │   ├── agents/                 # Agent adapter, registry, action processor
│   │   │   ├── api/                    # Express server + 7 route modules
│   │   │   ├── approval/              # Human-in-the-loop approval queue
│   │   │   ├── core/                   # Delta ops, entity registry, types
│   │   │   ├── cost/                   # Usage/quota tracker
│   │   │   ├── events/                 # Audit log, event bus, webhook dispatcher
│   │   │   ├── gateway/                # API middleware, rate limiter, request logger
│   │   │   ├── observability/          # Health, logger, metrics
│   │   │   ├── policies/              # Policy engine, decision cache, policy store
│   │   │   ├── storage/                # File I/O, snapshot manager
│   │   │   ├── tenants/                # Tenant isolation + registry
│   │   │   └── tests/                  # 7 test files
│   │   ├── specs/                      # Feature specifications
│   │   ├── tools/                      # Helper scripts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── start.bat
│   │   └── SYSTEM_BRIEF.md
│   ├── cognitive-sensor/               # Conversation analysis pipeline (Python/SQLite)
│   │   ├── _archive/                   # 15 dead/superseded files
│   │   ├── cycleboard/                 # CycleBoard dashboard UI
│   │   │   ├── brain/                  # State files (cognitive_state, daily_payload, etc.)
│   │   │   ├── css/styles.css
│   │   │   ├── js/                     # 11 JS modules (app, state, screens, ui, etc.)
│   │   │   ├── docs/                   # API, data structures, development docs
│   │   │   ├── index.html              # Main CycleBoard entry
│   │   │   └── LLM_CONTEXT.md
│   │   ├── tests/                      # 7 pytest files (atlas system tests)
│   │   ├── agent_excavator.py          # Extract ideas from conversations
│   │   ├── agent_deduplicator.py       # Merge duplicate ideas
│   │   ├── agent_classifier.py         # Classify ideas (status, skills, alignment)
│   │   ├── agent_classifier_convo.py   # Tag conversations (domain, outcome, trajectory)
│   │   ├── agent_orchestrator.py       # Priority scoring, tier assignment
│   │   ├── agent_reporter.py           # Generate IDEA_REGISTRY.md
│   │   ├── agent_book_miner.py         # Extract book writing material
│   │   ├── agent_synthesizer.py        # Generate BEHAVIORAL_AUDIT.md
│   │   ├── atlas_agent.py              # Unified governance runtime
│   │   ├── atlas_cli.py                # CLI entry (daily/weekly/backlog/briefs/status)
│   │   ├── atlas_config.py             # Single config source (north star, rules, agents)
│   │   ├── atlas_data.py               # Load embeddings from results.db
│   │   ├── atlas_graph.py              # Cluster relationship graph
│   │   ├── atlas_layers.py             # Toggle layer arrays
│   │   ├── atlas_layout.py             # ForceAtlas2 force-directed layout
│   │   ├── atlas_projection.py         # UMAP + HDBSCAN clustering
│   │   ├── atlas_render.py             # Assemble JSON payload + fill HTML template
│   │   ├── atlas_template.html         # Interactive dashboard template
│   │   ├── governor_daily.py           # Daily governance (mode compute, lane check)
│   │   ├── governor_weekly.py          # Weekly aggregation + lane review
│   │   ├── loops.py                    # Open loop detection (topic scoring)
│   │   ├── refresh.py                  # Master refresh pipeline (10-step orchestrator)
│   │   ├── run_agents.py               # Run agent pipeline
│   │   ├── run_audit.py                # Run behavioral audit
│   │   ├── run_daily.py                # Run daily cycle
│   │   ├── run_weekly.py               # Run weekly cycle
│   │   ├── model_cache.py              # Shared sentence-transformer model cache
│   │   ├── validate.py                 # JSON Schema contract validation
│   │   ├── route_today.py              # Determine today's mode
│   │   ├── export_cognitive_state.py   # Export state snapshot
│   │   ├── export_daily_payload.py     # Export daily directive
│   │   ├── wire_cycleboard.py          # Wire CycleBoard with latest state
│   │   ├── push_to_delta.py            # Push projection to Delta API
│   │   ├── build_cognitive_atlas.py    # Build cognitive atlas visualization
│   │   ├── build_cognitive_map.py      # Build semantic cognitive map
│   │   ├── build_dashboard.py          # Build HTML dashboard
│   │   ├── build_docs_manifest.py      # Build documentation index
│   │   ├── build_projection.py         # Build combined projection
│   │   ├── build_strategic_priorities.py # Compute strategic priorities
│   │   ├── cluster_leverage_map.py     # Score clusters by business value
│   │   ├── batch_triage.py             # Batch conversation processing
│   │   ├── completion_stats.py         # Closure behavior metrics
│   │   ├── reporter.py                 # State history reporter
│   │   ├── resurfacer.py               # Surface old conversations
│   │   ├── radar.py                    # Attention drift detection
│   │   ├── decide.py                   # Record loop closure decisions
│   │   ├── cognitive_api.py            # Cognitive API interface
│   │   ├── init_embeddings.py          # Generate sentence embeddings
│   │   ├── init_message_embeddings.py  # Initialize embedding table
│   │   ├── init_results_db.py          # Initialize results.db
│   │   ├── init_titles.py              # Extract conversation titles
│   │   ├── init_convo_time.py          # Extract timestamps
│   │   ├── init_topics.py              # Topic initialization
│   │   ├── inject_directive.py         # Manual directive injection
│   │   ├── requirements.txt            # Python dependencies
│   │   ├── pyproject.toml              # Pytest config
│   │   ├── *.json                      # 23 state/data JSON files
│   │   ├── *.md                        # 28 markdown documents
│   │   ├── dashboard.html              # Analytics dashboard
│   │   ├── control_panel.html          # Master control interface
│   │   ├── idea_dashboard.html         # Idea registry visualization
│   │   └── docs_viewer.html            # Documentation viewer
│   └── delta-kernel/                   # Deterministic state engine (TypeScript/Express, port 3001)
│       ├── src/
│       │   ├── api/server.ts           # Express REST API (~400 lines)
│       │   ├── cli/                    # Terminal UI (app.ts, index.ts, renderer.ts, storage.ts, input.ts)
│       │   ├── core/                   # 35+ TypeScript modules
│       │   │   ├── types.ts            # Central type system (1162 lines, LOCKED)
│       │   │   ├── delta.ts            # Delta operations + hash chain
│       │   │   ├── routing.ts          # Markov mode routing
│       │   │   ├── templates.ts        # 12 message templates (LOCKED)
│       │   │   ├── cockpit.ts          # Module 1: Daily command center
│       │   │   ├── preparation.ts      # Module 2: Preparation engine
│       │   │   ├── dictionary.ts       # Module 3: Matryoshka dictionary
│       │   │   ├── vector-discovery.ts # Module 4: Semantic discovery
│       │   │   ├── ai-design.ts        # Module 5: AI design compiler
│       │   │   ├── delta-sync.ts       # Module 6: P2P sync protocol
│       │   │   ├── off-grid-node.ts    # Module 7: Off-grid node architecture
│       │   │   ├── ui-stream.ts        # Module 8: UI delta streaming
│       │   │   ├── camera-stream.ts    # Module 9: Camera tile streaming
│       │   │   ├── actuation.ts        # Module 10: Remote control
│       │   │   ├── audio-*.ts          # Module 11: Audio streaming
│       │   │   ├── daily-screen.ts     # Mode screen generator
│       │   │   ├── lut.ts              # Lookup table router
│       │   │   ├── work-controller.ts  # Phase 6A: Work admission control
│       │   │   ├── timeline-logger.ts  # Event logging
│       │   │   └── fabric-tests.ts     # Test runner
│       │   ├── governance/
│       │   │   └── governance_daemon.ts # Autonomous scheduler (6 cron jobs)
│       │   ├── tools/
│       │   │   ├── gate.ts             # Access gate
│       │   │   └── gate_client.ts
│       │   └── ui/
│       │       ├── control.html        # Control panel
│       │       └── timeline.html       # Timeline visualization
│       ├── web/                        # React/Vite frontend (port 5173)
│       │   ├── src/App.tsx             # Main React component
│       │   ├── src/main.tsx
│       │   ├── package.json            # React 19 + Vite 7
│       │   └── vite.config.ts
│       ├── specs/                      # 19 specification documents
│       ├── package.json                # delta-state-fabric v0.1.0
│       ├── tsconfig.json
│       └── start.bat                   # Launches API (3001) + Web UI (5173)
├── atlas_boot.html                     # Master control dashboard (917 lines)
├── PRE_ATLAS_MAP.md                    # Architecture reference (571 lines)
├── ONBOARDING.md                       # Developer onboarding guide
├── CONTEXT_PACKET.md                   # Context + objectives
├── PHASE_ROADMAP.md                    # Implementation timeline
├── README.md                           # Project overview
├── Pre_Atlas_System_Debrief.docx       # System debrief document
├── Pre_Atlas_System_Debrief.json       # System debrief data
└── *.png                               # Dashboard/UI screenshots
```

### Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `.delta-fabric/` | Runtime state store. Entities, deltas, dictionary. Git-ignored. Created by delta-kernel on first run. |
| `.aegis-data/` | Aegis runtime state. Tenants, usage, per-tenant entities/deltas. Git-ignored. |
| `apps/blueprint-generator/` | Standalone Next.js app. Generates deterministic execution blueprints from one-sentence ideas. Zero coupling to other services. |
| `apps/webos-333/` | Web OS simulator UI. 3,443 lines. Standalone. |
| `contracts/schemas/` | JSON Schema (draft-07) data contracts. Shared boundary between Python and TypeScript services. |
| `data/` | Book writing pipeline (Chapter 01 of power dynamics guide) + daily projection artifacts. |
| `research/uasc-m2m/` | Symbolic encoding research. Not part of core system. |
| `scripts/` | PowerShell orchestration scripts for Windows. |
| `services/aegis-fabric/` | AI agent policy gate. Evaluates actions against declarative rules. Port 3002. |
| `services/cognitive-sensor/` | Python conversation analysis pipeline. 8 agents, atlas visualization, governance, loops detection. |
| `services/delta-kernel/` | Core TypeScript state engine. 11 spec'd modules, REST API, CLI, governance daemon. Port 3001. |

---

## 3. File Inventory

### delta-kernel — TypeScript Core Engine

| File Path | Type | Responsibility | Key Imports | Key Exports |
|-----------|------|---------------|-------------|-------------|
| `src/core/types.ts` | TypeScript | Central type system (1162 lines). LOCKED. 45 entity types, Mode enum, all data models. | None (leaf) | Mode, Entity, Delta, SystemStateData, DraftData, all 45 entity types, sync types, UI types |
| `src/core/delta.ts` | TypeScript | Delta operations. UUID generation, SHA256 hashing, entity creation, JSON Patch application. | `types.ts` | `generateUUID`, `now`, `sha256`, `hashState`, `createEntity`, `applyPatch` |
| `src/core/routing.ts` | TypeScript | Deterministic Markov mode routing. Pure lookup table. Bucket functions for 5 signals. | `types.ts` | `computeMode`, `bucketSleepHours`, `bucketOpenLoops`, `bucketAssetsShipped`, `bucketDeepWorkBlocks`, `bucketMoneyDelta` |
| `src/core/templates.ts` | TypeScript | 12 message templates (LOCKED). 6 generic + 6 mode-tagged. | `types.ts` | `TEMPLATES`, `renderTemplate` |
| `src/core/cockpit.ts` | TypeScript | Module 1: Daily command center. Generates CockpitState from signals, tasks, drafts. MAX 7 prepared actions. | `types.ts`, `delta.ts` | `CockpitState`, `buildCockpit` |
| `src/core/preparation.ts` | TypeScript | Module 2: Background preparation engine. Generates Draft entities. Never executes. MAX 5 drafts/run. | `types.ts`, `delta.ts`, `templates.ts` | `PreparationJob`, `runPreparation` |
| `src/core/dictionary.ts` | TypeScript | Module 3: Matryoshka 3-tier compression. Token → Pattern → Motif. Append-only, promotion permanent. | `types.ts` | `getOrCreateToken`, `getOrCreatePattern`, `getOrCreateMotif` |
| `src/core/vector-discovery.ts` | TypeScript | Module 4: Semantic clustering + pattern detection. Generates DiscoveryProposal entities. | `types.ts`, `delta.ts` | `VectorJob`, `runDiscovery`, `DiscoveryProposal` |
| `src/core/ai-design.ts` | TypeScript | Module 5: AI design compiler. LLM-based structure proposals. AI NEVER executes — outputs compile to LUTs only. | `types.ts`, `delta.ts` | `DesignProposal`, `runDesign` |
| `src/core/delta-sync.ts` | TypeScript | Module 6: P2P sync protocol. 7 packet types, LoRa-safe (220-byte max), nonce-based HELLO. | `types.ts` | `SyncPacket`, `SyncSession`, `EntityConflict` |
| `src/core/off-grid-node.ts` | TypeScript | Module 7: Off-grid node tiers (CORE/EDGE/MICRO). Hardware profiles, storage limits. Planned. | `types.ts` | `NodeClass`, `HardwareProfile`, `NodeCapabilities` |
| `src/core/ui-stream.ts` | TypeScript | Module 8: UI delta streaming. 6 component kinds, 7 stream operations. Ultra-low bandwidth. | `types.ts` | `UIStreamOp`, `UIComponentProps`, `UISurfaceData` |
| `src/core/camera-stream.ts` | TypeScript | Module 9: Camera tile delta streaming. Residual tile deltas for ultra-low bandwidth. | `types.ts` | `CameraSurfaceData`, `SceneTileData`, `CameraStreamOp` |
| `src/core/actuation.ts` | TypeScript | Module 10: Remote control. 7 actuator kinds, human confirmation gate. Intent status: NEW→AUTHORIZED→DISPATCHED→APPLIED. | `types.ts` | `ActuatorKind`, `ActuationIntentData`, `ControlSurfaceData` |
| `src/core/daily-screen.ts` | TypeScript | Mode screen generator. Builds DailyScreenData from pure data transforms. | `types.ts`, `routing.ts` | `DailyScreenData`, `buildDailyScreen` |
| `src/core/lut.ts` | TypeScript | Lookup table router. Alternative Markov routing with signal buckets. | `types.ts` | `routeMode` |
| `src/core/work-controller.ts` | TypeScript | Phase 6A: Universal work admission gate. 3 primitives: request(), complete(), status(). Humans AND machines. | `types.ts` | `WorkLedger`, `requestWork`, `completeWork`, `workStatus` |
| `src/core/timeline-logger.ts` | TypeScript | Event logging for temporal visibility. | `types.ts` | `logEvent` |
| `src/api/server.ts` | TypeScript | Express REST API server (port 3001). Merges delta + cognitive state. Serves control UI. Auto-starts governance daemon. | `types.ts`, `delta.ts`, `governance_daemon.ts`, `express`, `cors` | HTTP endpoints |
| `src/cli/app.ts` | TypeScript | Terminal TUI application. DeltaApp class. Keyboard controls (↑↓ Enter 1-7 n r s q). | `types.ts`, `renderer.ts`, `input.ts` | `DeltaApp` |
| `src/cli/index.ts` | TypeScript | CLI entry point. Launches DeltaApp. | `app.ts` | main() |
| `src/cli/renderer.ts` | TypeScript | Terminal rendering. ANSI colors, box drawing, mode color mapping. | `types.ts` | `render` |
| `src/cli/storage.ts` | TypeScript | JSON file persistence. Sync file I/O. Entities, deltas, dictionary stored as JSON. | `types.ts` | `saveEntity`, `loadEntity`, `appendDelta`, `saveDictionary` |
| `src/governance/governance_daemon.ts` | TypeScript | Autonomous scheduler. 6 cron jobs (heartbeat/5min, refresh/1hr, day_start/6am, day_end/10pm, mode_recalc/15min, work_queue/1min). | `types.ts`, `node-cron` | `startDaemon`, `DaemonState` |
| `web/src/App.tsx` | TypeScript/React | Browser dashboard. Mode display, task management, signal input. Fetches from API, falls back to localStorage. | `react` | React component |

### cognitive-sensor — Python Analysis Pipeline

| File Path | Type | Responsibility | Key Imports | Key Exports |
|-----------|------|---------------|-------------|-------------|
| `agent_excavator.py` | Python | Extract all ideas from 1,397 conversations. 36 intent patterns, 12 categories. | json, re, sqlite3, numpy, model_cache, validate | → excavated_ideas_raw.json |
| `agent_deduplicator.py` | Python | Merge duplicate ideas. UnionFind clustering. Cosine similarity (threshold 0.70). | json, base64, numpy, validate | → ideas_deduplicated.json |
| `agent_classifier.py` | Python | Classify ideas: status, skills, alignment, vision clusters, parent-child, dependencies. | json, re, base64, numpy, validate | → ideas_classified.json |
| `agent_classifier_convo.py` | Python | Tag all conversations: domain (6), outcome (4), emotional trajectory (5), intensity (3). | json, re, sqlite3, numpy, model_cache | → conversation_classifications.json |
| `agent_orchestrator.py` | Python | Priority scoring, tier assignment, execution order, gateway identification. Kahn's topological sort. | json, datetime, collections, validate | → idea_registry.json |
| `agent_reporter.py` | Python | Generate human-readable idea registry report. | json | → IDEA_REGISTRY.md |
| `agent_book_miner.py` | Python | Extract power dynamics passages. 20 semantic signatures, 12 chapter themes. | json, sqlite3, numpy, model_cache | → book_raw_material.json, BOOK_OUTLINE.md |
| `agent_synthesizer.py` | Python | Generate 30-question behavioral audit across 6 psychological layers. | json | → BEHAVIORAL_AUDIT.md |
| `atlas_agent.py` | Python | Unified governance runtime. Commands: run_daily, run_weekly, maintain_backlog, generate_briefs_only. | atlas_config, governor_daily, governor_weekly | Orchestration |
| `atlas_cli.py` | Python | CLI entry point. Commands: daily, weekly, backlog, briefs, status. | atlas_agent | CLI |
| `atlas_config.py` | Python | Single source of truth. North star, profile/kernel, autonomy levels, agent registry, active lanes, routing thresholds. | None (config) | CONFIG dict |
| `atlas_data.py` | Python | Load 384-dim message embeddings from results.db SQLite. | sqlite3, numpy | `load_embeddings()` |
| `atlas_graph.py` | Python | Construct cluster relationship graph (nodes + edges). | json, numpy | Graph structure |
| `atlas_layers.py` | Python | Build toggle layer arrays (cluster, role, time, conversation, leverage, graph). | json, numpy | Layer arrays |
| `atlas_layout.py` | Python | ForceAtlas2 force-directed layout (NumPy-based). | numpy | `compute_layout()` |
| `atlas_projection.py` | Python | UMAP dimensionality reduction + HDBSCAN clustering. ~207 clusters from 84K points. | umap, hdbscan, numpy | Cluster assignments |
| `atlas_render.py` | Python | Assemble JSON payload, fill HTML template. Produces self-contained cognitive_atlas.html. | json | → cognitive_atlas.html |
| `atlas_template.html` | HTML/JS | Interactive dashboard template. Plotly scatter + Sigma.js force graph + layer toggles. | Plotly, Sigma.js | Template |
| `governor_daily.py` | Python | Daily governance: ingest, state update, backlog maintenance, brief generation. Computes mode, lane violations, leverage moves. | atlas_config, json | → daily_brief.md, governance_state.json |
| `governor_weekly.py` | Python | Weekly aggregation, lane review, packet generation. | atlas_config, json | → weekly_governor_packet.md |
| `loops.py` | Python | Open loop detection. Topic-based scoring: intent words (+30) vs done words (-50). Threshold ≥18,000. | sqlite3, json | → loops_latest.json |
| `refresh.py` | Python | Master refresh pipeline. 10-step sequential orchestrator. | subprocess | Runs 10 scripts in sequence |
| `model_cache.py` | Python | Shared sentence-transformer model cache (all-MiniLM-L6-v2). Singleton pattern. | sentence_transformers | `get_model()`, `encode()` |
| `validate.py` | Python | JSON Schema contract validation. Validates outputs against contracts/schemas/. | jsonschema | `validate_output()` |
| `route_today.py` | Python | Determine today's mode from cognitive metrics. | json | Mode determination |
| `export_cognitive_state.py` | Python | Export cognitive state snapshot to JSON. | json | → cognitive_state.json |
| `export_daily_payload.py` | Python | Export daily directive, validates against DailyPayload.v1.json. | json, validate | → daily_payload.json |
| `wire_cycleboard.py` | Python | Copy state files to cycleboard/brain/ for dashboard consumption. | shutil | File copy |
| `push_to_delta.py` | Python | POST projection to Delta API (port 3001). | requests, json | HTTP POST |
| `build_cognitive_atlas.py` | Python | Thin wrapper orchestrating atlas build pipeline. | atlas_* modules | → cognitive_atlas.html |
| `build_dashboard.py` | Python | Build analytics HTML dashboard. | json | → dashboard.html |
| `build_strategic_priorities.py` | Python | Compute strategic priorities from idea registry. | json | → strategic_priorities.json |
| `cluster_leverage_map.py` | Python | Score conversation clusters by business value (5 metrics). | json, numpy | → leverage_map.json |
| `completion_stats.py` | Python | Track closure behavior metrics. | json, sqlite3 | → completion_stats.json |

### aegis-fabric — Policy Gate Service

| File Path | Type | Responsibility | Key Imports | Key Exports |
|-----------|------|---------------|-------------|-------------|
| `src/agents/agent-adapter.ts` | TypeScript | Normalize Claude/OpenAI/custom agents → CanonicalAgentAction. | types | `normalizeAction()` |
| `src/agents/action-processor.ts` | TypeScript | Process agent actions through policy pipeline. | policy-engine, approval-queue | `processAction()` |
| `src/agents/agent-registry.ts` | TypeScript | Manage agent registrations per tenant. | types, storage | Agent CRUD |
| `src/api/server.ts` | TypeScript | Express server (port 3002). CORS, middleware, route mounting. | express, cors, routes | HTTP server |
| `src/api/routes/agent-routes.ts` | TypeScript | POST /api/v1/agent/action — main action submission. | action-processor | Route handler |
| `src/api/routes/policy-routes.ts` | TypeScript | GET/POST policies, POST /simulate. | policy-store, policy-engine | Route handlers |
| `src/api/routes/approval-routes.ts` | TypeScript | GET approvals, POST approve/reject. | approval-queue | Route handlers |
| `src/api/routes/tenant-routes.ts` | TypeScript | Tenant CRUD. | tenant-registry | Route handlers |
| `src/api/routes/state-routes.ts` | TypeScript | GET entities by type. | entity-registry | Route handler |
| `src/api/routes/metrics-routes.ts` | TypeScript | GET system metrics. | metrics | Route handler |
| `src/api/routes/webhook-routes.ts` | TypeScript | Webhook subscription management. | webhook-dispatcher | Route handlers |
| `src/policies/policy-engine.ts` | TypeScript | **CORE**: 9 operators (eq/neq/in/not_in/gt/lt/gte/lte/exists), 3 effects (ALLOW/DENY/REQUIRE_HUMAN), first-match-wins. | types | `evaluatePolicy()` |
| `src/policies/decision-cache.ts` | TypeScript | Cache policy decisions (TTL configurable). | types | `getCachedDecision()`, `cacheDecision()` |
| `src/policies/policy-store.ts` | TypeScript | Load/save policy rules from file storage. | storage | Policy CRUD |
| `src/approval/approval-queue.ts` | TypeScript | Queue actions needing human review. Track status (PENDING/APPROVED/REJECTED/EXPIRED). | types, storage | `queueApproval()`, `decideApproval()` |
| `src/core/delta.ts` | TypeScript | Delta operations (mirrors delta-kernel pattern). | types | `createDelta()`, `applyPatch()` |
| `src/core/entity-registry.ts` | TypeScript | Entity store per tenant. | types, storage | Entity CRUD |
| `src/core/types.ts` | TypeScript | Aegis-specific type definitions. | None | All Aegis types |
| `src/cost/usage-tracker.ts` | TypeScript | Quota enforcement (max_agents, max_actions_per_hour). | types, storage | `checkQuota()`, `recordUsage()` |
| `src/events/audit-log.ts` | TypeScript | Immutable audit trail. | storage | `logAuditEvent()` |
| `src/events/event-bus.ts` | TypeScript | Internal event distribution. | None | `emit()`, `on()` |
| `src/events/webhook-dispatcher.ts` | TypeScript | Dispatch events to registered webhook URLs. | types | `dispatchWebhook()` |
| `src/storage/aegis-storage.ts` | TypeScript | File I/O wrapper for .aegis-data/. | fs, path | `readJSON()`, `writeJSON()` |
| `src/storage/snapshot-manager.ts` | TypeScript | Periodic state snapshots. | storage | `takeSnapshot()` |
| `src/tenants/tenant-registry.ts` | TypeScript | Multi-tenant management. | types, storage | Tenant CRUD |
| `src/tenants/tenant-isolation.ts` | TypeScript | Enforce tenant data boundaries. | types | `isolate()` |

### Top-Level Files

| File Path | Type | Responsibility |
|-----------|------|---------------|
| `atlas_boot.html` | HTML/JS | Master control dashboard (917 lines). 4-tab viewport, telemetry panel, command strip, 30s polling. |
| `PRE_ATLAS_MAP.md` | Markdown | Architecture reference (571 lines). Complete system map with diagrams. |
| `ONBOARDING.md` | Markdown | Developer onboarding (325 lines). Prerequisites, startup, gotchas. |
| `scripts/run_all.ps1` | PowerShell | Master orchestrator: start API → refresh → build projection → push to delta. |

---

## 4. Core Components

### Component 1: Mode Router
| Property | Value |
|----------|-------|
| **Name** | Deterministic Mode Router |
| **Location** | `services/delta-kernel/src/core/routing.ts` + `lut.ts` |
| **Responsibility** | Compute operational mode from 5 signals. Pure Markov lookup table. |
| **Inputs** | `{sleep_hours, open_loops, assets_shipped, deep_work_blocks, money_delta}` |
| **Outputs** | One of 6 modes: RECOVER, CLOSURE, MAINTENANCE, BUILD, COMPOUND, SCALE |
| **Dependencies** | `types.ts` |
| **Who Calls It** | `server.ts` (on state change), `governance_daemon.ts` (every 15 min), `daily-screen.ts`, `governor_daily.py` |

**Bucket Functions:**
- `sleep_hours`: <6 → LOW, ≥7.5 → HIGH, else OK
- `open_loops`: ≤1 → HIGH (good), ≥4 → LOW (bad), else OK
- `assets_shipped`: 0 → LOW, ≥2 → HIGH, else OK
- `deep_work_blocks`: 0 → LOW, ≥2 → HIGH, else OK
- `money_delta`: ≤0 → LOW, ≥target → HIGH, else OK

**Global Overrides (highest priority):**
1. sleep_hours == LOW → always RECOVER
2. open_loops == LOW (≥4) → always CLOSURE

### Component 2: Delta Engine
| Property | Value |
|----------|-------|
| **Name** | Delta State Engine |
| **Location** | `services/delta-kernel/src/core/delta.ts` |
| **Responsibility** | All state mutations through append-only, hash-chained deltas (RFC 6902 JSON Patch). |
| **Inputs** | Entity type + initial state (create), or entity ID + patch (mutate) |
| **Outputs** | `{entity, delta, state}` — new entity + immutable delta record + new state |
| **Dependencies** | `types.ts` |
| **Who Calls It** | `server.ts`, `storage.ts`, `preparation.ts`, `cockpit.ts`, all mutation paths |

### Component 3: Policy Engine
| Property | Value |
|----------|-------|
| **Name** | Aegis Policy Engine |
| **Location** | `services/aegis-fabric/src/policies/policy-engine.ts` |
| **Responsibility** | Evaluate declarative rules against agent actions. First-match-wins. |
| **Inputs** | `CanonicalAgentAction` + tenant policies + current mode |
| **Outputs** | `{effect: ALLOW|DENY|REQUIRE_HUMAN, matched_rule_id, reason}` |
| **Dependencies** | `types.ts`, `policy-store.ts`, `decision-cache.ts` |
| **Who Calls It** | `action-processor.ts` → `agent-routes.ts` |

### Component 4: Cognitive Refresh Pipeline
| Property | Value |
|----------|-------|
| **Name** | Refresh Pipeline |
| **Location** | `services/cognitive-sensor/refresh.py` |
| **Responsibility** | Orchestrate 10-step sequential analysis. Master pipeline entry point. |
| **Inputs** | results.db (SQLite), memory_db.json |
| **Outputs** | cognitive_state.json, daily_payload.json, dashboard.html, strategic_priorities.json, docs_manifest |
| **Dependencies** | All 10 sub-scripts it calls |
| **Who Calls It** | `run_all.ps1`, `governance_daemon.ts` (hourly cron) |

**10-Step Sequence:**
1. `loops.py` → open loop detection
2. `completion_stats.py` → closure behavior tracking
3. `export_cognitive_state.py` → state snapshot
4. `route_today.py` → determine mode
5. `export_daily_payload.py` → export directive
6. `wire_cycleboard.py` → wire dashboard
7. `reporter.py` → state history
8. `build_dashboard.py` → HTML dashboard
9. `build_strategic_priorities.py` → priorities
10. `build_docs_manifest.py` → doc index

### Component 5: Idea Intelligence Pipeline
| Property | Value |
|----------|-------|
| **Name** | Idea Intelligence System (8 Agents) |
| **Location** | `services/cognitive-sensor/agent_*.py` |
| **Responsibility** | Extract, deduplicate, classify, prioritize all ideas from conversation history. |
| **Inputs** | memory_db.json (1,397 conversations), results.db (embeddings) |
| **Outputs** | idea_registry.json (prioritized registry with tiers, execution sequence, gateway ideas) |
| **Dependencies** | model_cache.py, validate.py, numpy, sentence-transformers |
| **Who Calls It** | `run_agents.py` |

**Agent Chain:**
```
excavator → deduplicator → classifier → orchestrator → reporter
     ↓              ↓            ↓            ↓            ↓
excavated_    ideas_dedup   ideas_class   idea_reg    IDEA_REGISTRY.md
ideas_raw.json   .json        .json       .json
```

### Component 6: Governance Daemon
| Property | Value |
|----------|-------|
| **Name** | Governance Daemon |
| **Location** | `services/delta-kernel/src/governance/governance_daemon.ts` |
| **Responsibility** | Autonomous scheduler. 6 cron jobs. Auto-starts with API server. |
| **Inputs** | System clock, cognitive state (via refresh) |
| **Outputs** | Mode recalculations, work queue management, heartbeats |
| **Dependencies** | `node-cron`, `types.ts` |
| **Who Calls It** | `server.ts` (auto-start on API boot) |

**Cron Schedule:**
| Job | Cron | Purpose |
|-----|------|---------|
| heartbeat | `*/5 * * * *` | Health check |
| refresh | `0 * * * *` | Cognitive refresh (calls Python) |
| day_start | `0 6 * * *` | Morning setup |
| day_end | `0 22 * * *` | Evening summary |
| mode_recalc | `*/15 * * * *` | Autonomous mode governance |
| work_queue | `*/1 * * * *` | Work queue management |

### Component 7: Atlas Visualization
| Property | Value |
|----------|-------|
| **Name** | Cognitive Atlas |
| **Location** | `services/cognitive-sensor/atlas_*.py` + `atlas_template.html` |
| **Responsibility** | Interactive 84K-point visualization of conversation clusters with 6 toggle layers. |
| **Inputs** | results.db (384-dim embeddings), cluster data |
| **Outputs** | cognitive_atlas.html (5.9MB self-contained Plotly + Sigma.js dashboard) |
| **Dependencies** | umap-learn, hdbscan, numpy, Plotly, Sigma.js |
| **Who Calls It** | `build_cognitive_atlas.py` |

### Component 8: CycleBoard Dashboard
| Property | Value |
|----------|-------|
| **Name** | CycleBoard |
| **Location** | `services/cognitive-sensor/cycleboard/` |
| **Responsibility** | Real-time operational dashboard. Mode display, signals, strategic priorities. |
| **Inputs** | `brain/cognitive_state.json`, `brain/daily_payload.json`, `brain/daily_directive.txt`, `brain/strategic_priorities.json` |
| **Outputs** | Interactive HTML UI |
| **Dependencies** | 11 JS modules |
| **Who Calls It** | Loaded in `atlas_boot.html` as iframe |

### Component 9: Daily Cockpit
| Property | Value |
|----------|-------|
| **Name** | Daily Cockpit |
| **Location** | `services/delta-kernel/src/core/cockpit.ts` |
| **Responsibility** | Build command center state. MAX 7 prepared actions. 30-second PendingAction timeout. |
| **Inputs** | Mode, signals, tasks, drafts, threads |
| **Outputs** | `CockpitState` (signals, prepared_actions, top_tasks, drafts, leverage_moves) |
| **Dependencies** | `types.ts`, `delta.ts` |
| **Who Calls It** | `server.ts`, `daily-screen.ts` |

### Component 10: Preparation Engine
| Property | Value |
|----------|-------|
| **Name** | Preparation Engine |
| **Location** | `services/delta-kernel/src/core/preparation.ts` |
| **Responsibility** | Background draft generation. NEVER executes. MAX 5 drafts/run. Fingerprint dedup. |
| **Inputs** | Delta events, current mode, entities |
| **Outputs** | Draft entities (require human confirmation) |
| **Dependencies** | `types.ts`, `delta.ts`, `templates.ts` |
| **Who Calls It** | `server.ts`, `governance_daemon.ts` |

### Component 11: Work Admission Controller
| Property | Value |
|----------|-------|
| **Name** | Work Admission Controller |
| **Location** | `services/delta-kernel/src/core/work-controller.ts` |
| **Responsibility** | Universal work gate. 3 primitives: request(), complete(), status(). For humans AND machines. |
| **Inputs** | Job requests (type, title, weight, dependencies) |
| **Outputs** | Admission status (APPROVED/QUEUED/DENIED), work ledger |
| **Dependencies** | `types.ts` |
| **Who Calls It** | `governance_daemon.ts` (work_queue job), `server.ts` |

### Component 12: Matryoshka Dictionary
| Property | Value |
|----------|-------|
| **Name** | 3-Tier Compression Dictionary |
| **Location** | `services/delta-kernel/src/core/dictionary.ts` |
| **Responsibility** | Lossless hierarchical compression. Token → Pattern → Motif. Append-only. |
| **Inputs** | Raw text values |
| **Outputs** | Token/Pattern/Motif IDs (machine-addressable text) |
| **Dependencies** | `types.ts` |
| **Who Calls It** | `storage.ts` (persistence), future NLP pipeline |

### Component 13: Delta Sync Protocol
| Property | Value |
|----------|-------|
| **Name** | P2P Delta Sync |
| **Location** | `services/delta-kernel/src/core/delta-sync.ts` |
| **Responsibility** | LoRa-safe P2P state synchronization. 7 packet types. 220-byte max. Nonce-based auth. |
| **Inputs** | Entity heads from peers |
| **Outputs** | Synchronized deltas across nodes |
| **Dependencies** | `types.ts` |
| **Who Calls It** | Not yet wired into runtime (spec'd, code exists) |

### Component 14: Master Dashboard Shell
| Property | Value |
|----------|-------|
| **Name** | Atlas Boot |
| **Location** | `atlas_boot.html` (root) |
| **Responsibility** | Master control shell. 4-tab viewport, telemetry panel, command strip. 30s unified state polling. |
| **Inputs** | `GET /api/state/unified` (port 3001) |
| **Outputs** | Renders iframes: CycleBoard, Control Panel, Cognitive Atlas, Docs. Directive bar with mode/risk/loops. |
| **Dependencies** | Delta API (port 3001), cognitive-sensor HTML dashboards |
| **Who Calls It** | User opens in browser |

### Component 15: Governor (Daily + Weekly)
| Property | Value |
|----------|-------|
| **Name** | Atlas Governor |
| **Location** | `services/cognitive-sensor/governor_daily.py`, `governor_weekly.py` |
| **Responsibility** | Daily: mode compute, lane violations, leverage moves, brief generation. Weekly: aggregation, lane review. |
| **Inputs** | cognitive_state.json, idea_registry.json, conversation_classifications.json, completion_stats.json |
| **Outputs** | daily_brief.md, governance_state.json, weekly_governor_packet.md |
| **Dependencies** | `atlas_config.py` |
| **Who Calls It** | `atlas_agent.py` → `atlas_cli.py`, `governance_daemon.ts` |

---

## 5. Internal Data Models

### Model 1: SystemStateData (Delta-Kernel Core)
```typescript
{
  mode: "RECOVER" | "CLOSURE" | "MAINTENANCE" | "BUILD" | "COMPOUND" | "SCALE",
  signals: {
    sleep_hours: 7.5,        // Float, hours of sleep
    open_loops: 3,           // Int, unfinished conversations
    assets_shipped: 1,       // Int, assets shipped this week
    deep_work_blocks: 2,     // Int, 90-min focused blocks today
    money_delta: 500         // Float, revenue delta this period
  }
}
```
- **Produced by:** `routing.ts` (mode), `server.ts` (signals)
- **Consumed by:** `cockpit.ts`, `daily-screen.ts`, `App.tsx`, `atlas_boot.html`

### Model 2: Entity (Universal)
```typescript
{
  entity_id: "550e8400-e29b-41d4-a716-446655440000",  // UUID v4
  entity_type: "system_state",                          // One of 45 types
  created_at: 1709913600000,                            // Unix epoch ms
  current_version: 5,                                   // Incremented each delta
  current_hash: "a1b2c3d4...",                          // SHA256 of current state
  is_archived: false
}
```
- **Produced by:** `delta.ts` `createEntity()`
- **Consumed by:** All entity-consuming modules

### Model 3: Delta (Immutable Mutation Record)
```typescript
{
  delta_id: "660e8400-...",
  entity_id: "550e8400-...",
  timestamp: 1709913600000,
  author: { type: "SYSTEM", id: "governance_daemon" },
  patch: [
    { op: "replace", path: "/mode", value: "BUILD" }
  ],
  prev_hash: "a1b2c3d4...",
  new_hash: "e5f6g7h8..."
}
```
- **Produced by:** `delta.ts` on every state mutation
- **Consumed by:** `storage.ts` (append to deltas.json), `delta-sync.ts` (P2P transfer)

### Model 4: DailyPayload (CycleBoard Input)
```json
{
  "mode": "CLOSURE",
  "build_allowed": false,
  "primary_action": "Close 2 open loops before building",
  "open_loops": [
    { "convo_id": "abc123", "title": "API redesign discussion", "score": 24500 }
  ],
  "open_loop_count": 5,
  "closure_ratio": 12.5,
  "risk": "HIGH",
  "generated_at": "2026-03-09"
}
```
- **Produced by:** `export_daily_payload.py` (validates against DailyPayload.v1.json)
- **Consumed by:** CycleBoard UI (cycleboard/brain/daily_payload.json)

### Model 5: CognitiveState (Brain Snapshot)
```json
{
  "state": {
    "first_activity": "2024-01-15",
    "last_activity": "2026-03-09",
    "total_convos": 1397
  },
  "loops": [
    { "convo_id": "abc123", "title": "API redesign discussion", "score": 24500 }
  ],
  "drift": {
    "business": 0.35,
    "technical": 0.28,
    "personal": 0.15,
    "learning": 0.12,
    "processing": 0.07,
    "execution": 0.03
  },
  "closure": {
    "open": 42,
    "closed": 187,
    "ratio": 18.2
  }
}
```
- **Produced by:** `export_cognitive_state.py`
- **Consumed by:** `server.ts` (merged into unified state), CycleBoard, dashboards

### Model 6: IdeaRegistry (Idea Intelligence Output)
```json
{
  "metadata": {
    "generated_at": "2026-03-09T10:00:00Z",
    "total_ideas": 47,
    "tier_breakdown": { "execute_now": 3, "next_up": 8, "backlog": 24, "archive": 12 },
    "max_priority": 0.87,
    "avg_priority": 0.34
  },
  "tiers": {
    "execute_now": [{ "canonical_id": "idea_001", "canonical_title": "AI Consulting Service", "priority_score": 0.87, "tier": "execute_now" }]
  },
  "execution_sequence": ["idea_001", "idea_005", "idea_003"],
  "gateway_ideas": ["idea_001"],
  "vision_clusters": [{ "cluster_id": "vc_1", "theme": "AI Services", "ideas": ["idea_001", "idea_005"] }],
  "full_registry": [{ "canonical_id": "idea_001", "priority_score": 0.87, "complexity": 0.65, "alignment_score": 0.92, "skills_required": ["python", "ai_ml"], "dependencies": [], "version_timeline": [{ "date": "2024-06", "source_convo": "abc123" }] }]
}
```
- **Produced by:** `agent_orchestrator.py`
- **Consumed by:** `governor_daily.py`, idea_dashboard.html, CycleBoard

### Model 7: GovernanceState (Daily Governance)
```json
{
  "mode": "CLOSURE",
  "risk": "HIGH",
  "active_lanes": [
    { "name": "Power Dynamics Book", "status": "active", "health": "on_track" },
    { "name": "AI Consulting", "status": "active", "health": "stalled" }
  ],
  "violations": [],
  "leverage_moves": [
    "Close the API redesign loop — it blocks 3 downstream tasks",
    "Ship book chapter 1 draft — compounds into marketing",
    "Archive 5 stale idea loops — reduce cognitive overhead"
  ],
  "world_changed": [
    "Closure ratio dropped below 15% (now 12.5%)",
    "2 new loops opened without closing existing ones",
    "AI consulting lane health degraded to stalled"
  ],
  "generated_at": "2026-03-09T06:00:00Z"
}
```
- **Produced by:** `governor_daily.py`
- **Consumed by:** `atlas_boot.html` (via unified state), CycleBoard

### Model 8: ConversationClassification
```json
{
  "convo_id": "abc123",
  "domain": "business",
  "outcome": "produced",
  "emotional_trajectory": "positive",
  "intensity": "high",
  "domain_confidence": 0.82
}
```
- **Produced by:** `agent_classifier_convo.py`
- **Consumed by:** `governor_daily.py`, `agent_synthesizer.py`, dashboards

### Model 9: CockpitState (Daily Command Center)
```typescript
{
  timestamp: 1709913600000,
  mode: "BUILD",
  mode_since: 1709827200000,
  signals: {
    sleep_hours: { raw: 7.5, bucket: "HIGH", label: "Well rested", is_critical: false },
    open_loops: { raw: 2, bucket: "OK", label: "2 open loops", is_critical: false }
  },
  prepared_actions: [
    { slot: 1, action_id: "act_001", action_type: "create_asset", label: "Ship API client", priority: "HIGH", is_overdue: false }
  ],
  top_tasks: [
    { task_id: "task_001", title: "Write API docs", priority: "HIGH", due_at: 1710000000000, is_overdue: false, mode_relevance: 0.9 }
  ],
  drafts: [],
  leverage_moves: [
    { move_id: "lev_001", description: "Ship API client — compounds into 3 downstream projects", impact: 0.85, trigger_hint: "Start with the auth module" }
  ]
}
```
- **Produced by:** `cockpit.ts`
- **Consumed by:** `server.ts`, `renderer.ts` (CLI), `App.tsx` (web)

### Model 10: WorkLedger (Work Admission)
```typescript
{
  active: [
    { job_id: "job_001", type: "human", title: "Write Chapter 1", weight: 1.0, started_at: 1709913600000, timeout_at: null, depends_on: [] }
  ],
  queued: [],
  completed: [
    { job_id: "job_000", type: "ai", title: "Classify conversations", outcome: "completed", duration_ms: 45000, cost_usd: 0.12 }
  ],
  stats: { total_completed: 47, total_failed: 2, avg_duration_ms: 38000, total_cost_usd: 3.50 },
  config: { max_concurrent_jobs: 3, max_queue_depth: 10, default_timeout_ms: 3600000, allow_ai_in_closure_mode: false }
}
```
- **Produced by:** `work-controller.ts`
- **Consumed by:** `governance_daemon.ts`, `server.ts`

### Model 11: PolicyRule (Aegis)
```json
{
  "rule_id": "rule_001",
  "name": "Block task creation in CLOSURE",
  "priority": 100,
  "description": "Prevent new task creation when in CLOSURE mode",
  "conditions": [
    { "field": "mode", "operator": "eq", "value": "CLOSURE" },
    { "field": "action", "operator": "eq", "value": "create_task" }
  ],
  "effect": "DENY",
  "reason": "Must close existing loops before creating new tasks",
  "enabled": true
}
```
- **Produced by:** Tenant admin (manual)
- **Consumed by:** `policy-engine.ts`

### Model 12: AtlasConfig (Governance Rules)
```python
CONFIG = {
  "north_star": "Ship 1 asset per week",
  "max_active_lanes": 2,
  "active_lanes": ["Power Dynamics Book", "AI Consulting"],
  "idea_moratorium": True,  # No new ideas until current lanes ship
  "targets": {
    "min_closure_ratio": 15,  # Percent
    "max_open_loops": 20,
    "daily_work_blocks": 3,   # 90-min blocks
    "research_cap_minutes": 30
  },
  "autonomy_levels": {
    "ADVISORY": 0,       # Suggest only
    "DRAFT_ROUTE": 1,    # Generate actionable decisions
    "EXECUTE_REPORT": 2, # Execute + report
    "SILENT": 3          # Execute silently
  },
  "routing_thresholds": {
    "closure_ratio_critical": 15,
    "open_loops_caution": 10
  }
}
```
- **Produced by:** Manual config in `atlas_config.py`
- **Consumed by:** `governor_daily.py`, `governor_weekly.py`, `atlas_agent.py`

---

## 6. Execution Flow

### Full System Startup
```
User runs: scripts/run_all.ps1
    │
    ├── 1. Start Delta API
    │       └── npm run api (services/delta-kernel/)
    │           └── tsx src/api/server.ts
    │               ├── Express server on port 3001
    │               ├── Load entities.json + deltas.json from .delta-fabric/
    │               ├── Auto-start governance_daemon.ts
    │               │   └── Schedule 6 cron jobs
    │               └── Serve UI from src/ui/
    │
    ├── 2. Wait 3 seconds
    │
    ├── 3. Run Cognitive Refresh
    │       └── python services/cognitive-sensor/refresh.py
    │           ├── loops.py           → loops_latest.json
    │           ├── completion_stats.py → completion_stats.json
    │           ├── export_cognitive_state.py → cognitive_state.json
    │           ├── route_today.py     → mode determination
    │           ├── export_daily_payload.py → daily_payload.json
    │           ├── wire_cycleboard.py → copy to cycleboard/brain/
    │           ├── reporter.py        → STATE_HISTORY.md
    │           ├── build_dashboard.py → dashboard.html
    │           ├── build_strategic_priorities.py → strategic_priorities.json
    │           └── build_docs_manifest.py → docs_manifest.json
    │
    ├── 4. Build Projection
    │       └── python services/cognitive-sensor/build_projection.py
    │           └── Merge cognitive + directive → data/projections/today.json
    │
    └── 5. Push to Delta
            └── python services/cognitive-sensor/push_to_delta.py
                └── POST data/projections/today.json → localhost:3001/api/ingest/cognitive
```

### Ongoing Operation (After Startup)
```
Every 1 minute:   governance_daemon → work_queue management
Every 5 minutes:  governance_daemon → heartbeat
Every 15 minutes: governance_daemon → mode_recalc (re-evaluate mode from signals)
Every 1 hour:     governance_daemon → cognitive refresh (re-run Python pipeline)
Every 30 seconds: atlas_boot.html → GET /api/state/unified (browser poll)
On demand:        User clicks Acknowledge/Archive/Refresh in atlas_boot.html
                  → POST /api/law/acknowledge or /api/law/archive or /api/law/refresh
```

### AI Agent Action Flow
```
AI Agent → POST /api/v1/agent/action (port 3002, aegis-fabric)
    │
    ├── 1. agent-adapter.ts: Normalize to CanonicalAgentAction
    ├── 2. tenant-registry.ts: Look up tenant config
    ├── 3. usage-tracker.ts: Check quota
    ├── 4. Fetch current mode from Delta API (port 3001)
    ├── 5. policy-store.ts: Load tenant policy rules
    ├── 6. policy-engine.ts: Evaluate rules (first-match-wins)
    │       ├── ALLOW → Execute action, create delta, return 200
    │       ├── DENY → Return 403 with reason
    │       └── REQUIRE_HUMAN → Queue for approval, return 202
    └── 7. audit-log.ts: Log decision
         webhook-dispatcher.ts: Notify subscribers
```

### Idea Intelligence Pipeline
```
python run_agents.py
    │
    ├── agent_excavator.py
    │   └── Scan 1,397 conversations → excavated_ideas_raw.json
    │
    ├── agent_deduplicator.py
    │   └── Merge duplicates (cosine sim ≥0.70) → ideas_deduplicated.json
    │
    ├── agent_classifier.py
    │   └── Classify (status, skills, alignment, clusters) → ideas_classified.json
    │
    ├── agent_orchestrator.py
    │   └── Priority score + tier + execution order → idea_registry.json
    │
    └── agent_reporter.py
        └── Generate human-readable report → IDEA_REGISTRY.md
```

---

## 7. Runtime State

| State Type | Where Written | Where Read | Lifecycle |
|-----------|--------------|------------|-----------|
| `.delta-fabric/entities.json` | `storage.ts` (delta-kernel) | `server.ts`, `storage.ts` | Persistent. Created on first run. Updated on every entity mutation. |
| `.delta-fabric/deltas.json` | `storage.ts` | `storage.ts`, `server.ts` | Persistent. Append-only. Never deleted. Grows indefinitely. |
| `.delta-fabric/dictionary.json` | `storage.ts` | `storage.ts` | Persistent. Append-only (tokens, patterns, motifs never removed). |
| `.aegis-data/tenants.json` | `tenant-registry.ts` | `tenant-registry.ts` | Persistent. Updated on tenant CRUD. |
| `.aegis-data/usage.json` | `usage-tracker.ts` | `usage-tracker.ts` | Persistent. Updated on every agent action. |
| `.aegis-data/tenants/<uuid>/entities.json` | `entity-registry.ts` | `entity-registry.ts` | Persistent. Per-tenant entity state. |
| `.aegis-data/tenants/<uuid>/deltas.json` | `entity-registry.ts` | `entity-registry.ts` | Persistent. Per-tenant append-only delta log. |
| `results.db` (SQLite) | `init_*.py` scripts | All Python analysis scripts | Persistent. ~140MB. Contains messages, topics, embeddings, titles, dates. Git-ignored. |
| `memory_db.json` | External (user's chat history) | `agent_excavator.py`, `agent_classifier_convo.py`, `agent_book_miner.py` | Static input. 1,397 conversations. Not modified by system. |
| `cognitive_state.json` | `export_cognitive_state.py` | `server.ts`, CycleBoard, dashboards | Regenerated on every refresh cycle. |
| `daily_payload.json` | `export_daily_payload.py` | CycleBoard (brain/daily_payload.json) | Regenerated daily. |
| `governance_state.json` | `governor_daily.py` | `atlas_boot.html` (via unified state) | Regenerated daily. |
| `idea_registry.json` | `agent_orchestrator.py` | `governor_daily.py`, idea_dashboard.html | Regenerated on agent pipeline run. |
| `loops_latest.json` | `loops.py` | `server.ts`, dashboards | Regenerated on every refresh cycle. |
| `strategic_priorities.json` | `build_strategic_priorities.py` | CycleBoard | Regenerated on refresh. |
| `completion_stats.json` | `completion_stats.py` | `governor_daily.py` | Regenerated on refresh. |
| `conversation_classifications.json` | `agent_classifier_convo.py` | `governor_daily.py`, `agent_synthesizer.py` | Regenerated on agent pipeline run. |
| In-memory: Express state (server.ts) | In-process | API request handlers | Lost on restart. Rebuilt from files on boot. |
| In-memory: Daemon state | `governance_daemon.ts` | `governance_daemon.ts` | Lost on restart. Job history and heartbeat tracking. |
| `localStorage` (browser) | `App.tsx`, `atlas_boot.html` | Same | Per-browser. Fallback when API unavailable. |

---

## 8. Configuration and Environment

### Environment Variables
| Variable | Purpose | Default | Used By |
|----------|---------|---------|---------|
| `DELTA_DATA_DIR` | Override delta state directory | `~/.delta-fabric/` | `server.ts`, `storage.ts` |
| `PORT` | API server port (delta-kernel) | 3001 | `server.ts` |

### Configuration Files
| File | Purpose | Influence |
|------|---------|-----------|
| `services/delta-kernel/package.json` | Node project config. Scripts: start, api, gate, test, build. | Defines entry points and dependencies. |
| `services/delta-kernel/tsconfig.json` | TypeScript compilation settings. ES modules. | Controls type checking strictness. |
| `services/delta-kernel/start.bat` | Windows startup script. Launches API + web UI. | Sets DELTA_DATA_DIR, waits 5s between services. |
| `services/cognitive-sensor/requirements.txt` | Python dependencies. | sentence-transformers, numpy, scikit-learn, umap-learn, hdbscan, pytest. |
| `services/cognitive-sensor/pyproject.toml` | Pytest configuration. Test path: tests/. | Defines test markers (slow for UMAP/HDBSCAN). |
| `services/cognitive-sensor/atlas_config.py` | **Master governance config.** North star, active lanes, routing thresholds, agent registry, autonomy levels. | Controls all governance decisions. Single source of truth. |
| `services/aegis-fabric/package.json` | Aegis Node project config. | Dependencies and scripts. |
| `services/aegis-fabric/tsconfig.json` | Aegis TypeScript config. | Type checking. |
| `contracts/schemas/*.json` | JSON Schema (draft-07) data contracts. | Validation boundary between Python and TypeScript services. |
| `.claude/settings.local.json` | Claude Code workspace permissions. | Restricts IDE tool usage. |
| `.gitignore` | Git ignore rules. | Excludes .delta-fabric/, .aegis-data/, results.db, generated HTML, PDFs. |

### Runtime Parameters (Hardcoded Constants)
| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| MAX_PREPARED_ACTIONS | 7 | cockpit.ts | Max actions shown in cockpit |
| PENDING_ACTION_TIMEOUT_MS | 30,000 | cockpit.ts | Action confirmation window |
| MAX_DRAFTS_PER_RUN | 5 | preparation.ts | Draft generation limit |
| MAX_LEVERAGE_MOVES | 3 | preparation.ts | Strategic moves limit |
| MIN_CONFIDENCE | 0.5 | vector-discovery.ts | Discovery proposal minimum |
| MAX_PROPOSALS_PER_JOB | 10 | vector-discovery.ts | Discovery output limit |
| DEFAULT_MAX_PACKET_BYTES | 220 | delta-sync.ts | LoRa packet size limit |
| CHUNK_PAYLOAD_SIZE | 150 | delta-sync.ts | Sync chunk size |
| SAME_THRESHOLD | 0.70 | agent_deduplicator.py | Cosine sim for same idea |
| RELATED_THRESHOLD | 0.55 | agent_deduplicator.py | Cosine sim for related ideas |
| VISION_CLUSTER_THRESHOLD | 0.55 | agent_classifier.py | Cluster grouping threshold |
| PARENT_CHILD_THRESHOLD | 0.50 | agent_classifier.py | Hierarchy detection |
| OPEN_LOOP_THRESHOLD | 18,000 | loops.py | Score threshold for open loop |
| TIER_THRESHOLDS | 0.45/0.30/0.12 | agent_orchestrator.py | execute_now/next_up/backlog |

---

## 9. External Dependencies

### TypeScript (delta-kernel + aegis-fabric)
| Dependency | Version | Purpose | Used By |
|-----------|---------|---------|---------|
| express | 5.2.1 | HTTP server framework | server.ts (both services) |
| cors | 2.8.5 | Cross-origin resource sharing | server.ts (both services) |
| node-cron | 4.2.1 | Cron job scheduling | governance_daemon.ts |
| tsx | (dev) | TypeScript execution | CLI entry point, API server |
| typescript | 5.3.0 | TypeScript compiler | Build step |
| react | 19.2.0 | UI framework | web/src/App.tsx |
| react-dom | 19.2.0 | React DOM rendering | web/src/main.tsx |
| vite | 7.2.4 | Frontend build tool | web/vite.config.ts |

### Python (cognitive-sensor)
| Dependency | Version | Purpose | Used By |
|-----------|---------|---------|---------|
| sentence-transformers | ≥2.2.0 | Sentence embedding (all-MiniLM-L6-v2, 384-dim) | model_cache.py → agents |
| numpy | ≥1.24.0 | Numerical computation, cosine similarity, matrix ops | All agents, atlas modules |
| scikit-learn | ≥1.3.0 | Machine learning utilities | Clustering support |
| umap-learn | ≥0.5.5 | UMAP dimensionality reduction (384-dim → 2D) | atlas_projection.py |
| hdbscan | ≥0.8.33 | Density-based clustering (~207 clusters from 84K points) | atlas_projection.py |
| pytest | ≥7.0.0 | Testing framework | tests/ |
| jsonschema | (implied) | JSON Schema validation | validate.py |
| fpdf2 | (implied) | PDF generation | data/build_pdf.py |
| sqlite3 | (stdlib) | SQLite database access | loops.py, agents, atlas_data.py |
| requests | (implied) | HTTP client | push_to_delta.py |

### Frontend (CDN/Embedded)
| Dependency | Purpose | Used By |
|-----------|---------|---------|
| Plotly.js | Interactive scatter plots (84K points) | atlas_template.html |
| Sigma.js | Force-directed graph visualization | atlas_template.html |

### Next.js (blueprint-generator)
| Dependency | Version | Purpose |
|-----------|---------|---------|
| next | 15 | React framework |
| react | 19 | UI |

---

## 10. Custom or Unconventional Mechanisms

### 10.1 Hash-Chained Append-Only Deltas
Every state mutation in the system is recorded as an immutable delta with a cryptographic hash chain:
```
Delta N: { patch: [...], prev_hash: "abc", new_hash: "def" }
Delta N+1: { patch: [...], prev_hash: "def", new_hash: "ghi" }
```
- Each delta contains the previous state hash and the new state hash
- The chain is verified on read — any gap or fork is detectable
- Entities are never mutated directly; only deltas are applied
- This creates a full audit trail and enables P2P sync with conflict detection
- **Known Issue:** 10 fork points exist from concurrent writes without file locking (documented in HASH_CHAIN_FORKS.md)

### 10.2 Deterministic Markov Mode Routing
Mode transitions are computed by a pure lookup table — NOT AI, NOT heuristics:
```
Input: 5 signals → 5 bucket functions → mode lookup
```
- Each signal is bucketed (LOW/OK/HIGH) via hardcoded threshold functions
- Global overrides take priority (sleep LOW → always RECOVER, loops ≥4 → always CLOSURE)
- The routing is completely deterministic and reproducible
- This is a core philosophical choice: the system does NOT use AI to decide what mode you're in

### 10.3 Matryoshka 3-Tier Compression Dictionary
A custom hierarchical compression scheme (not standard):
```
Tier 1: Token Dictionary    — Atomic units (words, short phrases)
Tier 2: Pattern Dictionary   — Sequences of tokens (templates, common phrases)
Tier 3: Motif Dictionary     — Sequences of patterns (complex structures with slots)
```
- Append-only: tokens/patterns/motifs never deleted
- Promotion is permanent: once a pattern becomes a motif, it never reverts
- Reverse lookup enabled: value → token_id, JSON(sequence) → pattern_id
- Purpose: Make all text machine-addressable with minimal bandwidth for LoRa sync

### 10.4 Constitutional Law Genesis Layer
Inside `delta.ts`, the `ensurePathExists()` function implements what's called the "Law Genesis Layer":
- Before applying a JSON Patch leaf operation (replace, add), it ensures all parent path nodes exist
- This prevents state corruption from partial patches
- The metaphor is constitutional: state transitions must be structurally valid, like a state machine

### 10.5 LoRa-Safe P2P Sync Protocol
The delta-sync module is designed for extreme low-bandwidth scenarios:
- Max packet size: 220 bytes (LoRa constraint)
- Chunk payload: 150 bytes
- 7 packet types with a nonce-based handshake
- Entity priority map: system_state syncs first, patterns/motifs sync last
- 3-tier node classification: CORE (full), EDGE (limited), MICRO (token-only)
- Designed for off-grid/solar-powered operation

### 10.6 Proposal-Only Architecture
A fundamental architectural constraint: **preparation, discovery, and AI design modules NEVER execute directly**:
- `preparation.ts` generates Draft entities → require human confirmation
- `vector-discovery.ts` generates DiscoveryProposal entities → require human review
- `ai-design.ts` generates DesignProposal entities → compile to deterministic LUTs only after human review
- The PendingAction confirmation gate has a 30-second timeout
- This ensures the human is always in the loop

### 10.7 Dual-Language Pipeline with JSON Schema Contracts
Python (cognitive-sensor) and TypeScript (delta-kernel + aegis-fabric) communicate through:
- JSON files validated against shared JSON Schema (draft-07) contracts in `contracts/schemas/`
- Python validates outputs before writing; TypeScript validates on ingestion
- The push_to_delta.py script bridges Python → TypeScript via HTTP POST
- This creates a clean boundary between analysis (Python) and state management (TypeScript)

### 10.8 Open Loop Detection by Topic Scoring
Loop detection uses a custom scoring algorithm (not standard NLP):
```
score = user_words + (intent_weight × 30) - (done_weight × 50)
```
- Intent topics: "want", "need", "should", "plan", "build", etc. (+30 per match)
- Done topics: "did", "done", "finished", etc. (-50 per match)
- Threshold: score ≥ 18,000 = open loop
- This identifies conversations where the user expressed intent but never followed through

### 10.9 Idea Priority Scoring (Weighted Composite)
Ideas are ranked by a composite score:
```
priority = (frequency × 0.20) + (recency × 0.20) + (alignment × 0.25) + (feasibility × 0.15) + (compounding × 0.20)
```
- Alignment uses a psychological profile (core values, strengths)
- Compounding measures how much an idea enables other ideas
- Gateway ideas are identified: ideas that unlock the most downstream projects
- Topological sort (Kahn's algorithm) respects dependency ordering

### 10.10 Behavioral Governance with Lane Enforcement
The system enforces a 2-lane limit on active work:
- Only 2 active lanes at a time (e.g., "Power Dynamics Book" + "AI Consulting")
- Idea moratorium: no new ideas accepted until current lanes ship
- Lane violations detected by `governor_daily.py`
- Research cap: 30 minutes before must build
- Daily work blocks: 3 × 90-minute minimum

---

## 11. System Interaction Graph

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                            │
│                      atlas_boot.html                             │
│              (30s poll, commands, 4-tab viewport)                 │
└───────────────┬──────────────────────────────────┬───────────────┘
                │ GET /api/state/unified            │ iframe loads
                │ POST /api/law/*                   │
                ▼                                   ▼
┌───────────────────────────┐     ┌─────────────────────────────────┐
│   DELTA-KERNEL (port 3001)│     │  COGNITIVE-SENSOR (HTML/JS)     │
│                           │     │  cycleboard/index.html           │
│  ┌─────────────────────┐  │     │  dashboard.html                  │
│  │ server.ts            │  │     │  control_panel.html              │
│  │  - Express API       │  │     │  cognitive_atlas.html            │
│  │  - Unified state     │  │     │  docs_viewer.html                │
│  │  - Entity/Delta CRUD │  │     │  idea_dashboard.html             │
│  └─────┬───────────┬────┘  │     └─────────────────────────────────┘
│        │           │       │                    ▲
│        ▼           ▼       │                    │ wire_cycleboard.py
│  ┌──────────┐ ┌─────────┐ │     ┌──────────────┴───────────────────┐
│  │delta.ts  │ │daemon.ts│ │     │  COGNITIVE-SENSOR (Python)        │
│  │storage.ts│ │(6 cron) │ │     │                                   │
│  └──────────┘ └────┬────┘ │     │  refresh.py (10-step pipeline)    │
│                    │       │     │    ├── loops.py                   │
│  ┌─────────────────┘       │     │    ├── completion_stats.py       │
│  │ hourly: run refresh     │     │    ├── export_cognitive_state.py │
│  │ 15min: mode_recalc      │     │    ├── route_today.py            │
│  └──────────────┬──────────┘     │    ├── export_daily_payload.py   │
│                 │                │    └── ... (5 more steps)        │
│                 │                │                                   │
│                 ▼                │  run_agents.py (idea pipeline)    │
│  .delta-fabric/                 │    ├── agent_excavator.py         │
│    entities.json                │    ├── agent_deduplicator.py      │
│    deltas.json                  │    ├── agent_classifier.py        │
│    dictionary.json              │    ├── agent_orchestrator.py      │
│                                 │    └── agent_reporter.py          │
└─────────────────────────────────│                                   │
                ▲                 │  atlas_agent.py (governance)      │
                │                 │    ├── governor_daily.py           │
                │ POST /api/      │    └── governor_weekly.py         │
                │ ingest/         │                                   │
                │ cognitive       │  atlas_projection.py (UMAP)       │
                │                 │  atlas_layout.py (ForceAtlas2)     │
                │                 │  atlas_render.py → atlas.html      │
                │                 └──────┬────────────────────────────┘
                │                        │
                │    push_to_delta.py ───┘
                │
                │
┌───────────────┴──────────────────────────────────────────────────┐
│                    AEGIS-FABRIC (port 3002)                       │
│                                                                   │
│  POST /api/v1/agent/action                                       │
│    │                                                             │
│    ├── agent-adapter.ts (normalize Claude/OpenAI → canonical)    │
│    ├── tenant-registry.ts (lookup tenant config)                 │
│    ├── usage-tracker.ts (check quota)                            │
│    ├── policy-engine.ts (evaluate rules, first-match-wins)       │
│    │     ├── ALLOW → execute + create delta                      │
│    │     ├── DENY → return 403                                   │
│    │     └── REQUIRE_HUMAN → queue for approval                  │
│    ├── approval-queue.ts (human review)                          │
│    ├── audit-log.ts (immutable log)                              │
│    └── webhook-dispatcher.ts (notify subscribers)                │
│                                                                   │
│  .aegis-data/                                                    │
│    tenants.json                                                  │
│    usage.json                                                    │
│    tenants/<uuid>/entities.json + deltas.json                    │
└──────────────────────────────────────────────────────────────────┘

                        ▼
              contracts/schemas/
              (15 JSON Schema contracts)
              (shared validation boundary)

                        ▼
              results.db (SQLite, 140MB)
              memory_db.json (1,397 convos)
              (static input data)
```

### Data Flow Summary
```
memory_db.json (static input, 93K messages)
    ↓
init_*.py scripts → results.db (embeddings, topics, titles)
    ↓
refresh.py pipeline → cognitive_state.json + daily_payload.json
    ↓
push_to_delta.py → Delta API (port 3001) → .delta-fabric/
    ↓
atlas_boot.html → GET /api/state/unified → browser display
    ↓
AI Agent → POST to Aegis (port 3002) → policy evaluation → execute or deny
```

---

## 12. Areas of Complexity or Risk

### 12.1 Hash Chain Fork Problem
- **Location:** `.delta-fabric/deltas.json`
- **Issue:** 10 known fork points from concurrent writes (governance daemon + API handling simultaneously). No file locking mechanism exists.
- **Impact:** Hash chain verification fails at fork points. Documented in HASH_CHAIN_FORKS.md but not programmatically resolved.

### 12.2 Pre-existing TypeScript Type Errors
- **Location:** `server.ts`, `renderer.ts`, `ai-design.ts`, `camera-stream.ts`
- **Issue:** Interface mismatches (SystemStateData shape, Author type, DraftData shape). These are NOT from Mode changes — they're structural type drift.
- **Impact:** TypeScript compilation produces errors. Runtime works because tsx skips strict checking.

### 12.3 Dual Routing Implementations
- **Location:** `routing.ts` AND `lut.ts` (delta-kernel), `route_today.py` (cognitive-sensor)
- **Issue:** Three separate mode routing implementations that may diverge. The Python version operates on different thresholds than the TypeScript versions.
- **Impact:** Mode could be computed differently depending on which code path is hit.

### 12.4 File-Based State Without Locking
- **Location:** `.delta-fabric/`, `.aegis-data/`
- **Issue:** JSON files are read and written without file locks. Concurrent processes (daemon + API + Python scripts) can corrupt state.
- **Impact:** Race conditions on write. The hash chain forks (12.1) are a symptom of this.

### 12.5 Large Static Input Dependency
- **Location:** `memory_db.json` (~140MB), `results.db` (~large)
- **Issue:** The entire analysis pipeline depends on a single large JSON file that's never updated by the system. If the user's conversation history grows, the file must be manually replaced.
- **Impact:** System becomes stale without manual data refresh.

### 12.6 Tight Coupling Between Python Export and TypeScript Ingestion
- **Location:** `export_daily_payload.py` → `push_to_delta.py` → `server.ts`
- **Issue:** The Python-to-TypeScript bridge relies on exact JSON field names matching. Schema validation catches mismatches, but there's no auto-generation from a shared source.
- **Impact:** Schema drift between services could cause silent data loss.

### 12.7 Cognitive Atlas Size
- **Location:** `cognitive_atlas.html` (5.9MB self-contained)
- **Issue:** Single HTML file embedding 84K data points + Plotly + Sigma.js. Slow to load, hard to iterate on.
- **Impact:** Browser performance issues. Not incrementally updatable.

### 12.8 Spec-to-Implementation Gap
- **Location:** `specs/` (19 documents) vs actual code
- **Issue:** Modules 6-11 (delta-sync, off-grid-node, ui-stream, camera-stream, actuation, audio) have TypeScript type definitions and structures but limited runtime wiring. They exist as spec'd code but aren't integrated into the main execution flow.
- **Impact:** ~50% of delta-kernel's modules are structurally complete but not functionally connected.

### 12.9 Governance Config Hardcoded in Python
- **Location:** `atlas_config.py`
- **Issue:** All governance rules (north star, lane limits, thresholds) are hardcoded in a Python file. No API to update them. No TypeScript equivalent.
- **Impact:** Changing governance rules requires code changes and redeployment.

---

## 13. Missing or Incomplete Layers

### 13.1 Unified Launcher
- **Current State:** `scripts/run_all.ps1` (Windows-only PowerShell) with hardcoded wait times
- **What's Missing:** A cross-platform, dependency-aware launcher that:
  - Starts services in correct order with health checks (not `sleep 3`)
  - Verifies each service is healthy before starting the next
  - Provides unified stop/restart
  - Works on Mac/Linux
- **Where It Would Logically Exist:** Root-level `launcher.ts` or `docker-compose.yml` (the aegis-fabric has one but it's unused)

### 13.2 Refresh Protocol (Bidirectional)
- **Current State:** Python pushes to Delta API via HTTP POST. One-way.
- **What's Missing:** A bidirectional protocol where:
  - Delta-kernel can request cognitive refresh on demand (not just cron)
  - Cognitive-sensor can subscribe to delta events
  - State changes propagate in real-time, not on 30-second polls
- **Where It Would Logically Exist:** WebSocket connection between services, or event bus

### 13.3 Database Layer
- **Current State:** File-based JSON storage (no locking, no transactions, no indices)
- **What's Missing:** Proper database for:
  - Concurrent access safety (file lock → transactions)
  - Query efficiency (full file reads → indexed queries)
  - State recovery (corrupted JSON → WAL/journaling)
- **Where It Would Logically Exist:** SQLite (already used in cognitive-sensor), PostgreSQL (docker-compose exists but unused)

### 13.4 Authentication / Access Control
- **Current State:** No auth on either API. Anyone on localhost can call any endpoint.
- **What's Missing:** API key validation, tenant authentication, session management
- **Where It Would Logically Exist:** `aegis-fabric/src/gateway/api-middleware.ts` (structure exists, not fully implemented)

### 13.5 Error Recovery / Self-Healing
- **Current State:** If a cron job fails, it's logged in `job_history` but not retried automatically. If JSON is corrupted, the system crashes.
- **What's Missing:** Retry logic with exponential backoff, state file backup/restore, corruption detection and recovery
- **Where It Would Logically Exist:** `governance_daemon.ts` (retry wrapper), `storage.ts` (backup on write)

### 13.6 Test Coverage for Runtime
- **Current State:** Cognitive-sensor has 7 pytest files for atlas modules. Aegis-fabric has 7 test files. Delta-kernel has `fabric-tests.ts`.
- **What's Missing:** Integration tests that verify the full pipeline (Python refresh → push → API → dashboard rendering)
- **Where It Would Logically Exist:** Root-level `tests/` or `scripts/test_integration.sh`

### 13.7 Configuration API
- **Current State:** Config is hardcoded in `atlas_config.py` (Python) and constants in TypeScript files
- **What's Missing:** API endpoints to update governance config at runtime (north star, lane limits, thresholds)
- **Where It Would Logically Exist:** `server.ts` (delta-kernel) or `atlas_agent.py` admin endpoints

---

## 14. System Summary for External AI

Pre Atlas is a **personal behavioral governance system** built as a federated monorepo with three services:

**What it does:** It analyzes 1,397 historical conversations (93,898 messages) to compute an operational mode (RECOVER/CLOSURE/MAINTENANCE/BUILD/COMPOUND/SCALE), then enforces that mode through policy gates that approve or deny AI agent actions. The goal is behavioral discipline — preventing the user from starting new projects when they have too many open loops, ensuring adequate rest before building, and enforcing a 2-lane work limit.

**How it works:**
1. **Python pipeline** (cognitive-sensor) runs sentence-transformer embeddings on all conversations, detects open loops via topic scoring, computes closure ratios, and exports cognitive state as validated JSON.
2. **TypeScript state engine** (delta-kernel) ingests the cognitive state, computes the operational mode via a deterministic Markov lookup table (no AI), and serves a unified state API on port 3001. A governance daemon runs 6 cron jobs for heartbeat, refresh, mode recalculation, and work queue management.
3. **TypeScript policy gate** (aegis-fabric) intercepts AI agent actions, evaluates them against declarative policy rules (9 operators, 3 effects: ALLOW/DENY/REQUIRE_HUMAN), and enforces mode-appropriate behavior. For example, task creation is denied during CLOSURE mode.
4. **HTML dashboard** (atlas_boot.html) polls the unified state every 30 seconds and renders a 4-tab viewport with CycleBoard, control panel, cognitive atlas, and docs.

**Key architectural ideas:**
- **Append-only hash-chained deltas**: Every state mutation is an immutable record with cryptographic hash chain. Enables P2P sync and full audit trail.
- **Deterministic mode routing**: Mode is computed by pure lookup table from 5 signals. No AI, no heuristics, no drift.
- **Proposal-only architecture**: AI and preparation modules generate Draft/Proposal entities that require human confirmation. Nothing executes without the human gate.
- **Dual-language bridge**: Python handles NLP/analysis, TypeScript handles state/governance. JSON Schema contracts enforce the boundary.
- **LoRa-safe design**: The entire protocol is designed for 220-byte packet sizes, enabling future off-grid operation with solar-powered edge nodes.
- **Behavioral enforcement**: 2-lane work limit, idea moratorium, closure ratio enforcement, research time caps — all computed and enforced automatically.

**Scale:** 223 files, ~39,750 LOC, 3 services (ports 3001, 3002, 5173), 15 JSON Schema contracts, 19 specification documents, 8 Python analysis agents, 6 governance cron jobs, 45 entity types.

**Current state:** The core loop works (refresh → mode compute → display). Modules 1-5 (cockpit, preparation, dictionary, vector discovery, AI design) are functionally complete. Modules 6-11 (sync, off-grid, UI streaming, camera, actuation, audio) have type definitions and spec code but aren't wired into runtime. The system runs on Windows with PowerShell scripts.

---

*End of System Freeze Specification*
