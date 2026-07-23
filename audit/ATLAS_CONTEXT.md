# Pre Atlas — Repository Context Primer (for LLMs)

> **Purpose of this file.** A compact, accurate map of the Pre Atlas monorepo for any LLM
> that needs to reason about it. Read this before answering questions or editing code.
> Source of truth: `audit/system-index.json` (generated 2026-06-20, 35 subsystems) +
> first-hand `code-recon` (file:line-verified, 2026-06-21/22). Synthesized 2026-06-22.

## 0. Prime directives for the assistant

1. **Do not confabulate connections.** This repo's wiring is NOT what the architecture
   diagrams imply. The intuitive sketch "delta-kernel → intake → droplist → cycleboard →
   inPACT → atlas" is **wrong** (see §4). Verify any "X calls Y / X depends on Y" claim
   against actual files before asserting it. Past subagents fabricated causal stories here.
2. **Absence claims need 2+ angles.** Before saying "nothing uses X", grep imports AND
   routes AND config, and say which angles you checked.
3. **Two repos exist.** `C:\Users\bruke\Pre Atlas` (with a space) is THIS repo (the 35
   subsystems). `C:\Users\bruke\pre-atlas` (hyphen) is a *different* repo holding
   `delta-scp` + Supabase substrate + duplicate copies. Don't conflate them.
4. **"Runs but doesn't act" is by design.** The automation loop is intact in code but
   dormant behind unscheduled cron + default-off env gates (see §4). Don't "fix" it by
   flipping gates without the user.

## 1. What the system is

Pre Atlas is a **personal behavioral governance system** — one machine for governing the
user's own behavior. At the center is **`delta-kernel`**, a deterministic TypeScript/Express
state engine (SQLite, port 3001) that runs life as a **6-mode finite state machine**:

```
RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE
```

Architecture = **hub-and-spoke around delta-kernel, one-way HTTP seams.** 35 subsystems,
but functionally **one loop**: sensors read conversations → a triage core sorts them into
decisions → an execution arm acts → surfaces display it — all routed through the hub.

- The `Mode` type lives in `services/delta-kernel/src/core/types-core.ts:50-56`.
  Any `Record<Mode, ...>` MUST cover all 6 modes.
- Mode transitions are a hand-rolled functional table in
  `services/delta-kernel/src/core/routing.ts:103-146` (no xstate). Deterministic, pure.

## 2. The shape — roles in the loop

Group the subsystems by **role**, not by folder. This is how the system actually works:

| Role | Members | What the role does |
|---|---|---|
| 🧭 **Hub** | delta-kernel | The deterministic core. Mode/state, signals store, viewmodels, governance daemon (9 cron jobs, */5 heartbeat). Everything routes through it. |
| 👂 **Sense** | cognitive-sensor, perception, triangulation, mirofish | Reads conversations/history/signals → structured cards & ideas. |
| ⚖️ **Sort** | optogon | Triage: proposes keep/close/archive verdicts. Write-back gated off. |
| 🤖 **Act** | cortex, droplist, uasc-executor | Turns decisions/drops into tool-verified actions. Gated + ARCHIVE-only. |
| 🪟 **Surface** | inpact, lattice, crucix, mosaic-dashboard, webos-333 | The faces: daily flow, projection views, boards. |
| 🛠️ **Build tools** | canvas-engine, code-converter, search-stack, blueprint-generator, canvas-demo | Generators: code, clones, research. |
| 🗺️ **Substrate/audit** | atlas-map-api, atlas-cli, atlas-audit, memory-hub | The map of itself: index, locate, drive the fleet. |
| 🛡️ **Gateway/infra** | aegis-fabric, ws-gateway | Auth gateway + real-time transport. |
| 🔬 **Anatomy R&D** | anatomy-research, anatomy-extension, anatomy-rewrite | Capturing UI structure (research line). |
| 🤝 **Dev tooling** | codex-partner, fest-reconcile, mini-ship, reminders | Delegation, reconciliation, ship telemetry. |
| 🗄️ **Legacy/paused** | mosaic-orchestrator, openclaw, ai-exec-pipeline | Retired/paused. Furniture, not in the live loop. |

## 3. Subsystem catalog (all 35)

Format: `name` (path) — role · lang/framework · port · LOC · **status** — description.
Status legend: **live** · **gated** (off by default) · **dormant** (unscheduled) ·
**legacy/retired** · **stub** (≈0 LOC).

