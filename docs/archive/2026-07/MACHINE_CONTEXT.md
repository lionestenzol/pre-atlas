# Pre Atlas — Machine Context for AI Reasoning

Generated: 2026-03-10 | Updated: 2026-03-11 (stabilization: SQLite, unified routing, retries, schema versioning)
Target: DeepSeek or any reasoning model that cannot access the repository.

---

## What Pre Atlas Is

Pre Atlas is a solo-operator behavioral governance system. It enforces operational discipline by analyzing 1,397 historical conversations (93,898 messages), computing a behavioral mode, and gating all actions through that mode. The system prevents the operator from starting new work when existing loops are unclosed, from building when sleep-deprived, and from scaling before compounding.

## The Kernel Concept

The **delta-kernel** is a TypeScript/Express state engine on port 3001. Every mutation in the system is recorded as an immutable **delta** — an RFC 6902 JSON Patch with cryptographic hash chaining:

```
Delta N:   { patch: [...], prev_hash: "abc", new_hash: "def" }
Delta N+1: { patch: [...], prev_hash: "def", new_hash: "ghi" }
```

Entities are never mutated directly. The kernel maintains 45 entity types (system_state, task, thread, message, draft, pending_action, etc.), each with a version counter and current hash. The append-only delta log enables hash chain verification and is designed for eventual P2P sync over LoRa radio (220-byte packet limit).

The kernel's core invariant: **all execution requires a PendingAction confirmation gate with a 30-second timeout**. The preparation engine generates Draft entities, but drafts cannot execute without human confirmation. This is a constitutional constraint — the system proposes, the human disposes.

State is stored in SQLite (WAL mode) under `.delta-fabric/state.db` — migrated from JSON files to eliminate concurrent-write hash chain forks. The previous JSON storage (`entities.json`, `deltas.json`) had no locking, which produced 10 known hash chain forks. SQLite provides atomic writes, O(1) appends, and busy_timeout-based concurrency. A `dictionary.json` (3-tier compression dictionary) remains file-based.

## The Mode Routing System

The system enforces 6 operational modes in a strict progression:

```
RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE
```

Mode is computed by a **deterministic Markov lookup table** — not AI, not heuristics. Five signals are bucketed into LOW/OK/HIGH via hardcoded threshold functions:

- `sleep_hours`: <6→LOW, ≥7.5→HIGH
- `open_loops`: ≥4→LOW(bad), ≤1→HIGH(good)
- `assets_shipped`: 0→LOW, ≥2→HIGH
- `deep_work_blocks`: 0→LOW, ≥2→HIGH
- `money_delta`: ≤0→LOW, ≥target→HIGH

Two global overrides have absolute priority:
1. sleep < 6 hours → always RECOVER
2. open_loops ≥ 4 → always CLOSURE

Mode-specific transitions then apply: RECOVER exits when sleep improves, CLOSURE exits when loops close, BUILD exits when assets ship, COMPOUND exits when deep work + revenue align, SCALE exits when delegation completes.

A governance daemon runs 6 cron jobs: heartbeat (5min), cognitive refresh (1hr), day_start (6am), day_end (10pm), mode recalculation (15min), work queue (1min). The mode_recalc job reads cognitive state and applies closure_ratio thresholds: ≥0.8→SCALE, ≥0.6→BUILD, ≥0.4→MAINTENANCE, <0.4→CLOSURE.

Mode routing has been unified (2026-03-11 stabilization): `routing.ts` is the single TypeScript authority (lut.ts deleted), `atlas_config.py:compute_mode()` is the single Python authority, and the governance daemon delegates to `routing.ts` instead of using inline thresholds. Python handles 3 modes (CLOSURE/MAINTENANCE/BUILD); TypeScript handles all 6 via the full signal set.

## The Cognitive Pipeline

The **cognitive-sensor** is a Python analysis pipeline that processes conversation history through a 10-step sequential refresh:

1. **loops.py** — Score conversations for open loops using topic weights: `score = user_words + (intent × 30) - (done × -50)`. Threshold: score ≥ 18,000.
2. **completion_stats.py** — Compute closure ratio from loop_decisions table (CLOSE vs ARCHIVE).
3. **export_cognitive_state.py** — Export full cognitive snapshot (loops, drift, closure metrics).
4. **route_today.py** — Compute mode from cognitive state (ratio<15→CLOSURE, open>20→CLOSURE, open>10→MAINTENANCE, else→BUILD).
5. **export_daily_payload.py** — Generate daily directive payload (duplicates step 4's routing logic).
6. **wire_cycleboard.py** — Copy state files to dashboard brain directory.
7. **reporter.py** — Generate state history.
8-10. Build dashboard, strategic priorities, docs manifest.

An 8-agent **idea intelligence pipeline** runs separately: excavator (extract ideas from conversations using 18 regex patterns + semantic similarity with all-MiniLM-L6-v2, 384-dim embeddings) → deduplicator (Union-Find clustering at cosine similarity ≥ 0.70) → classifier (status, skills, alignment scoring against a psychological profile) → orchestrator (composite priority scoring: `freq*0.20 + recency*0.20 + alignment*0.25 + feasibility*0.15 + compounding*0.20`, with Kahn's topological sort for execution sequence) → reporter (markdown output).

The cognitive pipeline bridges to the TypeScript kernel via: `build_projection.py` (merge cognitive + directive into `today.json`) → POST to `http://localhost:3001/api/ingest/cognitive`. Payloads include `schema_version` and `mode_source` fields for cross-service negotiation. Communication is validated against 17 JSON Schema contracts (draft-07) stored in `contracts/schemas/`, including `ModeContract.v1.json` documenting the Python↔TypeScript mode routing split.

A governance layer runs daily and weekly: `governor_daily.py` computes lane health, violations, and leverage moves from a hardcoded config (`atlas_config.py`) that defines north star goals, 2-lane work limit, idea moratorium, research caps (30 min), and minimum build time (90 min). `governor_weekly.py` aggregates and produces autonomy proposals.

## The Governance Layer

**aegis-fabric** is a TypeScript/Express policy gate on port 3002. It intercepts AI agent actions and evaluates them against declarative rules:

- **Agent adapter**: Normalizes Claude (tool_use), OpenAI (function_call), and direct formats to a canonical action schema.
- **Policy engine**: 9 operators (eq, neq, in, not_in, gt, lt, gte, lte, exists), 3 effects (ALLOW, DENY, REQUIRE_HUMAN). First-match-wins evaluation on priority-sorted rules. Default: ALLOW.
- **Approval queue**: REQUIRE_HUMAN queues actions for human review (1-hour TTL, then auto-expire).
- **Multi-tenant**: FREE/STARTER/ENTERPRISE tiers with per-tenant quotas (max agents, actions/hour, entities).

The action processing pipeline: normalize → validate agent → fetch tenant → check quota → evaluate policy → execute/deny/queue → audit log → webhook dispatch.

aegis-fabric maintains its own delta engine and entity store (`.aegis-data/`), duplicated from delta-kernel with no shared package.

## The Event Sourcing Model

Pre Atlas implements event sourcing through hash-chained deltas:

1. Every state change is a **Delta**: entity_id + RFC 6902 JSON Patch + prev_hash + new_hash + author + timestamp.
2. The delta log is **append-only** — no updates, no deletes.
3. State can be **reconstructed** by replaying deltas from genesis.
4. Hash chain enables **fork detection** — if prev_hash doesn't match the entity's current_hash, a fork is detected.
5. A **Law Genesis Layer** (`ensurePathExists()`) auto-materializes parent path nodes before leaf patches, ensuring structural validity.
6. The 3-tier **Matryoshka Dictionary** compresses text into machine-addressable tokens (tier 1) → patterns (tier 2) → motifs (tier 3). Append-only with permanent promotion.
7. A **priority map** assigns sync priority to entity types: system_state syncs first (priority 1), discovery proposals sync last (priority 10).

The system is designed for eventual P2P operation: 3 node classes (CORE/EDGE/MICRO) with capability caps, LoRa-safe 220-byte packets, nonce-based sync handshake, and deterministic 3-way merge for conflicts. This infrastructure exists as type definitions and spec code but is not wired into runtime.

## Key Architectural Properties

1. **Deterministic routing** — No AI in the mode computation loop. Pure lookup tables.
2. **Proposal-only preparation** — Engines generate drafts/proposals, never execute.
3. **Human gate** — 30-second PendingAction timeout on all mutations.
4. **Append-only state** — Deltas never modified, hash chain integrity.
5. **Dual-language bridge** — Python (NLP/analysis) → JSON → TypeScript (state/governance). Validated by JSON Schema contracts.
6. **Behavioral enforcement** — 2-lane limit, idea moratorium, closure ratio gates, research caps.
7. **Constitutional constraints** — Marked as LOCKED in source (types.ts, templates.ts).

## Current System Scale

- 3 services: delta-kernel (port 3001), cognitive-sensor (Python), aegis-fabric (port 3002)
- ~223 files, ~39,750 lines of code
- 45 entity types (only ~10 used in runtime)
- 17 JSON Schema contracts
- 19 specification documents
- 6 cron jobs, 11-step refresh pipeline (with retry logic), 5-agent idea pipeline
- 10 HTML dashboards
- 1,397 analyzed conversations, 84K visualization points

The system is a working prototype. Modules 1-5 (cockpit, preparation, dictionary, vector discovery, AI design) are functionally wired. Modules 6-11 (sync, off-grid, UI streaming, camera, actuation, audio) exist as specifications and type definitions only.
