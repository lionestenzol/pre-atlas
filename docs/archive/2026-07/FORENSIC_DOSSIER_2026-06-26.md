# Pre Atlas · Forensic Dossier

> Written to you, Bruke, on 2026-06-26 · so you can see yourself and this code, and read your own patterns and trajectory.
> Every load-bearing claim below is grounded in a date, a commit hash, a `file:line`, or a number from the forensic mining. Where the inputs say "unknown", this says so rather than inventing.

---

## 1 · The shape in one page

Pre Atlas is a personal behavioral-governance system that grew into a federated TS + Python monorepo. The founding idea is narrow and clear: a deterministic personal state machine to break the `start > jump > switch > stall > stop` cycle. What you actually built over five months is roughly 20 services and 29-35 named subsystems, plus 8 spun-out repos.

It lives as a load-bearing two-repo split, both born from one genesis commit (`b013729`, 2026-01-12, "Initial commit: Pre Atlas behavioral governance system"):

- **A · `C:/Users/bruke/Pre Atlas`** (space) is the live working clone. 426 commits, 254 of them unique to A. It sits 126 commits ahead on `feat/atlas-setup-ui` with effectively nothing merged back to `main`.
- **B · `C:/Users/bruke/pre-atlas`** (hyphen) is the delta-scp home. 178 commits, only 6 unique to B, all authored by you, all scoped `delta-scp` (the v2 graph-memory work: prune + flue + AST graph, Supabase-free demo gateway, idempotent sync).

The two clones share 172 commits off the common root. The combined deduplicated universe is **432 unique commits over 44 active days** (2026-01-12 to 2026-06-25).

### Headline numbers

