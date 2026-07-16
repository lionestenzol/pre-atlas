# DECISIONS.md -- Pre Atlas Architectural Decision Record

Provider-neutral extract of load-bearing decisions from project memory.
Each entry records what was chosen, why, what was rejected, and current status.

---

## Architecture

### ADR-001: Pre Atlas maps to four established architectural models

**DECISION:** Pre Atlas maps onto MAPE-K (Kephart & Chess 2003), BDI (Rao & Georgeff 1995), Subsumption (Brooks 1986), and Homeostatic regulation. Monitor = cognitive-sensor, Analyze = scoring/fest, Plan = directive.ts, Execute = Cortex, Knowledge = state.json. Optogon paths serve as the reflex (subsumption) layer; delta-kernel serves as the deliberative layer.

**RATIONALE:** Grounds the system in proven autonomic-computing and agent-architecture theory rather than ad-hoc design. Provides a shared vocabulary for reasoning about component roles.

**DATE:** 2026-06-28.
**STATUS:** Active.

---

### ADR-002: Atlas pivot from behavioral governance to execution substrate

**DECISION:** Atlas is no longer a behavioral governance layer that regulates Bruke's execution capacity. It is now an execution substrate -- infrastructure that runs work via agent fleets.

**RATIONALE:** More work is agent-executed than human-executed. A governance layer shaped to protect a fragile human's capacity is wrong once the actor is an agent fleet. Same components, different job: mode ladder becomes system health/throughput gate; aegis-fabric policy becomes standard safety/approval layer. Rejected alternative: adding agent orchestration on top of behavioral governance (doubles the abstraction without changing the fundamental shape).

**DATE:** 2026-07-04.
**STATUS:** Active. Executing via master plan (ADR-006).

---

### ADR-003: One engine (delta-kernel), three operations

**DECISION:** Atlas, ATM, and UASC are one engine (delta-kernel: deterministic, event-sourced, signed append-only deltas) under three operations. Atlas = Identity (engine pointed inward at one life, BUILT). ATM = Ancestry (engine scaled outward, scoped to one node; city layer unbuilt). UASC = Composition (uasc-executor :3008 bolts on as hands via executor-bridge.ts and HMAC).

**RATIONALE:** Analysis of all three systems' shipped artifacts showed a shared unit shape and a 5-element signature where exactly one element (self-expansion) is always stripped. Rejected alternative: treating them as three separate projects with independent engines.

**DATE:** 2026-06-28.
**STATUS:** Active. ATM's transport/learning layer has zero code.

---

### ADR-004: Trust boundary rule -- capability changes only by source-diff + redeploy

**DECISION:** The action-type list can only be changed by a source diff and redeploy, never by a runtime request, proposal, or payload. Compile-time and runtime are different trust domains; capability changes may only cross from the compile-time side.

**RATIONALE:** Any runtime path where the system can register a new capability from AI output becomes exactly what sophisticated prompt injection targets. ActionType is a closed literal union in types-core.ts, enforced at execution time.

**DATE:** 2026-07-06.
**STATUS:** Active.

---

### ADR-005: REQUIRE_HUMAN gate is permanent by design

