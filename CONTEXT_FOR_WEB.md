# Pre Atlas — Context for Web Claude

> **Purpose:** cold-start orientation for an AI assistant with no prior repo
> knowledge. Read this first, then drill into the canonical docs named at the
> bottom. This packet reconciles the older docs (README, MACHINE_CONTEXT,
> CONTEXT_PACKET) against current code as of **2026-06-08**.
>
> **Scope note:** this packet is about the **Pre Atlas monorepo**. The
> operator also runs a separate local **agent search belt** (a 13-tool
> structural-code-search stack driven by the `repo-search` Claude Code skill) —
> see §8 and `docs/repo-search-stack.md`. That belt operates *on* this repo but
> doesn't ship with it.

---

## 1. What Pre Atlas is (elevator pitch)

Pre Atlas is a **solo-operator behavioral governance system** — a personal OS
that ingests life signals (sleep, open loops, assets shipped, deep work, money
delta), computes an operational **mode** via deterministic routing, and **gates
all work** (human *and* AI) through that mode. It prevents starting new work
while loops are open, building while sleep-deprived, and scaling before
compounding. Every state change is an immutable, hash-chained **delta** (event
sourcing). The original two-service core (`delta-kernel` + `cognitive-sensor`)
has grown into a ~15-service federated monorepo coordinated by a FastAPI
orchestrator.

---

## 2. Core concepts (the load-bearing ideas)

- **Delta-kernel / event sourcing.** Entities are never mutated in place. Every
  change is a **delta** = entity_id + RFC 6902 JSON Patch + `prev_hash` +
  `new_hash` + author + timestamp, appended to an immutable log. State is
  reconstructable from genesis; hash-chain mismatches reveal forks. Stored in
  SQLite WAL (`.delta-fabric/state.db`) since the 2026-03 migration off JSON
  (which had produced ~10 hash-chain forks). Designed for eventual P2P sync over
  LoRa (220-byte packets) — that part is spec/types only, not wired.

- **Mode routing (deterministic, no AI).** Six modes in strict progression:
  `RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE`. Computed by a
  Markov lookup table from 5 signals bucketed LOW/OK/HIGH. Two absolute
  overrides: `sleep < 6h → RECOVER`, `open_loops ≥ 4 → CLOSURE`. Closure-ratio
  thresholds gate transitions (≥0.8→SCALE, ≥0.6→BUILD, ≥0.4→MAINTENANCE,
  <0.4→CLOSURE). Unified 2026-03-11: `routing.ts` is the TS authority (all 6
  modes); `atlas_config.py:compute_mode()` is the Python authority (3 modes).

- **Cognitive pipeline.** A ~10-step Python analysis over 1,397 historical
  conversations (93,898 messages): loop detection → closure ratio → cognitive
  state export → daily mode routing → payload/projection → CycleBoard wiring →
  reporting/dashboards. Bridges to the kernel via `POST /api/ingest/cognitive`.
  A separate 5-agent **idea pipeline** (excavator → deduplicator → classifier →
  orchestrator → reporter) scores and sequences ideas.

- **Aegis governance.** A policy gate intercepting AI-agent actions. 9 operators
  (eq/neq/in/not_in/gt/lt/gte/lte/exists), 3 effects (ALLOW / DENY /
  REQUIRE_HUMAN), first-match-wins on priority-sorted rules, default ALLOW.
  REQUIRE_HUMAN queues for human review (1h TTL). Multi-tenant quotas. Keeps its
  own delta store in `.aegis-data/`.

- **Work admission control (Phase 6A).** The universal gate for *all* work.
  `POST /api/work/request` (ask), `POST /api/work/complete` (report),
  `GET /api/work/status` (query). Enforces mode gates (CLOSURE blocks AI by
  default), capacity bounds (1 concurrent, 5-job queue), and dependency
  tracking. A daemon advances the queue every minute; everything is logged.

- **Constitutional constraint.** The system *proposes, the human disposes*:
  engines emit Drafts/proposals; execution requires a PendingAction confirmation
  gate (30s timeout). Marked LOCKED in source.

---

## 3. Services & apps (status reconciled to current code)

Ports are the convention used by `docker-compose.yml` / `MOSAIC_README.md`.
"Working" = has runtime code + tests; "spec-only" = types/specs without runtime.