### services/
- **delta-kernel** — hub · ts/express · :3001 · 35k LOC · **live (daemon active)** — the 6-mode state engine + API hub. Entry `src/api/server.ts`. Key: `/api/signals/ingest` (server.ts:1806), `/api/cycleboard`, `/api/lattice/viewmodel` (server.ts:2004), governance daemon `src/governance/governance_daemon.ts`.
- **cognitive-sensor** — sense · py/fastapi · 116k LOC (644 files) · **dormant automation** — conversation-analysis pipeline (HDBSCAN/UMAP/sentence-transformers), idea registry, thread cards (cycleboard content). Hosts `auto_triage.py` (the unscheduled triage arm) + `droplist_bridge.py` (new, uncommitted).
- **optogon** — sort · py/fastapi · 4k LOC · **gated** — proposes triage verdicts, seeds preferences. Writes back only when `AUTO_TRIAGE_APPLY=1`.
- **cortex** — act · py/fastapi · 4k LOC · **gated** — autonomous execution layer. Double-gated (`CORTEX_BRIDGE_APPLY` + `CORTEX_BRIDGE_RUN_PROPOSAL`), ARCHIVE-only.
- **droplist** — act · py/fastapi · :3073 · 8.6k LOC · **live (on-demand)** — capture→packet→DAG→tool-verified done engine. Own BIBLE/PACKETS/DOCTRINE. Key: `server.py:148` POST /api/drop, `intake.py:33`, `graph_engine.py:236` emits Signal.v1, `atlas_signal.py`. **Highest churn in repo (91).** User's farm data lives in `data/entities/*.json`.
- **uasc-executor** — act · py/raw-http · :3008 · 2.2k LOC · **live** — M2M command executor, HMAC auth, audit log.
- **aegis-fabric** — infra · ts/express · :3010 · 12k LOC · **live** — admin gateway + API middleware, tenant-key auth in front of kernel ingest. Security perimeter.
- **ws-gateway** — infra · ts · :3006 · 122 LOC · minimal — WebSocket gateway (NATS + socket.io).
- **canvas-engine** — build · ts/express · :3060 · 7k LOC · **live** — URL→React clone via in-process Vite pool. Uses Anthropic SDK.
- **search-stack** — build · py/fastapi · 3.4k LOC · **live** — router over 28 search providers / 14 intents. Also a port :3070 service + MCP.
- **atlas-map-api** — substrate · py/fastapi · :3072 · 2k LOC · **live** — GPS substrate. `GET /items` (unified item feed, 373 items), `/map` (start/stop/restart services), locate/path/neighbors. POST guarded by `X-Atlas-Token`.
- **memory-hub** — substrate · py/fastapi · :3071 · 558 LOC — memory aggregation.
- **crucix** — surface · html/express · 2k LOC — standalone "jarvis" dashboard, outside the fleet.
- **perception** — sense · py · 832 LOC · **stub** — Phase A sensor scaffold.
- **triangulation** — sense · py/fastapi · :3010(!) · 1.3k LOC · **stub** — Phase B. NOTE port :3010 collides with aegis-fabric.
- **mirofish** — sense · py/fastapi · 2.9k LOC · **retired** — Neo4j prediction engine, pending merge into cognitive-sensor.
- **mosaic-orchestrator** — legacy · py/fastapi · 7.5k LOC · **retired** (still autostarted) — Mosaic platform orchestrator (58% built, paused).
- **mosaic-dashboard** — surface · ts/next · :3000 · 2.1k LOC · **retired** (still autostarted) — Mosaic Next.js dashboard.
- **openclaw** — legacy · py/fastapi · 918 LOC · **retired** (still autostarted).

### apps/
- **inpact** — surface · js · 11k LOC · **live** — THE chosen human face: daily flow, onboarding, cycleboard, projects. State in `projects.json` (42). Cycleboard syncs kernel `/api/cycleboard`.
- **lattice** — surface · js · 12.5k LOC · **live** — projection view (tree/graph via Cytoscape/timeline). Consumes the 373-item backbone, writes status back. Replicache client of the kernel. `index.html` is hand-maintained (NOT generated).
- **code-converter** — build · py/fastapi · :3007 · 1.3k LOC · **live** — Python→C++ AST converter (30 patterns).
- **blueprint-generator** — build · js/next · 998 LOC · **retired** (still autostarted).
- **ai-exec-pipeline** — legacy · py/flask · 455 LOC · **retired** — superseded by cortex.
- **canvas-demo** — build · ts/react · 254 LOC — Remotion comparison sandbox.
- **webos-333** — surface · html · 3.4k LOC — experimental single-file web OS.