**DECISION:** The human-in-loop approval gate for high-risk/high-blast-radius actions (aegis-fabric's REQUIRE_HUMAN) stays permanently. It is a design choice, not a training-wheels phase.

**RATIONALE:** Atlas should execute autonomously as infrastructure, but for high-risk actions specifically, Bruke wants to remain a partner in the loop. Rejected alternative: treating REQUIRE_HUMAN as a maturity phase to be automated away.

**DATE:** 2026-07-04.
**STATUS:** Active.

---

### ADR-006: Convergence thesis -- machine substrate IS the human prosthetic

**DECISION:** The machine execution substrate and the human prosthetic are not two things -- agents execute, human shrinks to three touchpoints (morning push, one-tap decision, REQUIRE_HUMAN approval). Six-phase plan: UNLOCK -> RITUAL -> LIGHTS_ON -> SUBSTRATE -> TRIAGE -> COMPOUND. Steering metric = human-minutes per shipped item.

**RATIONALE:** Once Atlas is the execution substrate (ADR-002), the behavioral-governance features naturally serve as the human's three touchpoints. Building them as separate concerns would duplicate effort. Phase 001 (UNLOCK) completed 2026-07-07.

**DATE:** 2026-07-07.
**STATUS:** Active. Phase 001 DONE; phases 002 (RITUAL) and 003 (LIGHTS_ON) next.

---

### ADR-007: Self-describing surfaces with role-based ACL

**DECISION:** Three levels: L1 = per-surface atlas.surface.json self-description, L2 = registry aggregating all 35 surfaces (158 capabilities), L3 = gateway (POST /call) with visibility-as-ACL. Five roles: anon, agent-ro, agent, operator, root. Write-scoped tokens, MCP integration at POST /call.

**RATIONALE:** Needed a single discovery and invocation path across 35 heterogeneous surfaces. Hardened after 4-lens adversarial review (14 findings fixed including path-param traversal).

**DATE:** 2026-06-20.
**STATUS:** Active.

---

### ADR-008: Three-layer read surface -- HTTP API + CLI + MCP over same snapshot

**DECISION:** Atlas GPS substrate exposes the system map through three consumer layers: HTTP API (FastAPI :3072), CLI (typer), MCP server (FastMCP 3.x, direct-imports). All three read the same files (audit/system-index.json + atlas-map.json). Each has its own in-process cache.

**RATIONALE:** Different consumers need different access patterns: AI needs MCP tools, humans need CLI from any cwd, dashboards need HTTP. Sharing the same snapshot data ensures consistency.

**DATE:** 2026-06-20.
**STATUS:** Active.

---

### ADR-009: Atlas/inPACT role split

**DECISION:** Atlas = manager view. today.html inPACT = worker/client view. Execution flow: worker -> manager (today.html feeds Atlas state, not reverse).

**RATIONALE:** Separates the concerns of governance/oversight (Atlas) from daily execution/work (inPACT).

**DATE:** 2026-04-21.
**STATUS:** Active.

---

### ADR-010: Headless Atlas -- UI is visualization, not capability

**DECISION:** Atlas spine is already headless. The spine is: cognitive-sensor (analyze) -> optogon/cortex (propose/execute) -> droplist (packetize) -> delta-kernel (commit) -> lattice/inpact (project = THE UI). Only the last step is UI. Steps 1-4 are backend.

**RATIONALE:** Partition analysis showed every surface is a thin client over delta-kernel/spoke APIs. Control surface already exists via atlas-cli, delta-kernel CLIs, MCP atlas-map, /call gateway, and tools/seam/run.py.

**DATE:** 2026-06-29.
**STATUS:** Active. Three load-bearing verifies pending before cut.

---

### ADR-011: LangGraph as the missing executor under the Thompson bandit

**DECISION:** LangGraph is the durable execution layer. Skills become graph nodes, seam.v1 Receipts become graph state. combo.py's Thompson bandit plugs IN as the conditional-edge router. delta-kernel's work queue is the external supervisor. SqliteSaver with durability="sync". LANGGRAPH_STRICT_MSGPACK=true from day one.

**RATIONALE:** The stack has a learned policy over skills with NO durable executor. seam fans out but does not chain. Receipts are printed and thrown away. Zero orchestration libraries anywhere in the stack. Two critical design constraints: (1) the bandit must be a node, not an edge (LangGraph replays on resume -- a Thompson draw in an edge re-draws differently); (2) every skill/CLI call goes in @task (resume restarts the interrupted node from its beginning).

**DATE:** 2026-07-14 (plan locked); 2026-07-15 (Seq 1 shipped).
**STATUS:** Active. Seq 1 (Receipt store) DONE; Seq 2-7 not built.

---

## Data

### ADR-012: libSQL as delta-kernel database spine

**DECISION:** libSQL (Turso's production better-sqlite3-compatible synchronous fork) is the delta-kernel DB spine, accessed behind a DELTA_DB_DRIVER flag. Default = better-sqlite3 (no behavior change). DELTA_DB_DRIVER=libsql routes through libSQL.

**RATIONALE:** (1) delta-kernel's storage layer uses only the synchronous better-sqlite3 core API, so libSQL is a near-drop-in. (2) libSQL ships production native vectors + embedded-replica sync. (3) Turso-Rust's BEGIN CONCURRENT (MVCC) is contraindicated -- the hub serializes writes on purpose to keep the delta hash-chain fork-free.

**DATE:** 2026-06-25.
**STATUS:** Active. Default NOT flipped to libSQL yet (deliberate).

---

### ADR-013: delta-scp v2 -- state-aware graph-memory with Supabase AST persistence

**DECISION:** Brownfield upgrade turning the static repo compressor into a state-aware memory filter. Additions: state-aware anchor pruning (prune.ts), file-inbox flue (flue.ts), AST graph (graph.ts with Supabase persistence). Core compressTree (~97% of the engine) left untouched. Graph sync at REPO scope (delete-and-replace), not per-file.

**RATIONALE:** Needed state-awareness (pruning by anchor/symbol/trace), a downstream delivery channel (flue to droplist), and a persistent graph for cross-file relationships. Per-file graph sync was explicitly rejected because (1) no file-watcher exists, (2) per-file sync silently drops all cross-file import edges, (3) name-only edge mapping causes basename collisions, (4) CASCADE makes it decay.

**DATE:** 2026-06-21.
**STATUS:** Active.

---

### ADR-014: Flue uses file-inbox, not HTTP

**DECISION:** The flue (delta-scp's delivery channel to droplist) writes markdown drops to a file inbox directory (SCP_FLUE_DIR). It does NOT use an HTTP POST to droplist.

**RATIONALE:** Droplist works on a drop-to-packet grain, so a file inbox means zero edits to droplist. The two services live in different repo roots, making direct imports impossible.

**DATE:** 2026-06-21.
**STATUS:** Active.

---

### ADR-015: atlas-manifest.yaml -- generator-backed interface-first map with overlay model

**DECISION:** atlas-manifest.yaml (~449 lines, ~6.9k tokens) is a single interface-first YAML map of the entire Atlas system, regenerated deterministically by python audit/build_atlas_manifest.py. Mechanical facts re-derived every run. Curated knowledge lives in audit/manifest-overlay.yaml. Overlay model = drift only touches the derived layer.

**RATIONALE:** Needed a single document small enough for LLM upload that captures the real system structure. Generator + overlay separates mechanical re-derivation from human-curated knowledge.

**DATE:** 2026-06-25.
**STATUS:** Active.

---

### ADR-016: Item backbone -- unified GET /items aggregating four sources

**DECISION:** Unified item backbone via GET /items. Four sources: droplist, cycleboard, inpact, festival (399 items total at time of decision). Each source adapter normalizes to a common item shape.

**RATIONALE:** Multiple surfaces needed to query items but each had its own bespoke API. A single aggregation endpoint eliminates per-consumer integration work. Bricks 1-3 shipped.

**DATE:** 2026-06-26.
**STATUS:** Active. Brick 4 (shared identity / cross-surface item linking) pending.

---

### ADR-017: Content-addressed Receipt fabric with sigil sha256 join key

**DECISION:** seam.v1 Receipt (pydantic v2, frozen): {seam_version, tool, sha256, produced_at, status, data, error}. The join key across ALL tools is sigil's sha256 (computed over original bytes, enforced on unpack). Tools that lack content-addressing CONSUME sigil's sha as the join key rather than minting their own.

**RATIONALE:** Needed a single content-addressable identity that chains across a multi-tool pipeline. Sigil's sha256 is the only sound content-address in the fleet. The Receipt is a justified hand-roll because it is the connective tissue between heterogeneous tool outputs.

**DATE:** 2026-06-26.
**STATUS:** Active.

---

## Methodology

### ADR-018: Assemble-first posture -- default stance is assembler, not generator

**DECISION:** The default build posture is assembler, not generator. Before writing any non-trivial implementation, check whether it is a solved category. If yes, search the ecosystem for the mature, maintained package. Surface what you found by name before generating any implementation. Hand-roll only when: (1) no mature option exists, or (2) integration depth IS the product value and a library would make the product worse, not just later.

**RATIONALE:** Pattern confirmed across multiple projects: solved-category hand-rolls accumulate as debt. The discriminator is "worse vs later" -- if the library would make the product worse, hand-roll; if it would just make it finish sooner, use the library.

**DATE:** 2026-05-29.
**STATUS:** Active.

---

### ADR-019: No building without locked plan

**DECISION:** LAW: no code until WHAT (the concrete artifact/outcome) and WHY (the goal it serves) are written and locked. Plan to the end -- the whole path to done, not the next poke. Search before building is mandatory.

**RATIONALE:** Manual API fiddling, hand-rolled harnesses, and one-off probes are the failure mode. Exploration without a locked target reads as flailing. Exception: a probe is fine only when it is a named step inside an agreed plan.

**DATE:** 2026-07-13.
**STATUS:** Active.

---

### ADR-020: Six-mode homeostatic ladder

**DECISION:** System operates in six modes: RECOVER -> CLOSURE -> MAINTENANCE -> BUILD -> COMPOUND -> SCALE. Under the pivot (ADR-002), the ladder is no longer a psychological pacing gate but a system health/throughput gate for the execution substrate.

**RATIONALE:** Provides a single governance signal that gates what kind of work the system should accept. The six modes map naturally from human capacity states to system health states.

**DATE:** Original design; reframed 2026-07-04.
**STATUS:** Active.

---

## Product

### ADR-021: Modernization suite -- four tools as B2B legacy-modernization product

**DECISION:** code-recon + binre + sigil + delta-scp form a single legacy-modernization product. Pipeline: decompose -> understand/prove -> (decompile if no source) -> compose/carry -> deliver a modernization dossier. The seam (seam.v1 Receipts, sigil sha256 join key) is the productization spine. Unified entry point: binre/modernize.py auto-detects asset type.

**RATIONALE:** The four tools already existed independently. The seam integration provided the spine to chain them into one pipeline. Proven end-to-end on three different repo shapes with zero babysitting. Injection sweep found and fixed 11 real vulnerabilities including an unauth LLM-mediated RCE chain.

**DATE:** 2026-07-07.
**STATUS:** Active.

---

### ADR-022: tree-sitter WASM AST core for delta-scp

**DECISION:** web-tree-sitter (WASM, no node-gyp) + tree-sitter-wasms (precompiled grammars) as the AST extraction engine. Pin web-tree-sitter@0.22.6 (ABI compatibility). Eight languages: c, python, typescript, javascript, cpp, csharp, java, go. Opt-in via SCP_EXTRACTOR=treesitter flag; default remains regex.

**RATIONALE:** The regex extractor returns zero symbols for C/C++/C# and cannot extract call edges. tree-sitter provides exact line numbers, real function/class/struct extraction, and caller->callee call edges. WASM chosen over node-gyp for portability (B2B product must install without native build tools).

**DATE:** 2026-07-07.
**STATUS:** Active.

---

### ADR-023: HYDRA-S / Supagetti -- two-brand SaaS split

**DECISION:** Two-brand split for the modernization-suite SaaS. HYDRA-S = serious enterprise/house brand. Supagetti = playful self-serve funnel (Tier I). Three-tier menu: I Supagetti (self-serve cleanup), II Working Head (managed ship-and-keep-shipping), III Deepwater Head (enterprise no-source/binary decompile + due-diligence).

**RATIONALE:** The code-modernization product slot is effectively empty. Moat = sealed server-side delivery + no-source binary capability.

**DATE:** 2026-07-13.
**STATUS:** Active. Working names -- not locked.

---

## Tooling

### ADR-024: Tool lattice -- five-axis instruction set with Receipt-fabric composition

**DECISION:** Tools are an instruction set composed via the Receipt fabric with a router on top. Five axes: Fidelity, Trust, Time, Direction, Reflexivity. combo.py scores tool TUPLES (cofire + sequential) with synergy/lift metrics. Proven: combo router beats random (margin +0.57/+0.39/+0.19 across three hash-seed splits).

**RATIONALE:** Individual tools report "I ran" but never "I did well." The lattice treats tools as composable primitives rather than standalone programs. Synergy/lift metric surfaces real organic synergy.

**DATE:** 2026-06-25.
**STATUS:** Active.

---

### ADR-025: Tool outcome ledger with objective feed from seam Receipts

**DECISION:** Retroactive reward ledger feeding a Thompson bandit router. Backfill from transcripts (sentiment of next human message as proxy reward). Live append via Stop hook. Objective feed from seam: tools/seam/run.py appends one row per tool per run (source:"seam", reward = all-receipts-ok -> +1, any error -> -1).

**RATIONALE:** Proxy reward (sentiment) is noisy and neutral-heavy. The seam objective feed is the non-proxy signal that made the combo router beat random (ledger 93->129 rows; margin went from -0.06 to +0.19..+0.57).

**DATE:** 2026-06-25.
**STATUS:** Active.

---

### ADR-026: Stack integration seam -- seven surfaces via /call gateway

**DECISION:** Seven tool surfaces wired through the atlas-map /call gateway: sigil + binre + gw + ST3GG + delta-scp + code-recon + repo-inventory. Each tool exposed via atlas.surface.json overlays. Three model-agnostic access paths: seam CLI (in-process), HTTP POST /seam/call (:3072), MCP atlas_call.

**RATIONALE:** The stack had ~7 tools that were young and disconnected. Gateway hardened: opt-in behind DESCRIBE_GATEWAY_CLI=1 (fail-closed 501 when unset), argv-only with -- sentinel + leading-dash rejection, shutil.which abs-path.

**DATE:** 2026-06-26.
**STATUS:** Active.

---

### ADR-027: Write-token auth guard on all atlas-map-api POST routes

**DECISION:** X-Atlas-Token shared secret required on all state-changing POST routes. Resolution order: ATLAS_WRITE_TOKEN env -> <repo_root>/.atlas-write-token (gitignored) -> generated (secrets.token_urlsafe(32)) at startup. Single FastAPI dependency using secrets.compare_digest.

**RATIONALE:** HIGH security finding: state-changing POSTs had no auth. Bind-127.0.0.1 + restricted CORS was insufficient against DNS-rebind attacks. 56 tests covering 401 paths across all 5 POSTs.

**DATE:** 2026-06-20.
**STATUS:** Active.

---

*27 decisions extracted from project memory. This file is the provider-neutral record.*
*Last updated: 2026-07-15.*