| Service | Stack | Port | Purpose | Status |
|---|---|---|---|---|
| **delta-kernel** | TS / Express / SQLite | 3001 | State engine, mode routing, governance daemon, work admission, REST + SSE, Atlas CLI | Working |
| **cognitive-sensor** | Python / SQLite | — | 10-step analysis pipeline; loops, closure, daily routing | Working |
| **aegis-fabric** | TS / Express / Postgres | 3002 | Policy gates for AI agent actions; approval queue; multi-tenant | Working |
| **mirofish** | Python / FastAPI / Neo4j | 3003 | Prediction / swarm simulation; graph reasoning | Working |
| **openclaw** | Python / FastAPI | 3004 | Multi-channel messaging utility (25 tests) | Working |
| **mosaic-orchestrator** | Python / FastAPI | 3005 | Coordination layer; runs cognitive-sensor; metering | Working |
| **inPACT** | HTML/JS (+ signal ingest) | 3006 | Personal methodology product (today/method/followup) | Working |
| **code-converter** | Python / FastAPI | 3007 | Python→C++ transpiler (AST + verifier) | Spec-ish |
| **uasc-executor** | Python / HTTP | 3008 | Deterministic command execution (7 cmds, HMAC) | Working |
| **cortex** | Python / FastAPI | 3009 | Autonomous exec (planner/executor/reviewer); Phase 0 dispatcher | Working (early) |
| **optogon** | Python / FastAPI | 3010 | Session-based dialogue paths; sitepull→ContextPackage adapter | Working |
| **ws-gateway** | TS / Node | 3011 | WebSocket relay; NATS | Working |
| **blueprint-generator** | Next.js | 3030 | Project blueprint generation | Working |
| **canvas-engine** | TS / Express / Vite | 3050 | URL → anatomy → live React clone; SSE edit loop | Working (6 phases) |
| **mosaic-dashboard** | Next.js / React | 3000 | Web UI (metering, workflows, state) | Working |
| **triangulation** | Python / FastAPI | custom | Multi-agent reasoning / consensus grid | Working |
| **perception** | Python | custom | Sensory data processing | In progress |
| **crucix** | submodule | — | Submodule; little/no code present | Unknown |