### tools/
- **atlas-cli** — substrate · py · 627 LOC · **live** — `atlas where|locate|neighbors|path|search|list|show|status|open`.
- **anatomy-extension** — anatomy · js · 5.3k LOC — Chrome MV3 UI-anatomy capture.
- **anatomy-research** — anatomy · mixed · :8080 · **571,924 LOC** (2,967 files, mostly vendored) — Anatomy R&D vault. Dwarfs the rest of the repo; exclude from "real LOC".
- **fest-reconcile** — devtool · py · 3.2k LOC — Festival manifest reconciler.
- **codex-partner** — devtool · py · 211 LOC — OpenAI Codex delegation.
- **atlas-audit** — substrate · 0 LOC · **stub** — audit pipeline / index generator (audit.sh).
- **anatomy-rewrite** — anatomy · 0 LOC · **stub**.
- **mini-ship** — devtool · 0 LOC · **stub** — ship-loop telemetry (skill lives in ~/.claude).
- **reminders** — devtool · 0 LOC · **stub/empty**.

## 4. The spine — VERIFIED relationships (read this carefully)

First-hand `code-recon`, file:line-cited. Tags: ✅ live (proven e2e) · 🟡 dormant ·
🟣 gap-closed (built, off) · ❌ busted (does not exist).

✅ **droplist → delta-kernel → lattice** (the real "to lattice" path):
droplist `graph_engine.py:236` → POST `/api/signals/ingest` → kernel signals-store →
`lattice-projection.ts:204` → `apps/lattice` viewmodel. Live-proven e2e (commit `7640010`).
NOTE: viewmodel response is `{ok, viewmodel:{items,...}}` — items are NESTED.

✅ **intake chainer**: droplist `server.py:148` POST /api/drop → `intake.py:33 chain_intake`
→ `engine.process_drop` → settles secured packet. Tested.

✅ **inPACT ↔ cycleboard ↔ kernel**: shared state via kernel `/api/cycleboard`
(`inpact/cli/inpact.ts:96`). **Cycle Board is a VIEW, not an engine** — localStorage SPA,
zero droplist refs, zero realtime.

✅ **item backbone**: atlas-map-api `GET /items` (`items.py`) read-aggregates droplist DAGs +
cycleboard `thread_cards.json` + inPACT `projects.json` → one shape `{id,source,kind,title,
status,updated,ref}`. 373 items live. lattice consumes it; write-through (`POST /items/{id}/
status`) flips **droplist-only** status (others 422). Last unbuilt brick: shared identity
across surfaces (currently 4 records seen separately, not 1 record seen 4 ways).

🟣 **auto-triage → droplist**: was the ONE real gap. Built `cognitive-sensor/droplist_bridge.py`
+ Rung 4 in `auto_triage.py` (6/6 tests). **Dormant** until `DROPLIST_DROP_URL` set. Uncommitted.

🟡 **the act-loop** (intake→sort→route→close): Python arm `auto_triage → cortex_bridge →
Cortex → decisions_to_atlas` is intact in code but **UNSCHEDULED** (hand-cranked via `at`),
behind 3 stacked default-off gates (`AUTO_TRIAGE_APPLY` → `CORTEX_BRIDGE_APPLY` →
`CORTEX_BRIDGE_RUN_PROPOSAL`). The every-5-min popup is a SEPARATE engine: the TS
`governance_daemon.ts` preparation job (`PREPARATION_CRON */5`), NOT the Python arm.

❌ **CORRECTIONS to the intuitive sketch:**
- "delta-kernel → droplist intake" is **reversed**: droplist emits TO the kernel. Nothing
  external calls droplist's /api/drop except its own server + tests.
- "droplist → cycleboard" has **no direct wire** — they meet only at the atlas-map `/items`
  read layer.
- The **"4-part stateless pipeline on a Supabase Realtime bus" does not exist.** No event bus,
  no interception (writes are one-way), Cycle Board doesn't consume Drop List. Supabase is NOT
  in this repo — only in the hyphen repo's `delta-scp`.