| Metric | Value |
|---|---|
| Combined unique commits | 432 (A 426 / B 178 / shared 172) |
| Frontier | `feat/atlas-setup-ui`, ~126 ahead of `main`, ~nothing merged |
| Tracked source files (excl. crucix submodule) | 929 (`.py/.ts/.tsx/.js`) |
| Markdown files | 389 (markdown is the #2 "language" by volume) |
| Active span | 2026-01-12 to 2026-06-25 · 44 active days |
| Author split | Bruke 339 · Claude (`noreply@anthropic.com`) 65 · lionestenzol 28 |
| feat : fix : test | 197 : 46 : 3 |
| Largest hand-authored file | `services/delta-kernel/src/api/server.ts` = 3157 lines |
| Hardcoded secret literals | 1 (`executor-bridge.ts:14`) · cloud-key literals 0 |

Authorship is effectively two people. `lionestenzol` (`96748360+lionestenzol@users.noreply.github.com`) is your GitHub-web identity: 21 of its 28 commits are "Merge pull request #N from lionestenzol/claude/..." GitHub-UI merges. So raw human:Claude is ~339:65, but Claude's true contribution is undercounted because most human-committed work here is Claude-assisted (you describe yourself as the architect/director, not the typist).

---

## 2 · Timeline and eras

Six legible eras. Each row: the dates, what was born, and what it reveals about how you work.

### Genesis · 2026-01-12 (`b013729`)
The whole system starts in one commit: a TS/Express deterministic state engine (delta-kernel), cognitive-sensor, the contracts layer, and the early WebOS/atlas_boot UI all present at genesis. Same-day adds mode-transition timestamps and realtime unified state streaming (`acac44a`). Commit messages are bare capitalized imperatives ("Track mode transition timestamps", "Fix daemon repoRoot path calculation"). 0% conventional-commit format. 12 commits this day.
**Reveals:** you ship a working deterministic core first, with judgment still implicit in code. The contract layer is present from the start, which is the earliest sign of the contract-first instinct that later becomes law.

### Deploy · 2026-02 (36 commits)
The Claude-identity era: 24 Claude + 12 lionestenzol commits, and **zero Bruke direct commits** all month. Entirely PR-merge driven ("Merge pull request #5-#10 from claude/analyze-breaches branches"). The three Feb-9 Vercel deploy commits (`15927a0`, `565edd6`, `8b5518e`) make `atlas_boot.html` the real combined ATLAS CORE dashboard with the WebOS simulator embedded behind "Enter Desktop". Burst days 2026-02-09 (24, 10 merges) and 2026-02-08 (12, all merges).
**Reveals:** the first time you treated the system as something agents extend through PRs. Still ad-hoc message style. Multi-author convergence but no discipline yet.

### Mosaic · 2026-03-26 (`3286586`, festival tag MP0001)
The conventional-commit turn lands here (March = 30% conventional, the transition month) and you take over direct committing (20 Bruke, 0 Claude in March). The entire "Mosaic Platform" (MiroFish swarm, OpenClaw gateway, dashboard scaffold + 5 panels, full Docker/installer) lands in a one-burst festival day: 10 of 14 mosaic-cluster commits on this single day. aegis-fabric is also born two days earlier (2026-03-24, `2afe289`, "Close-to-ship: wire governance pipeline").
**Reveals:** big-bang build mode, and the first time work is tracked by project task IDs. Typed commits and bundled tests become legible in the log.

### Big Bang · 2026-04-14 (`4c45676`) and the April inflection
April is the single biggest month: **160 commits**, and conventional-commit discipline snaps on hard, from 30% (March) to 95% (April) and holds. `4c45676` ("full system state sync") lands cortex + the crucix submodule, aegis integration, and the three apps (inpact, blueprint-generator, code-converter) in one commit. The all-time burst day is **2026-04-27 with 81 commits** (optogon 10, cognitive-sensor 7, canvas-engine 7), about 19% of the entire combined history in one day. Optogon is born 2026-04-19 (`9a7b299`), canvas-engine 2026-04-26 (`dd82a10`).
**Reveals:** your execution mode is high-amplitude detonation, not metronome. The conventional-commit regime change is a clean dated behavioral shift, not a gradient.

### Diverge · 2026-04-18 onward · the doctrine codification
On 2026-04-18 (`bf5417d`) the founding conversation is frozen into the 5-doc doctrine stack: `01_SEED > 02_ROSETTA_STONE > 03_OPTOGON_SPEC > 04_BUILD_PLAN > 05_FEST_PLAN`. Days later (2026-04-27, `410330c`) you commission an adversarial external audit of your own work (`doctrine/AUDIT_REPORT.md`). Then specialized services keep diverging out: shardstate + png-substrate (2026-04-30), search-stack + memory-hub (2026-06-08), droplist (2026-06-07), atlas-map (2026-06-20), lattice (2026-06-20).
**Reveals:** you locate value in transferable judgment and write the philosophy down so it survives any single implementation. Doctrine outranks code by your own rule: "If the doctrine says something different, the doctrine wins" (`04_BUILD_PLAN.md`).

### Mass sweep · 2026-06-25 (43 commits, the final day)
The documented mass-commit sweep that banked all uncommitted work onto `feat/atlas-setup-ui` (droplist 12, lattice 8, atlas-map-api 4). The 2nd-biggest day after the April burst. Droplist lifecycle bricks 1-4, lattice Week 3 (reject TinyBase), HIGH security fix on the atlas-map write-token handout (`8f0a32c`), and the festival methodology framework finally entering git (`f1a05f4`) all land.
**Reveals:** work is "done" in the working tree long before it is committed; the methodology predates its own tracking. June ran 137 commits at 94.2% conventional.

---

## 3 · System-by-system forensic

Every system from the mining, with born date, commit count, status, and a one-line purpose, followed by an evolution-and-idiosyncrasy paragraph each.

| System | Born | Commits | Status | Purpose |
|---|---|---|---|---|
| delta-kernel | 2026-01-12 | 36 | active | Deterministic delta-driven state engine, 6-mode FSM, Atlas hub (:3001) |
| cognitive-sensor | 2026-01-12 | 40 | maintained | Closed-loop behavioral governor over ChatGPT history, 6-layer pipeline |
| optogon | 2026-04-19 | 16 | maintained | Path-runtime FSM dialogue engine, node-graph closes (:3010) |
| cortex + crucix | 2026-04-14 | 8 | maintained | cortex = autonomous execution loop (:3009); crucix = vendored OSINT submodule |
| aegis-fabric | 2026-03-24 | 7 | dormant | Policy-gated agent execution: ALLOW/DENY/REQUIRE_HUMAN (:3002) |
| ws-gateway + uasc-executor | 2026-04-06 | 7 | maintained | NATS->Socket.IO bridge (:3011) + deterministic command "hands" (:3008) |
| mosaic cluster | 2026-03-26 | 14 | dormant | Docker-federated platform: orchestrator/mirofish/openclaw/dashboard |
| atlas-map | 2026-06-20 | 18 | active | "GPS for code": locate/path/search + call gateway (:3072) |
| droplist | 2026-06-07 | 33 | active | Capture-to-execution packet engine, lifecycle spine |
| lattice | 2026-06-20 | 26 | active | Cytoscape projection UI over Atlas work items |
| canvas-engine | 2026-04-26 | 10 | maintained | URL/screenshot -> live editable React clone (:3050) |
| inpact + blueprint-generator + code-converter | 2026-04-14 | 16 | active (mixed) | Three app surfaces: bullet-journal, scope planner, Py->C++ |
| minidocs + png-substrate + shardstate + hydra | 2026-04-30+ | 25 | dormant | Four independent research/substrate experiments |
| search-stack + memory-hub | 2026-06-08 | 7 | maintained | Unified search router (:3070) + memory router (:3071) |
| delta-scp | 2026-06-13 | 14 | active | Repo URL -> compact symbolic JSON map (:3012) |
| contracts layer | 2026-01-12 | 13 | maintained | 50-57 JSON Schemas (draft-07), producer/consumer contracts |
| doctrine + festival | 2026-04-14 | 6 | dormant | Prose governance corpus + step-based festival methodology |
| webos-333 + ATLAS CORE | 2026-01-12 | 9 | dormant | WebOS simulator + the Feb-2026 Vercel dashboard surface |

### delta-kernel
The founding core, package name `delta-state-fabric`. Born at genesis (`b013729`) and still active: last real edit `51c52cc` (2026-06-25) banked WIP db-driver / sqlite storage / api-tests. Its arc runs from a deterministic engine (mode-transition timestamps day one, SSE/WebSocket state by 2026-02-09) to the Atlas hub (`/api/atlas/cockpit` wiring `5b96bf0`, PKT-008 lattice viewmodel `b40a36b`, AtlasArtifact.v1 schema `b7e02c8`, all 2026-06-14/15). Idiosyncrasies: determinism is hand-rolled by design (custom delta + SHA-256 hash-chain in `core/delta.ts`, hand-coded 6-mode union FSM in `types-core.ts:50-56`) because integration depth is the product. It carries a 19-file `_deferred/` graveyard (actuation, camera/audio adapters, off-grid-node) kept in-tree per code-as-furniture. Tests exist but as hand-rolled tsx runners (`src/tests/*-tests.ts`), invisible to the standard `.test.ts` glob, so tooling reports 0 coverage when it is substantial. The pluggable DB driver (`db-driver.ts:29`) lazy-requires libsql only under `DELTA_DB_DRIVER=libsql` and fails loud with an install hint. This file also holds the one genuine hardcoded secret (see Section 4).

### cognitive-sensor
The "Cognitive Operating System": ingests ~93.8k messages / ~1.4k conversations into a SQLite store, then runs a 6-layer pipeline (MEMORY -> INTELLIGENCE -> NERVOUS SYSTEM -> LAW GENERATION -> INTERFACE GOVERNANCE -> DECISION TRACKING). Born at genesis, last touch 2026-06-25 (`fac10fd`, a multi-service refresh chore); last substantive feature was the Rung-4 triage->droplist bridge 2026-06-21 (`c0c45be`). It is the most sprawl-prone surface: ~155 `.py` files plus ~30 capitalized profile/report `.md` artifacts at the root (output documents committed alongside code), many tiny single-purpose scripts. Assemble-first is visibly applied and annotated (commits `2e6ef4a`/`6328dc1` on 2026-05-29 swapped a hand-rolled chunker for langchain-text-splitters and BaseHTTPRequestHandler for FastAPI; `droplist_bridge.py` cites the rule files by path). Dead code is quarantined in a 15-file `_archive/` not deleted. Note: the "49 JSON Schemas in contracts/schemas" claim does NOT live here (0 schema files; 25 plain `.json` data files) — that contract dir is a sibling component.

### optogon
Python/FastAPI path-runtime FSM dialogue engine on :3010, self-described as "brain stem". Born 2026-04-19 (`9a7b299`, "Phase 2"), "PATH COMPLETE" same day (`d5b82cf`), last fix 2026-06-25 (`9f922f5`, propagate session close to state field + SQLite column, with an 84-line regression test). Its evolution is tight and disciplined: each node type and path landed with its own test (18 test files / 100 test functions for ~4k lines of source, a ~1:1 ratio that is the best in the inventory). Idiosyncrasies: the FSM is hand-rolled (`process_turn` + `_transition` in `node_processor.py:42-87`) against the assemble-first doctrine, justified by tight doctrine/spec coupling (handlers reference `03_OPTOGON_SPEC.md §14` by name). There is real drift between code and data: `paths/*.json` fixtures declare node types (retrieval, side_effect, tool_call, transform) the runtime never dispatches; `fork` raises `NotImplementedError`. The "belt-and-suspenders" close logic in `main.py:276-282` is the visible scar of the `closed_at` bug that `9f922f5` fixed.

### cortex + crucix
Two unrelated things bundled by directory. **cortex** (:3009, Python/FastAPI) is the autonomous execution brain: `loop.py` runs a hand-rolled FSM (poll -> Aegis gate -> plan -> budget -> execute -> review -> verdict accept/retry/rollback/escalate) and plays the "Ghost Executor" role per doctrine Decision D6. Born 2026-04-14 (`4c45676`), last cortex feature 2026-05-02 (`0ec5d67`, RUN_PATH -> Optogon wiring). Its resilience is hand-rolled (a bespoke `CircuitBreaker` in `recovery.py:23`, no tenacity/pybreaker), and the Aegis gate "fails open" on error (`loop.py:219`) — a deliberate but security-relevant footgun. **crucix** is a true vendored git submodule (gitlink `160000 7a5015e`), NOT internal glue: its own 114-commit upstream repo (calesthio, born 2026-03-12, crucix.live, AGPLv3, 27 OSINT sources). Because no `.gitmodules` is tracked at root, a bulk `git add -A` would corrupt it — which matches the standing repo rule. Its pinned SHA sits one commit behind its own HEAD (`a419727`, 2026-06-24).

### aegis-fabric
Policy-gated execution fabric (:3002), born 2026-03-24 (`2afe289`) with almost the whole system in one large initial commit. Now dormant; last touch 2026-06-24 (`6c6585d`) was only an `atlas.surface.json` descriptor. The policy engine is a hand-rolled JSON rule evaluator (ALLOW/DENY/REQUIRE_HUMAN, 9 operators, `packages/shared/src/policy-engine.ts:87-229`). Its defining idiosyncrasy is DUAL CODE TREES: a flat live `src/` (the actual `start` entrypoint) AND an unwired `packages/` monorepo with Postgres migrations, docker-compose, and a 12.6MB committed `redis.zip` — strongly suggesting the Postgres+Redis design was started then abandoned for the file-based build. Two of its seven commits (`3aa8093`, `6680440`, 2026-05-29) are pure assemble-first swaps (pino, lru-cache), yet the core policy evaluator stayed hand-rolled. The only bugfix (`a03f6b5`) removed a default admin-key fallback and made the server refuse to boot without `AEGIS_ADMIN_KEY` — a deliberate security posture.

### ws-gateway + uasc-executor
Two halves of the real-time + execution spine, born together 2026-04-06 (`70d75d8`, "Phase 1"). **ws-gateway** (`index.ts`, 122 lines, :3011) is a thin NATS->Socket.IO bridge over 5 governance topics, with NO tests and NO persistence. **uasc-executor** (:3008) is the deterministic "hands": delta-kernel signs an HMAC-SHA256 request and POSTs a command token (@WORK, @BUILD, @DEPLOY...) and the executor runs a versioned JSON profile. SPEC.md states it explicitly: "not a language, not an AI agent... It does not decide what to do." The asymmetric maturity from a shared birth is the tell: one stayed a wire, the other grew a body (server + daemon + executor + auth + 184-line pytest suite + 9 versioned profiles). The FastAPI refactor (`335c745`, 2026-05-30) cites "Atlas Law #2 (Assemble First)" in the commit and deliberately preserved the public contract down to a legacy lowercase "404 Not found".

### mosaic cluster
"Mosaic Platform", a Docker-federated 6-service platform behind one orchestrator (:3005), born 2026-03-26 (`3286586`) in a single MP0001 festival day: ~71% of its commits (10/14) landed that day. Now formally SUPERSEDED by cognitive-sensor (3 of 4 READMEs carry `load_bearing_now: false`, tracked in `audit/lava-layers.json`) yet kept installed. Polyglot federation: TS/Next.js dashboard + Python/FastAPI orchestrator/mirofish/openclaw, glued by a root docker-compose with 5 heavy infra containers (postgres + redis + neo4j + nats + ollama) — heavyweight for a personal tool. Well-tested for a dead system (33 of 172 files are tests), but JSON fixtures (~11.8k lines) outweigh actual TS source (~1.1k). openclaw is the one service with no README and hand-rolls its own channel abstraction. A textbook code-as-furniture carcass left on the floor.

### atlas-map
"GPS for code" over the system map, born 2026-06-20 (`e0dea1c`), the youngest and one of the most active. It began strictly read-only and evolved fast into the control + capability plane: a self-describing registry (`/describe`, 35 surfaces), a layer-3 `/call` gateway (registry-as-ACL), item-backbone read/write-through, and process start/stop. Three consumers compose on it (the `atlas` CLI, an MCP server, a setup UI). Idiosyncrasies: assemble-first mostly honored (FastAPI, rapidfuzz, fastmcp, psutil, httpx) with a deliberately hand-rolled BFS graph (`graph.py:59`) where a library would be tax. The README is now stale doctrine drift — it still asserts "reads only, never writes" (`README.md:13`) while `gateway.py`/`auth.py`/`items.py`/`launcher.py` add token-guarded writes, file mutation, and OS process spawn. Security was fixed inline not documented: `auth.py:20-22` cites `code-as-furniture.md` by path when fixing the HIGH open-root-token finding (`8f0a32c`, 2026-06-25). Strong test discipline for a 5-day-old system: 141 test functions.

### droplist
Capture-to-execution packet engine, born 2026-06-07 (`e754015`), the most-iterated surface in the system (31 commits with the `droplist` scope, top of the scope chart). It grew through 4 MVPs into a persistent operating layer, then on 2026-06-25 added the lifecycle spine (mark-off, headless daemon tick, cron, daisy-chain) plus litellm-swappable LLM, PWA, and a native desktop window (`21c0d44`). Strong test discipline: 19 standalone `test_*.py` (~4,098 LOC, ~63% of package size). Safety-by-construction is the throughline: the engine never auto-acts (`completion.py:22-23` `_GLOBAL_BLOCKED`), tools are sandboxed, and "no node done without evidence". Assemble-first is baked into source comments (`llm.py:31` cites litellm; `desktop.py` cites pywebview+PyInstaller "not a hand-rolled Electron-style shell"). Heavy doctrine artifacts for one service: 11 numbered `PACKETS/*.md` plus BIBLE/DOCTRINE/SMOKE_AND_DOD.

### lattice
Projection-first single-file browser UI over Atlas work items, born 2026-06-20 (`5c2701b`). This is the canonical assemble-first win, made literal in code: hand-rolled SVG node-link rendering was replaced with vendored Cytoscape, and the 3-week plan composed Replicache + Zod + dagre/cose-bilkent rather than hand-rolling sync, validation, and layout (`index.html:9-22` carries an explicit "Week 2 (assemble-first)" comment). The discipline cuts both ways: Week 3 (2026-06-25, `0df6d01`/`b3bbbd7`) REJECTED TinyBase after 28-agent verified recon because the load-bearing depth-N BFS "TinyQL can't express anyway", so the hand-rolled BFS was deliberately kept. Two giant single-file HTML apps (`index.html` 2,724 lines, `system-map.html` 3,271) deliberately NOT React (a documented non-goal). One hermetic Playwright smoke (`smoke.spec.mjs`, 108 lines) guards exactly the Week-3 regressions. Known dead CSS left in place and deferred to a spawned cleanup task rather than rushed.

### canvas-engine
TS/Express service (:3050) turning a URL or screenshot into a live editable React clone in an in-process Vite sandbox pool (:3060-3069), born 2026-04-26 (`dd82a10`, Phases 1-6 in one commit). Last substantive code 2026-05-25 (`a522859`, image-vision pipeline); since then only surface/chore touches. Assemble-first done right: it vendors firecrawl/open-lovable at a pinned SHA (`VENDOR_SHA.ts`) with an explicit "do NOT modify in place, re-vendor instead" protocol. Strong self-evaluation: 15 test/fixture files, a self-grading trainer reporting group-level accuracy with an explicitly-labeled non-truth heuristic. Two-way contract coupling is load-bearing and fragile: the Zod twin (`v1-schema.ts`) uses `.passthrough()` in lockstep with `AnatomyV1.v1.json`; adding a field to one side silently drops data. One machine-specific footgun: `server.ts:20` defaults `WEB_AUDIT_ROOT` to `C:/Users/bruke/web-audit`.

### inpact + blueprint-generator + code-converter
Three unrelated app surfaces bundled only by a shared 2026-04-14 inception commit and the `apps/` directory, with divergent fates. **inPACT** (vanilla HTML/JS, no build, ~6700 LOC, localStorage + delta-kernel sync) is active and got an in-app AI assistant on 2026-06-25. **code-converter** ("Code to Numeric Logic", :3007, Py->C++ AST translator with runtime parity verification) is live-dormant. **blueprint-generator** (deterministic no-AI scope planner) self-documents its own death: `README.md:1-5` carries a "SUPERSEDED by canvas-engine, load_bearing_now: false" banner and its `atlas.surface.json` headline reads "do not build on this surface". Zero tracked test files across all three despite the 80% rule — a sharp contrast with the deterministic engines, and a tombstone left in place rather than deleted.

### minidocs + png-substrate + shardstate + hydra
Four independent experiments at different lifecycle stages and locations, not one system. Only **hydra** (`apps/hydra/`, GitHub-crawling snake game, born + last-touched 2026-06-25) and the **png-substrate** SEED doc (a 135-line `.md`, not code, 2026-04-30) live in HEAD. **minidocs** (OCR-free document shape recognizer) and **shardstate** (Merkle-addressed content-addressed graph store) exist ONLY on unmerged `claude/*` worktree branches — dead-ended experiment branches. The honesty signal here is strong: both research branches end on negative/self-correcting findings ("PRECISION-DEGRADES-AT-SCALE" for minidocs; "replace fabricated benchmark with honest not-yet-measured" for shardstate). Anti-hype discipline baked into the commit log. png-substrate explicitly discards the AGI framing the source transcript drifted into: "a demo family, not a computing paradigm".

### search-stack + memory-hub
Two paired retrieval-infra services. **search-stack** (:3070) is a unified search router: one REST + one MCP that classifies a query by intent across 14 kinds and dispatches to 32 provider singletons, each a thin vendor wrapper with a "missing key -> DISABLED, never raises" contract (`base.py:45-52`). **memory-hub** (:3071) routes (not warehouses) over Pre Atlas memory stores. Born 2026-06-08 (`fd4ed57`) and 2026-06-09. The pattern here is big-bang-then-idle: Phases 1+3+4+5 all shipped in one 2026-06-08 commit (`e06599d`), then core logic froze ~2 weeks; the only later touches are a rename and descriptor JSON. Doc drift is live: memory-hub README says "three memory stores" but enumerates four; search-stack README still says "19 providers" while `registry.py` ships 32. The mirofish Neo4j store is a documented dead-on-arrival stub returning `[]` until wired.

### delta-scp
Async compression service ("Symbolic Compression Protocol") turning a repo URL into a compact symbolic JSON map, born 2026-06-13 (`f510f2e`) in the hyphen repo, on :3012. Hardened the same day (reaper, auth, URL guardrails, CodeRabbit round-2 fixes). The v2 graph-memory upgrade (state-aware prune + flue + AST graph) landed 2026-06-21 (`8dfee18`, 999 insertions); the Supabase-free demo gateway 2026-06-25 (`87e4679`). Symbol extraction is hand-rolled by intent: a per-language regex table (`compressor.ts:97-131`) chosen over a real parser for determinism and breadth, with the gap named in-code (`graph.ts:8-12` "FIDELITY SEAM" deferring richer edges to a future tree-sitter pass). Deterministic-purity discipline: `compressTree` injects `generatedAt` so identical input yields identical output; `prune.ts`/`flue.ts` are "pure, no I/O, no clock". This is the 6-unique-commits home of the federated split.

### contracts layer
The contract-first spine: JSON Schema (draft-07) definitions of every cross-service payload, at repo-root `contracts/`. Born at genesis (`b013729`), last substantive non-merge touch 2026-06-17 (`a1eb24b`, DropList `source_layer=droplist`). The architecture mining counts 57 schemas (100% draft-07, 55 version-suffixed); the contracts mining counts 50. Either way the layer is disciplined. Two idiosyncrasies bite: (1) two parallel validators with split scope — `contracts/validate.py` hard-codes a 10-item Optogon allowlist and validates only those, deferring the other 40 to `cognitive-sensor/validate.py`, so most schemas have no example-pair CI gate; (2) only 12 of 50 ship an example payload, and Aegis schemas are physically duplicated in two trees (drift risk). Schemas are doctrine-coupled (cite `Spec §6/§7/§8`, `Bible §17`), so contract and prose can drift independently.

### doctrine + festival
Two coupled methodology layers, both prose/markdown not running code. `doctrine/` is the founding governance corpus (01_SEED through 05_FEST_PLAN), frozen at 2026-04-27 (4 April-only commits). The festival framework (`festivals/.festival/`) only entered git on 2026-06-25 in one mass-commit (`f1a05f4`) — the methodology predates its own tracking. Governing principle: "The user experiences a conversation. The system executes a close." 100 of ~116 files are markdown; no source, no real tests. A WSL workaround is baked in as permanent furniture: `05_FEST_PLAN.md` documents WSL "fully unresponsive" so 50 task bodies were authored offline with a materializer script still listed as pending. The `fest` CLI is Go (`build_fest.sh`) built for /root, now stale relative to the native `fest.exe` the runtime moved to.

### webos-333 + ATLAS CORE
Two coupled things under the "original product" banner. **webos-333** (`web-os-simulator.html`, 3,442 lines) is a single-file browser "operating system" toy with no Atlas data wiring. **ATLAS CORE** (`atlas_boot.html` + `public/index.html`) is the real Feb-2026 Vercel dashboard fetching delta-kernel at `localhost:3001`. Born at genesis, last touch 2026-06-24 (incidental `atlas.surface.json`). It self-declares dead furniture: `atlas.surface.json` says verbatim "Stub (kind=ui)... do not build on this." Notable rot: two copies of the 3,442-line simulator (`apps/webos-333/` and `public/apps/webos-333/`) have silently diverged (`diff` reports DIFFERENT). And a `localhost:3001` API base is hardcoded in a file deployed to Vercel, so the cloud surface is effectively a static shell unless the engine runs on the viewer's machine.

---

## 4 · Engineering patterns and idiosyncrasies (hard numbers)

### Work rhythm
- **Monday-dominated.** Monday holds 174 of 432 combined commits (40%). The rest: Thu 66, Sun 57, Sat 42, Tue 35, Wed 31, Fri 28. The cadence is one big Monday push, a Thursday/weekend secondary, midweek quiet.
- **2pm is your hour.** 14:00 = 65 commits, nearly double the next bands (09:00=39, 11:00=34, 15:00=28, 12:00=23). By block: afternoon (12-16) 143, morning (05-11) 123, night (21-04) 95, evening (17-20) 71. Real late-night work exists (03:00=19, 00:00=16, 02:00=15) but the productive center of mass is early afternoon.

### Burst profile
- Spiky, not steady. 19 days have >=8 commits and account for most of the 432.
- Top days: 2026-04-27 (81, ~19% of all history), 2026-06-25 (43), 2026-06-20 (25), 2026-02-09 (24), 2026-05-01 (16), 2026-03-26 (16), 2026-05-27 (14), 2026-06-15 (13).
- Bursts cluster on service spin-ups and ship/merge days.

### Commit hygiene
- Hard regime change, not a gradient: Jan 0%, Feb 0%, Mar 30%, then April snaps to 95% conventional and holds (May 87.7%, June 94.2%). Early era (Jan-Mar) 8.6%, recent era (Apr-Jun) 93.4%.
- Type mix: feat 197, docs 48, fix 46, chore 26, refactor 11, experiment 8, merge 4, test 3, audit 1, non-conventional 88. **feat:fix = 4.3:1** — build-forward, low-bugfix-ratio, greenfield-spinning rather than maintenance.
- Style: terse subject, rich body. Subjects average 8.51 words (max 14, min 3); full bodies average ~103 words (max 455). Short scannable headlines backed by substantial explanatory bodies — a mature recent-era style. The "reject TinyBase" commit literally banks a negative architectural decision in the log.
- Punctuation discipline is correctly scoped: 90 subjects use em-dashes (commits are not UI, so the no-em-dash law does not fire), while the approved set mirrors UI doctrine (middot · 31, arrow -> /→ 30, ↔ 4, § 4). Exactly one true emoji ever (✓ in one docs commit).

### Code maturity
- 929 tracked source files (excl. crucix). Above-average maturity for a personal/federated system, but uneven.
- **Strong:** contract layer (57 schemas, 100% draft-07); delta-kernel typing (string-literal unions over enums, `unknown` for untrusted JSON-patch values at `types-core.ts:92`, exhaustive `Record<Mode,...>` FSM tables at 8 sites, 53 immutable spread-update sites across 15 files); clean idiomatic Python (`atomic_write.py` forces UTF-8 at `:23` against the cp1252 gotcha, atomic temp-file + `os.replace()`).
- **Secret hygiene strong, one real finding:** 0 `sk-`/`AKIA`/`ghp_` tokens anywhere; of 43 generic matches nearly all are env reads or type hints. Exactly ONE genuine hardcoded literal: `services/delta-kernel/src/core/executor-bridge.ts:14` `const UASC_SECRET = 'delta-kernel-local-secret'`, a fixed HMAC signing key with no env fallback (used live at `:158`). Local-only, so HIGH not CRITICAL — but it should move to an env var. Note `:12` already reads `UASC_URL` from `process.env`, so the inconsistency is right there in adjacent lines.

### The big-file and test-naming debts
- **32 of 929 files (~3.4%) break your own 800-line max.** Worst hand-authored: `delta-kernel/src/api/server.ts` 3157, `audit/imports/_build_map.py` 3878, `apps/inpact/js/functions.js` 2988, `tools/anatomy-extension/content.js` 2700, `cognitive-sensor/cycleboard/js/functions.js` 2657, `delta-kernel cli/atlas-ai.ts` 1582 and `atlas.ts` 1557. Some are vendored (the `layout-base.js` 4333 x2 is Cytoscape) and effectively exempt; `server.ts` and the atlas CLIs are genuine extraction candidates.
- **Test discipline is real but uneven, with a naming trap.** 96 Python `test_*.py`, 18 TS `.test.ts`, 0 `.spec.*`. But the deterministic CORE (delta-kernel) shows 0 under the glob because its substantial suite uses a non-standard `-tests.ts` convention invisible to tooling. Two services have ZERO tests of any naming: the crucix submodule and ws-gateway.
- **The ledger-level tell:** 192 feat commits to 2 test commits (~96:1). Your own rules mandate TDD and 80% coverage; the behavior is feature-first. delta-kernel and optogon (96 pytest, ~1:1) are the exceptions that prove how rare it is elsewhere.

---

## 5 · Methodology evolution

Your methodology moved along one consistent vector: from "code is the product" to "judgment is the product, code is furniture, verification is the gate." Four dated phases.

**Genesis instinct (Jan-Apr) · contract-first.** The build sequence is always ground truth before logic. `04_BUILD_PLAN.md` Phase 1 is "10 JSON Schemas that every layer validates against... Nothing else runs yet." You think in interfaces and boundaries first, implementation second — the same instinct that later becomes the TGT Law (fix the folder before the UI) and the database+agent-pair shape.

**Codification (2026-04-18, `bf5417d`) · doctrine over code.** The 5-doc stack asserts judgment outranks code: `01_SEED.md` Part 6 "The code is not the moat... The doctrine is"; `03_OPTOGON_SPEC.md` "The code is implementable by an engineer. The doctrine is not. Both are required"; `04_BUILD_PLAN.md` closes "If the doctrine says something different, the doctrine wins." You build backwards from a real-world model (the sales-floor closer) rather than forward from technology.

**Adversarial self-audit (2026-04-27, `410330c`).** Days after shipping Optogon you bundled your own doctrine + code and had a different model audit it with BLOCKING/DEVIATION tags, accepting findings like "pacing is advisory, not enforced... the most important gap." This is the seed of the later anti-confabulation cluster — but still trusting; the distrust came after agents burned you.

**Organizational law (May-Jun).** Two tastes hardened into checkable gates. The **TGT Law** (codified 2026-05-28, committed `fd802e4` 2026-06-07): every artifact must pass Tree + Graph + Time before any UI "makeup" — "apps are folders + makeup; the hard part is the folder." The **no-em-dash UI ban**, precisely scoped (banned in product UI, allowed in commits/docs/chat). You convert repeated friction into permanent rules rather than re-deciding each time.

**Anti-confabulation discipline (Jun) · the hard-won cluster.** A dense set of rules converging on distrust of confident-but-unverified output, including your own:
- **Assemble-first** (2026-05-29): after catching a hand-rolled SVG graph ("isnt there graph software"), name the library before any hand-roll, "no false symmetry". Rigorously applied it can mean REJECTING the library (TinyBase, `0df6d01`/`b3bbbd7`, 2026-06-25).
- **Plans and reports are hypotheses** (2026-06): a 26-day-old lattice plan was wrong on 3 of 6 swaps because Week 1 silently invalidated Week 3's premise. "File/line citations are usually accurate; the causal story attached often isn't" (the `cockpit.ts:472` "three consumers" that had zero callers).
- **Deterministic tools over LLM improvisation** (2026-06-16/21): "never use agents for code recon again. code-recon is so much better." Agents should orchestrate Pre Atlas tools, not duplicate them, and surface a token budget before spawning (after ~535K tokens burned on PKT-006).
- **Solo when locked, swarm only for discovery** (2026-06-16): locked spec + loaded context = build solo with structured self-critique; multi-agent is for genuine uncertainty, not theater.
- **Target shape = one DB + one agent** (2026-04-29 and later): when tool-building competes with the work, default to paper; Atlas-software must name one thing paper-with-memory can't do before it grows.

The throughline: a builder progressively defending against his own builder-instinct — that tool-building becomes a substitute for work, that generation masquerades as progress, that plausible narratives get acted on without proof. The commit log fossilizes the same arc: bare sentences (Jan) -> conventional + task-ID `(MP0001)` (Mar) -> scoped + rule/severity tags `(HIGH security)` (Jun).

---

## 6 · The constellation

Pre Atlas is a monorepo-as-factory: the parent foundry spins things OUT. Three spin-out modes plus one outlier.

| Repo | Born | Commits | Mode | Lineage note |
|---|---|---|---|---|
| Pre Atlas (space) | 2026-01-12 | 426 | origin/foundry | the live working clone everything orbits |
| pre-atlas (hyphen) | 2026-01-12 | 178 | origin/foundry | delta-scp home, same genesis commit |
| atlas | 2026-04-29 | 20 (last 05-10) | distilled-from | "initial atlas substrate distilled from pre-atlas" |
| anatomy-saas | 2026-06-25 | 1 | product-spinoff | the /anatomy-map skill productized, sequence 01 |
| groundwork-cli | UNKNOWN | UNKNOWN (0 committed) | sibling-tool | git-init'd, zero commits, all files untracked |
| operator-system | 2026-05-05 | 11 (last 05-06) | sibling-tool | claude.ai <-> CC handoff scaffolding |
| POLARIS | 2026-02-22 | 6 (last 03-09) | product-spinoff | earliest spinoff, agent guardrails layer |
| competitor-monitor | 2026-05-04 | 1 | sibling-tool | weekly competitive intel, $0 marginal |
| mcp-servers/competitor-monitor | 2026-05-03 | 1 | sibling-tool (MCP twin) | the MCP half, born one day earlier |
| binre | 2026-06-25 | 4 | sibling-tool | RE pipeline (DIE/Ghidra/x64dbg/Frida) |
| bearings | 2026-06-25 | 2 | sibling-tool | deterministic where-am-I digest |
| everything-claude-code | 2026-01-17 | 1099 (last 03-31) | meta-track / OUTLIER | third-party (affaan-m), NOT Pre-Atlas lineage |

The distillation is explicit: `atlas`'s first commit reads "feat: initial atlas substrate distilled from pre-atlas" — a deliberate compression of the heavy federated services into a single-folder, no-Docker core. Three tools were born in a single 2026-06-25 burst (anatomy-saas, binre, bearings), extracting capabilities the monorepo had been incubating. Two data-quality flags worth naming: groundwork-cli is a real, built tool with ZERO commits (working tree all untracked), so its dates are genuinely unknown; and everything-claude-code's 1099 commits dwarf all Atlas-native repos combined but are vendored reference, not yours.

---

## 7 · Personal trajectory and blind spots

Bruke, here is the candid read.

### What you are unusually good at
- **Architecture and framing.** You think in interfaces, contracts, and boundaries before implementation, and you write the philosophy down so it outlives any one build. The contract layer present at genesis, the 5-doc doctrine stack, the TGT Law — these are the work of someone who designs the seams first. That is rare and it is your real moat.
- **Velocity that isn't capped by typing.** Because you delegate every keystroke to Claude and direct rather than type, your throughput is uncapped: 432 commits over 44 days, an 81-commit day, consecutive phased ships. You carry enormous parallel context (50+ tracked projects) in your head.
- **A sound stack heuristic.** Python for intelligence, TS for orchestration, vanilla HTML for owned UI. You assemble libraries correctly in domains you know (FastAPI, FAISS, hdbscan, Cytoscape) and you hold the hand-roll when integration depth IS the product (delta-kernel determinism).
- **A genuine methodological immune system.** Verification is the one loop you reliably close. The verify-distrust cluster (agent-report distrust, verify-at-HEAD, code-recon-not-agents, ground-claims-in-source) is hard-won discipline most builders never develop. The TinyBase rejection and the "honest not-yet-measured" benchmark commit show intellectual honesty baked into the log.

### The debt, in one shape
You build far faster than you close, and you sweep almost never. The ledger is the tell, and it is consistent across every metric:
- **Test-as-afterthought.** 192 feat to 2 test commits (~96:1), despite your own TDD/80% rule. The deterministic engines are the only places it holds.
- **Doc-vs-ship inversion.** 389 markdown files, markdown the #2 language. The "why" is exhaustively recorded while the "what" frequently stalls before merge. MEMORY.md is itself over budget.
- **Merge debt.** `feat/atlas-setup-ui` sits ~126 ahead of `main` with ~nothing merged back. Main is a fossil; the real state lives in scattered feature branches plus `claude/*` worktrees that may never converge.
- **Abandoned services kept warm.** ~27% subsystem mortality in 4 months (mirofish, openclaw, mosaic-orchestrator, blueprint-generator, mosaic-dashboard, ai-exec-pipeline retired). They keep autostart slots, memory entries, and config drift. The factory keeps the carcasses on the floor — your code-as-furniture rule, taken too literally, becomes a hoarding rule.
- **The recognition blind spot, not a competence one.** You hand-roll in domains you don't register as solved: the delta-kernel Mode FSM (no xstate), optogon's FSM, inPACT step-toggling. FSM, multi-step forms, date math, fuzzy search slip through because they don't trip the "solved category" alarm. Your assemble-first doctrine exists precisely to catch this; it fires inconsistently.
- **The builder-trap you already named.** Your own `tools-must-beat-paper` rule diagnoses it: the tool meant to remove friction becomes the friction. The relief valve isn't more building — it is the act of auditing itself, which is what this dossier is.

### Three blind spots to watch
1. **Merge/branch debt compounds silently.** Work that's "done" in a branch but never integrated is indistinguishable from work that was never done, six months later.
2. **Retired-but-resident services and stale READMEs (atlas-map "reads only", search-stack "19 providers", memory-hub "three stores") quietly lie to future-you and to any agent reading them as ground truth.**
3. **Solved-category recognition is the one place your doctrine doesn't reliably fire — FSMs and forms keep getting hand-rolled.**

---

## 8 · Appendix · raw stats tables

### A · Commits and authorship
| Metric | Value |
|---|---|
| Combined unique commits | 432 |
| Clone A "Pre Atlas" | 426 (254 unique) |
| Clone B "pre-atlas" | 178 (6 unique) |
| Shared | 172 (common root b0137297) |
| Active days | 44 (2026-01-12 to 2026-06-25) |
| Bruke | 339 |
| Claude (noreply@anthropic.com) | 65 |
| lionestenzol (GitHub web identity) | 28 (21 PR merges) |
| Merge commits | 42 (37 subjects start "Merge") |

### B · Cadence
| Dimension | Distribution |
|---|---|
| Day of week | Mon 174, Thu 66, Sun 57, Sat 42, Tue 35, Wed 31, Fri 28 |
| Hour peak | 14:00=65, 09:00=39, 11:00=34, 15:00=28, 12:00=23 |
| Time blocks | afternoon(12-16) 143, morning(05-11) 123, night(21-04) 95, evening(17-20) 71 |
| Subject words | avg 8.51, max 14, min 3 |
| Body words | avg ~102.9, max 455 |

### C · Commit types
| Type | Count |
|---|---|
| feat | 197 |
| docs | 48 |
| fix | 46 |
| chore | 26 |
| refactor | 11 |
| experiment | 8 |
| merge | 4 |
| test | 3 |
| audit | 1 |
| non-conventional | 88 |

### D · Conventional adherence by month
| Month | Conventional % | Commits |
|---|---|---|
| Jan | 0% | 12 |
| Feb | 0% | 36 |
| Mar | 30% | 20 |
| Apr | 95% | 160 |
| May | 87.7% | 65 |
| Jun | 94.2% | 137 |

### E · Top scopes
droplist 31 · cognitive-sensor 25 · optogon 20 · delta-scp 14 · shardstate 13 · canvas-engine 13 · lattice 12 · minidocs 8 · atlas-map-api 8 · atlas-map 8 · delta-kernel 7 · anatomy-extension 7 · optogon-stack 6 · map 6 · inpact 6 · contracts 6 · audit 6 · aegis-fabric 6

### F · Code maturity
| Metric | Value |
|---|---|
| Tracked source files (excl. crucix) | 929 |
| Files over 800-line rule | 32 (~3.4%) |
| Largest hand-authored | server.ts 3157 |
| JSON Schemas | 57 (architecture mining) / 50 (contracts mining), 100% draft-07 |
| Python tests | 96 test_*.py |
| TS tests | 18 .test.ts |
| Services with zero tests | crucix (submodule), ws-gateway |
| Hardcoded secret literals | 1 (executor-bridge.ts:14) |
| Cloud-key literals | 0 |
| Record<Mode,...> FSM sites | 8 |
| Immutable-update sites | 53 across 15 files |

### G · Non-ASCII in commit subjects
em-dash — 90 · middot · 31 · arrow → 20 / -> 11 · ↔ 4 · § 4 · ✓ 1 · en-dash – 0 · true emoji subjects 1

### H · Burst days (>=8 commits, top 12)
2026-04-27 (81) · 2026-06-25 (43) · 2026-06-20 (25) · 2026-02-09 (24) · 2026-05-01 (16) · 2026-03-26 (16) · 2026-05-27 (14) · 2026-06-15 (13) · 2026-04-26 (12) · 2026-04-20 (12) · 2026-02-08 (12) · 2026-01-12 (12)

---

*Forensic dossier compiled 2026-06-26 from deterministic git mining of both clones, per-system code-recon, methodology trace, constellation scan, architecture characterization, and fingerprint synthesis. Claims are grounded in commit hashes, file:line citations, and counts; "unknown" is stated where the evidence was absent.*