**Newer subsystems (post-March, not in MACHINE_CONTEXT.md):**
- **canvas-engine** (3050): URL→anatomy→React clone; vendors firecrawl/open-lovable; Zod twin schema (`src/adapter/v1-schema.ts`) locks round-trip with `AnatomyV1.v1.json`; in-process Vite pool (3060–3069). Replaced the old `claude -p` edit loop.
- **optogon** (3010): FastAPI dialogue paths; `sitepull` adapter turns `anatomy.json` → `ContextPackage` for pre-seeded sessions (Ship Target #3, 2026-04-27).
- **anatomy-extension** (`tools/anatomy-extension/`): Chrome extension producing `anatomy.json` (DOM region tree); the producer side of the canvas-engine contract.
- **signals-store** (in delta-kernel): preserves resolved signal state on re-ingest (fix 2026-04-27).
- **cortex** (3009): autonomous execution layer; Phase 0 dispatcher poll loop landed 2026-04-27.

---

## 4. Repo layout

```
pre-atlas/
  services/          # the ~15 federated services (table above)
  apps/              # standalone apps: blueprint-generator, webos-333,
                     #   canvas-demo, ai-exec-pipeline, c110-trace, inpact, ...
  contracts/         # JSON Schema (draft-07) data contracts + examples
  tools/             # dev tooling: anatomy-extension, anatomy-rewrite, codex-partner
  doctrine/          # planning/doctrine docs + fest staging fixtures
  research/, _research/   # research projects & test fixtures
  data/              # runtime artifacts (projections/today.json, consulting)
  anatomy/           # rendered anatomy dashboard output
  migrations/        # DB migrations
  scripts/           # launchers + discover.sh (local tool-belt probe)
  contracts/, docs/  # schemas and developer docs
  .delta-fabric/     # kernel state: state.db (WAL), dictionary.json (gitignored)
  docker-compose.yml # full-stack orchestration (Postgres, Redis, Neo4j, NATS, Ollama)
```

Plus a large set of top-level `*.md` / `*.json` briefings (see §7).

---

## 5. How to run it

```bash
# Full stack (Docker) — easiest
cp .env.example .env          # set ANTHROPIC_API_KEY etc.
docker compose up -d          # dashboard → http://localhost:3000

# delta-kernel (core engine + governance daemon)
cd services/delta-kernel && npm install && npm run api        # REST :3001 + SSE
npx tsx src/cli/index.ts                                       # human CLI
npx ts-node src/cli/atlas-ai.ts                                # agent-native JSON CLI

# cognitive-sensor (analysis pipeline)
cd services/cognitive-sensor && python refresh.py             # 10-step refresh

# canvas-engine (URL → React clone)
cd services/canvas-engine && npm run dev                      # :3050

# optogon (dialogue paths)
cd services/optogon && python -m optogon.main                 # :3010
```

**Key endpoints (delta-kernel):**
`GET/PUT /api/state` · `POST /api/ingest/cognitive` · `GET /api/governance/config`
· `GET/POST /api/tasks` · `POST /api/work/{request,complete}` · `GET /api/work/status`
· `GET /api/timeline` · `POST /api/law/close_loop`

**Port map:** 3000 dashboard · 3001 delta-kernel · 3002 aegis · 3003 mirofish ·
3004 openclaw · 3005 mosaic-orchestrator · 3006 inPACT · 3007 code-converter ·
3008 uasc-executor · 3009 cortex · 3010 optogon · 3011 ws-gateway · 3030
blueprint-generator · 3050 canvas-engine · 5432 Postgres · 6379 Redis ·
7474/7687 Neo4j · 4222/8222 NATS · 11434 Ollama.

---

## 6. Roadmap / phase state

**Shipped (Phases 1–6C, Jan 2026):** genesis cognitive-sensor → contracts &
cognitive→delta bridge → autonomy daemon (cron + SSE) → progressive enforcement
gates → **closure mechanics** (closures as first-class state transitions,
streaks, mode transitions, closure-amnesty resets violations) → **work
admission** (request/complete/status) → ambient gate UI → **timeline** event log.
Phase 5A (WebSocket push) deferred in favor of polling.

**Recent (Apr 2026):** canvas-engine (6 phases, 84 vitest tests) · optogon
sitepull adapter · signals-store re-ingest fix · PNG-substrate/c110-trace
telemetry · cortex Phase 0 dispatcher · inPACT signal ingestion.

**Next (potential):** Phase 6B work *preparation* (background prep workers) ·
Phase 7 federated/cross-device state replication.

---

## 7. Which docs to trust (canonical vs stale)

**Use these as primary sources:**
- `PHASE_ROADMAP.md` — most reliable feature-completion history (Phases 1–6C).
- `MOSAIC_README.md` + `docker-compose.yml` — current service/port topology.
- `services/canvas-engine/README.md` — freshest technical detail (2026-04-27).
- `ARCHITECTURE_BRIEFING.md` — deep mechanics (mode unification, closure
  mechanics); mostly current as of 2026-03-11.
- `contracts/schemas/` — the data contracts (e.g. `ModeContract.v1.json`,
  `AnatomyV1.v1.json`).

**Treat with caution (stale / partial):**
- `README.md` — header says "Atlas," lists fewer/older services; use as a nav index.
- `MACHINE_CONTEXT.md` (2026-03) — kernel internals are solid, but it only knows
  3 services; missing canvas-engine, optogon, cortex, triangulation, perception.
- `CONTEXT_PACKET.md` (2026-01-12) — pre-April; phase/service descriptions are dated.
- `ONBOARDING.md` (2026-01) — quickstart still works; lacks post-6C subsystems.

**Known conflicts to be aware of:**
- **inPACT (3006):** older docs call it a static methodology app; recent commits
  add dynamic signal ingestion.
- **CLOSURE thresholds:** cognitive-sensor uses `open_loops > 20` (Python
  heuristic); delta-kernel uses `open_loops ≥ 4` (TS strict). Both intentional.
- **`closures.json`** lives in the cognitive-sensor workspace, not `.delta-fabric/`.
- **crucix / uasc-executor** runtime status is unverified from docs alone.

---

## 8. The operator's agent search belt (how the code gets read)

Separate from the running system, the operator drives this repo through a
local **structural-code-search belt** — a Claude Code skill (`repo-search`)
over 13 CLI tools, plus a global file-locator. The rule is *understand the
codebase before editing it*. Full inventory + runnable examples:
**`docs/repo-search-stack.md`**. `repo-search` is one skill in a wider ~40-skill
Claude Code belt catalogued in **`AGENT_BELT.md`**.

- **Step 0 — `es`** (voidtools Everything CLI): locate the right project/file
  *anywhere on the machine* before any repo-local search. Cheatsheet:
  `~/.claude/rules/common/file-search.md`.
- **The 13-tool stack:** `rg` (text) · `fd` (files) · `bat` (read) · `eza`
  (tree/list) · `tree` · `delta` (diffs) · `jq` (JSON) · `yq` (YAML/TOML) ·
  `sg`/ast-grep (AST shape) · `semgrep` (static analysis) · `tree-sitter`
  (parse trees) · `tokei` (LOC stats) · `ctags` (symbol index).
- **Agent loop:** `eza --tree` → `fd` → `rg` → `sg` → `bat` → `ctags` → patch →
  tests → `git diff | delta`. `semgrep`/`tokei` are out-of-band (bug-class
  sweeps / sizing).
- **Playbook vs inventory:** `docs/repo-search-stack.md` is the *inventory*;
  the operational rules are the **"DropList Search Tightening Protocol"** in
  `docs/search-protocol.md` (the *playbook*: search-first/edit-last, the
  es→fd→rg→sg→semgrep→ctags→tests→diff escalation ladder, and a Windows
  substitutions table).
- **Verify the stack:** `bash tools/repo_search_check.sh`, or the portable
  `bash scripts/discover.sh` (checks all 13 tools + `es` and lists the Claude
  Code skills/commands).

**Naming correction (supersedes earlier guesses):** "DropList" is the *search
protocol*, not a task/job CLI; there is no DropList/Atlas/RAG-DAG/Lattice
"job system + SQLite spine." (`.droplist` does appear as proof-log/output
artifacts the protocol locates via `es`, but it is not a CLI or DB.) "Atlas"
elsewhere = this repo's delta-kernel system, unrelated.

> **Still local-only (referenced but not yet committed):**
> `~/.claude/rules/common/file-search.md` (the `es`/Everything DSL cheatsheet)
> and `tools/repo_search_check.sh` (the original stack verifier;
> `scripts/discover.sh` is a portable stand-in). Push or paste these to make
> them durable context too.

---

*Generated 2026-06-08, updated 2026-06-09 (added agent search belt, §8).
If something here disagrees with code, the code wins — and this file is stale.*