**To activate the full loop** (user decision, reversible): set `DROPLIST_DROP_URL` +
`DROPLIST_ATLAS_SIGNALS_URL`; flip `AUTO_TRIAGE_APPLY` in DRY-RUN first; enable Cortex execute
(ARCHIVE-only) last, watched.

## 5. Dependency edges (import/call graph, 19 edges; `src → dst` = src depends on dst)

```
lattice→delta-kernel    inpact→delta-kernel     droplist→delta-kernel
cortex→delta-kernel      optogon→delta-kernel    optogon→cortex
canvas-engine→delta-kernel  ws-gateway→delta-kernel  uasc-executor→delta-kernel
aegis-fabric→delta-kernel   cognitive-sensor→delta-kernel  inpact→cortex
droplist→search-stack    lattice→cognitive-sensor   code-converter→canvas-engine
crucix→canvas-engine     mosaic-orchestrator→optogon   mosaic-dashboard→mosaic-orchestrator
perception→triangulation
```
- **delta-kernel has 10 inbound deps** (the blast radius). canvas-engine & cortex: 2 each.
- **Orphans in the import graph** (read-time HTTP or standalone, NOT broken): atlas-map-api,
  atlas-cli, memory-hub, anatomy-*, atlas-audit, canvas-demo, codex-partner, fest-reconcile,
  webos-333, mini-ship, reminders.

## 6. Where state lives

- `governance_state.json` — mode / risk / north_star / lanes (HUB state, NOT items).
- delta-kernel SQLite — signals store, cycleboard, viewmodels.
- droplist `data/dags/*.json` + `data/entities/*.json` — packets + farm data.
- cognitive-sensor `thread_cards.json` (326) — cycleboard cards.
- inPACT `apps/inpact/projects.json` (42).
- "today" surface — browser localStorage (no file).
- `contracts/schemas/` — ~49 JSON Schema (draft-07) data contracts.

## 7. Bound ports

3000 mosaic-dashboard · 3001 delta-kernel (hub) · 3006 ws-gateway · 3007 code-converter ·
3008 uasc-executor · 3010 aegis-fabric **+ triangulation (collision)** · 3060 canvas-engine ·
3070 search-stack · 3071 memory-hub · 3072 atlas-map-api · 3073 droplist · 8080 anatomy-research.

## 8. Conventions & gotchas (Windows / this repo)

- Platform is **Windows**; shell is **PowerShell** (Bash also available). Paths with spaces
  ("Pre Atlas") need quoting. PowerShell `$_` mangles when passed inline via Bash — write a
  `.ps1` file instead.
- Edit tool requires the file be Read in the current context first.
- delta-kernel `tsc --noEmit` was clean as of 2026-06-15.
- Don't treat **retired/stub** subsystems as live targets. 4 retired services are still in
  autostart (blueprint-generator, mosaic-dashboard, mosaic-orchestrator, openclaw) — boot
  cost, no live consumer.
- Current branch: `experiment/droplist-remediation-2026-06-15`.

## 9. Health flags (from the index)

- **Retired (6):** ai-exec-pipeline, blueprint-generator, mirofish, mosaic-dashboard,
  mosaic-orchestrator, openclaw.
- **Stale / no recent commits (11):** anatomy-extension, anatomy-research, anatomy-rewrite,
  canvas-demo, code-converter, codex-partner, cortex, crucix, optogon, perception, triangulation.
- **Missing tests (7):** code-converter, inpact, lattice, anatomy-extension, anatomy-rewrite,
  codex-partner, fest-reconcile.
- **Anomalies:** :3010 port collision (aegis-fabric vs triangulation); 4 zero-LOC stubs;
  anatomy-research vendored mass (571k LOC).

## 10. How to navigate / regenerate

- **Human view:** `audit/atlas-whitepaper.html` (interactive white paper — open in a browser).
- **The index** behind both: `audit/system-index.json` (+ `audit/system-map-data.js`).
- **Regenerate:** run `audit/imports/_build_map.py`, then `atlas_reload` the atlas-map MCP.
- **Live GPS queries:** `atlas where|locate|neighbors|path|search` (tools/atlas-cli) or the
  atlas-map MCP. For deep code skeletons, the `delta-scp` skill compresses a repo into a
  symbolic file+symbol map.

---
*This primer is hand-authored synthesis over the index. After major structural changes,
regenerate the index and refresh §3–§7. Spine facts (§4) are point-in-time first-hand recon —
re-verify file:line before relying on them for edits.*
