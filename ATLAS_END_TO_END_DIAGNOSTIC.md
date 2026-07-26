# Atlas — End-to-End Information Flow Diagnostic

> Verified read-audit. Every load-bearing claim cites `file:line`. Absence claims triangulated. No memory-sourced assertions. Generated 2026-07-23.

---

## (a) Directed flow diagram · three planes

```mermaid
flowchart LR
  subgraph INGEST["INGESTION SOURCES"]
    U_INPACT["inPACT UI · today.html<br/>human writes"]
    U_SETUP["atlas-setup.html<br/>human boot"]
    U_MISSION["atlas-mission-control.html<br/>human observe"]
    OPT["optogon :3010<br/>signal emitter"]
    COG["cognitive-sensor triage :8765<br/>KEEP/CLOSE/MINE verdicts"]
    CC["Claude Code sessions<br/>transcripts on disk"]
    DROP["droplist :3073<br/>capture -> DAG"]
  end

  subgraph DATA["DATA PLANE"]
    DK["delta-kernel :3001<br/>THE HUB · 80+ routes"]
    STORE["storage entities<br/>server.ts:2137"]
    ITEMS["atlas-map-api /items<br/>server.py:513 · 4 sources"]
    TIMELINE["timeline<br/>server.ts:2273"]
  end

  subgraph CONTROL["CONTROL PLANE"]
    GOV["governance daemon<br/>gated GOVERNANCE_DAEMON=1<br/>server.ts:83"]
    COCKPIT["Cockpit<br/>/api/atlas/cockpit :2102"]
    DIR["Directive emitter<br/>next-directive :2064"]
    PEND["pending_action entities<br/>createPendingAction<br/>cockpit.ts:499"]
    MODE["mode FSM<br/>6 modes"]
  end

  subgraph TELEM["TELEMETRY PLANE"]
    SIG["signals store<br/>POST /api/signals :1998"]
    WORK["work queue<br/>/api/work/* :1701-1955"]
    LIFE["life-signals<br/>:3066-3153"]
    CS["cortex :3009<br/>Directive.v1 -> TaskPrompt.v1"]
    UASC["uasc-executor :3008<br/>HMAC exec"]
    AEGIS["aegis-fabric :3002<br/>policy + approvals"]
  end

  subgraph SINK["OUTCOME SINKS"]
    NEXT["atlas-ai next<br/>CLI directive read"]
    BANNER["inPACT banner<br/>signals.js:35 pending render"]
    STATUS["/status :3072/status<br/>mission-control :2s"]
    LEDGER["work ledger persist"]
  end

  %% INGEST -> DATA
  U_INPACT ==LIVE==> DK
  U_SETUP ==LIVE==> STATUS
  DROP -.DORMANT: env-flag DROPLIST_ATLAS_SIGNALS_URL.-> DK

  %% Optogon signal chain
  OPT ==LIVE gated OPTOGON_SIGNAL_EMIT=1<br/>optogon/config.py:27==> DK
  DK ==LIVE approval_required forward<br/>server.ts:2007,2045==> OPT

  %% Cognitive sensor
  COG ==LIVE _run_sync_pipeline<br/>triage_server.py:232==> STORE
  COG ==LIVE cortex_bridge.emit<br/>auto_triage.py:189==> CS

  %% DATA persistence
  DK ==LIVE==> STORE
  DK ==LIVE==> TIMELINE
  DK ==LIVE aggregates 4 sources==> ITEMS

  %% CONTROL
  DK ==LIVE first caller<br/>governance_daemon.ts:1058==> GOV
  GOV ==LIVE creates pending==> PEND
  DK ==LIVE==> COCKPIT
  DK ==LIVE builds from state==> DIR

  %% TELEMETRY
  DK ==LIVE==> SIG
  DK ==LIVE==> WORK
  DK ==LIVE==> LIFE
  CS ==LIVE long-poll<br/>dispatcher/poll.py:1==> DIR
  CS ==LIVE POST /api/signals/bulk<br/>cortex/inpact/client.py:74==> DK
  CS -.SCAFFOLDED submit_task bypass.-> UASC
  DK -.DORMANT no wired write callers.-> AEGIS

  %% SINKS
  DIR ==LIVE==> NEXT
  PEND ==LIVE==> BANNER
  DK ==LIVE==> STATUS
  WORK ==LIVE==> LEDGER
  TIMELINE ==LIVE /api/notifications = timeline query :2540==> STATUS
```

**Plane legend:**
- **Data plane** = domain payloads (items, tasks, goals, cycleboard, life-signals)
- **Control plane** = mode/directive/pending-action orchestration (governance daemon output)
- **Telemetry plane** = signals + work queue + downstream execution (cortex/uasc/aegis)

---

## (b) Per-surface role table

| Surface | Port | Owned schemas | Emits (file:line + shape) | Consumes (file:line + shape) | Persistence | Depends on | Status |
|---|---|---|---|---|---|---|---|
| **delta-kernel** | 3001 | Signal.v1, Directive.v1, CloseSignal.v1, LifeSignals.v1, WorkLedger.v1, ModeContract.v1, CompoundState.v1, IdeaRegistry.v1, TimelineEvents.v1 | `Directive` on GET /api/atlas/next-directive (server.ts:2064-2091) · `pending_action` via `createPendingAction` (cockpit.ts:499) · timeline events (server.ts:2273) · forwards approval_required to Optogon (server.ts:2007, 2045) | `Signal` via handleSignalIngest (server.ts:1983-2000) · cognitive ingest POST /api/ingest/cognitive (server.ts:783) · life-signals POST (server.ts:3066+) · work request (server.ts:1701) | libsql spine + storage entities (loadEntitiesByType, server.ts:2137) | aegis-tenant-key auth · optogon URL | LIVE hub · daemon LIVE only when `GOVERNANCE_DAEMON=1` (server.ts:83) |
| **atlas-map-api** | 3072 | atlas.surface.json overlays · items backbone (bb: prefix) | GET /describe (surface forms) · GET /route (dispatch) · GET /items (aggregate) · GET /status · POST /call proxy · POST /map/start/{name} | reads snapshot of launch.json + retired set · items from 4 sources · atlas.surface.json per service | filesystem overlays · in-process snapshot | delta-kernel for `atlas_call` proxy | LIVE · writes gated behind `DESCRIBE_GATEWAY_WRITES=1` |
| **cognitive-sensor** | 3077 (also 8765 triage) | thread_decisions.json · memory_db.json | POST /api/decide upsert (triage_server.py:212) · fires fs_actor + decisions_to_atlas.py (triage_server.py:232) · emits Directive via cortex_bridge (auto_triage.py:189) | conversation index by numeric idx (triage_server.py:188) · triage verdicts KEEP/CLOSE/MINE/ARCHIVE/REVIEW/DROP/DONE/SKIP | thread_decisions.json · memory_db.json | delta-kernel + optogon | LIVE · REVIEW verdict on fs- card auto-starts Optogon triage session |
| **optogon** | 3010 | OptogonPath.v1 · OptogonNode.v1 · OptogonSessionState.v1 · Signal.v1 emissions | Signal to delta-kernel /api/signals when `OPTOGON_SIGNAL_EMIT=1` (config.py:23-27) · GET /signals debug read · POST /session/run drives paths | POST /session/start (path_id + initial_context) · POST /session/{id}/turn · signal-triggered path activation | in-memory session state | delta-kernel + Codex CLI | LIVE gated · `OPTOGON_SIGNAL_EMIT=1` set in launch.json:156 |
| **cortex** | 3009 | CortexTask.v1 · TaskPrompt.v1 · directive routing | POST /api/signals/bulk to delta-kernel (cortex/inpact/client.py:74) · TaskPrompt.v1 to Claude Code (README:10) · POST /tasks/submit UASC bypass (criticality 3, cortex/main.py:186) | Long-polls delta-kernel /api/atlas/next-directive (dispatcher/poll.py:1) · reads /api/cycleboard for inPACT state (cortex/inpact/client.py:14) | local queue + upstream fanout | delta-kernel :3001 + uasc :3008 + aegis :3002 (README:60) | LIVE consumer of directives |
| **uasc-executor** | 3008 | ExecutionSpec.v1 · ExecutionResult.v1 · TaskExecution.v1 | GET /commands · GET /runs · exec result | POST /exec (HMAC-signed cmd, criticality 3) | run history | HMAC key | LIVE terminal executor |
| **aegis-fabric** | 3002 | AegisAgent.v1 · AegisAgentAction.v1 · AegisApproval.v1 · AegisPolicy.v1 · AegisPolicyDecision.v1 · AegisTenant.v1 · AegisWebhook.v1 | GET /api/v1/approvals · GET /api/v1/deltas (hash-chain) · GET /api/v1/audit · Prometheus /metrics | POST /api/v1/agent/action (submit for policy eval) · POST /api/v1/approvals/:id (decide) · POST /api/v1/policies (set rules) | tenant DB + hash-chained delta ledger | admin key · tenant tokens | LIVE surface · no wired delta-kernel write consumer per grep of server.ts (aegis-client.ts:6 reads only) |
| **droplist** | 3073 | packets · DAGs · IdeaRegistry.v1 · MemoryPacket | GET /api/now · GET /api/dags · GET /api/packets · GET /api/entities · POST /api/drop (capture) | text captures · packet queue | droplist DB | delta-kernel signals ingest (`DROPLIST_ATLAS_SIGNALS_URL=http://localhost:3001/api/signals/ingest`, launch.json:355) · `DROPLIST_DAEMON=1` (launch.json:357) | LIVE with daemon; write-back to delta-kernel gated by env |
| **memory-hub** | 3071 | aggregate over droplist + idea-registry + cognitive-sensor | POST /search unified search · GET /idea/{canonical_id} · GET /entity/{name} graph neighbors | POST /save (append packet to droplist) | delegates to source stores | droplist + cognitive-sensor | LIVE |
| **search-stack** | 3070 | search results | POST /search routed · POST /extract page · POST /memory/save intel drop | url + query | 28-provider router | provider budgets | LIVE |
| **canvas-engine** | 3050 | AnatomyV1.v1 · session state | SSE /clone · SSE /edit · GET /sessions/:id/envelope | POST /clone url/image · POST /edit intent | in-process Vite pool | none | LIVE isolated · not wired to Atlas control plane |
| **code-converter** | 3007 | conversion I/O | HTTP conversions | source code | in-mem | none | LIVE isolated |
| **openclaw** | 3004 | claw state | (surface not read in this pass) | HTTP | in-mem | none | LIVE isolated |
| **inpact** (app) | 3006 | today.html live UI · calendar · signals banner | writes cycleboard, tasks, life-signals via atlas-ai routes | reads /api/actions/pending (signals.js:35) · /api/signals · /api/auth/token | delta-kernel via HTTP | delta-kernel :3001 | LIVE — the ONLY human-facing surface reading pending actions |
| **atlas-setup.html** | 8888 (http-server) | none | POST /call → :3072 to start/stop services | GET :3072/status | none | atlas-map-api | LIVE boot UI |
| **atlas-mission-control.html** | 8888 static | none | polls :3072/status every 2s (mission-control.html:69, 93-94) | services + governance daemon + scheduled tasks + orphan listeners | none | atlas-map-api /status | LIVE observability shell |
| **triangulation** | 3075 | (audit surface) | verify capability | anatomy elements | HTTP | none | LIVE isolated |
| **ws-gateway** | 3013 | websocket routing | ws messages | client subs | in-mem | none | LIVE transport |
| **delta-scp-demo** | 3012 | jobs Map | POST /jobs (write-gated) · GET /jobs/{id} | repo compression requests | in-memory Map (demo-server.ts:98) | none | LIVE demo · jobs lost on restart |
| **cycleboard** (static) | 8889 static | none | none | GET :3001/api/cycleboard | none | delta-kernel | LIVE observability shell |

**Retired** (per atlas_status): ai-exec-pipeline, blueprint-generator, mirofish, mosaic-dashboard, mosaic-orchestrator.

---

## (c) Visibility matrix · canonical entities

| Entity | Visible in UI | Behind-scenes | Invisible to operator |
|---|---|---|---|
| **items** (unified backbone) | atlas-map-api `GET /items` · inPACT feed (item backbone brick 1, git log 2026-06-20) | `items.py` aggregator across droplist/cycleboard/inpact/festival (server.py:513-523; 4 sources at items.py:75, 111, 133, 191) | — |
| **actions (pending)** | **inPACT banner ONLY** (signals.js:35 poll every 5s, MAX 30s backoff) | `createPendingAction` (cockpit.ts:499) called by governance daemon at 3C (governance_daemon.ts:1058); stored as `pending_action` entity (server.ts:2137) | not on atlas-setup.html · not on mission-control · not on cycleboard shell · not on any :3072 view |
| **signals** | inPACT banner priority-styled cards (signals.js:107-115) · optogon `GET /signals` debug | `handleSignalIngest` (server.ts:1983); listSignals; approval_required forwarded to Optogon (server.ts:2045) | signal store contents beyond banner filter · signal→daemon triggering |
| **directives** | `atlas-ai next` CLI · consumed by cortex/dispatcher/poll.py:1 | `DirectiveEmitter.emit` at /api/atlas/next-directive:2078 | returns 204 when no directive — silent void |
| **cockpit** (mode + prepared actions + top tasks + drafts + leverage) | GET /api/atlas/cockpit :2102 returns JSON | `buildCockpit` in cockpit.ts | no HTML dashboard renders cockpit end-to-end |
| **cycles / cycleboard** | cycleboard static shell :8889 · inPACT edits · atlas-ai CLI `/api/cycleboard` (atlas-ai.ts:155) | GET/PUT `/api/cycleboard` (server.ts:2710, 2729) | mode-derived cycle events |
| **journals / timeline** | timeline endpoint /api/timeline · atlas-ai `/api/timeline` writes CHECKPOINT/DAY_WRAP/INBOX_PROCESSED/RESEARCH_COMPLETED/DRAFTS_GENERATED (atlas-ai.ts:767+) | timeline persistence | `/api/notifications` (server.ts:2540) IS a timeline query with limit 50 — no separate notifications table exists |
| **transcripts** | (none in Atlas UIs) | cognitive-sensor triage_server.py:188 reads memory_db.json by numeric idx; `_run_sync_pipeline` fs_actor + decisions_to_atlas.py | raw JSONL on disk under Claude Code project dirs; not indexed inside Atlas UI |
| **instincts** (continuous-learning v2) | (none in Atlas surfaces) | external tool `instinct-cli.py`; drops into ~/.claude | not part of Atlas control plane at all |
| **work jobs** | atlas-ai CLI (atlas-ai.ts:622-631, 1290, 1349) · GET /api/work/status :1841 · /api/work/metrics :1938 · SSE /api/work/subscribe :1955 | work controller ledger · claim/heartbeat/complete/cancel | HTML dashboard exists in mission-control for governance daemon but NOT a live work-queue viewer |
| **mode / directive** | atlas-ai CLI `state` / `next` (atlas-ai.ts extensively) · cockpit JSON | 6-mode FSM in delta-kernel core/types.ts (Mode type) | mode-since transition timestamps in `state.last_mode_transition_at` (server.ts:2098) |
| **cognitive signals** (energy/finance/skills/network) | inPACT + atlas-ai (atlas-ai.ts:339-376) | /api/life-signals/* (:3066-3153) | aggregated LifeSignals.v1 payload not visible on setup/mission-control |
| **capability manifests** | atlas_describe MCP · GET :3072/describe/{surface} | atlas.surface.json overlays verified by scripts/verify_overlays.py | redacted_proofs HMAC hashes only surface to over-cleared auditors |
| **approvals (aegis)** | GET /api/v1/approvals (internal-only) | aegis-fabric hash-chained delta ledger | aegis-client.ts inside delta-kernel READS approvals (aegis-client.ts:56) but NO wired writer surface pushes actions to aegis in the audit trail |

**Dead-air pockets found:**
1. **`pending_action` queue → operator UI is single-thread.** Only inPACT's fixed-position banner renders them (signals.js:117-124). Setup shell and mission-control shell do not. If inPACT tab is not open, the operator never sees a pending action.
2. **`/api/notifications` is a lie.** It is a timeline aggregator (server.ts:2544 `timeline.query`), not a notification stream. No push, no separate topic.
3. **aegis-fabric writes are orphan.** delta-kernel imports `aegis-client.ts` (line 6 comments approvals) but grep of `server.ts` for `POST /api/v1/agent/action` returns zero — no code path submits agent actions to aegis today.
4. **cognitive triage → delta-kernel → operator has no round-trip.** `decisions_to_atlas.py` prunes open_loops from governance_state.json (SYSTEM_MAP.md:107) but no UI shows "we pruned N loops today."

---

## (d) Live-capability inventory · verified

### LIVE (traced to wired call site or /describe overlay)

| Surface | Capability | Route | Direction | Criticality | Proof |
|---|---|---|---|---|---|
| delta-kernel | health | GET /api/health | R | 0 | server.ts:2403 |
| delta-kernel | view_state | GET /api/state | R | 0 | server.ts:403 |
| delta-kernel | next_directive | GET /api/atlas/next-directive | R | 0 | server.ts:2064 |
| delta-kernel | emit_signal | POST /api/signals | W | 1 | server.ts:1998 |
| delta-kernel | create_task | POST /api/tasks | W | 1 | server.ts:513 |
| delta-kernel | work-queue set | /api/work/{request,claim,complete,heartbeat,cancel,status,history,metrics,subscribe} | R+W | 1 | server.ts:1701-1955 |
| delta-kernel | pending action set | GET/POST/confirm/cancel /api/actions/pending | R+W | 1 | server.ts:2763, 2782, 2825, 2954 |
| delta-kernel | cockpit | GET /api/atlas/cockpit | R | 0 | server.ts:2102 |
| delta-kernel | cycleboard | GET/PUT /api/cycleboard | R+W | 1 | server.ts:2710, 2729 |
| delta-kernel | life-signals | POST /api/life-signals/{energy,finance,skills,network,bulk} | W | 1 | server.ts:3066-3153 |
| delta-kernel | timeline | GET/POST /api/timeline | R+W | 1 | server.ts:2273, 2322 |
| delta-kernel | law close_loop | POST /api/law/close_loop | W | 2 | server.ts:1322 |
| atlas-map-api | describe | GET /describe/{surface}?role=R | R | 0 | server.py, SELF_DESCRIBE.md:68 |
| atlas-map-api | route | GET /route?q= | R | 0 | server.py; verified via `atlas_route` MCP this session |
| atlas-map-api | items | GET /items | R | 0 | server.py:513 |
| atlas-map-api | status | GET /status | R | 0 | server.py:748 |
| atlas-map-api | set_status | POST /items/{id}/status | W | 1 | server.py:526 (write-token gated) |
| atlas-map-api | start_service | POST /map/start/{name} | W | 2 | atlas.surface.json:11 |
| atlas-map-api | call_traffic | GET /map/calls | R | 0 | ef62908 2026-07-06 per-capability call counter |
| cognitive-sensor | post-decide | POST /api/decide | W | 1 | triage_server.py:212 |
| cognitive-sensor | get-conv | GET /api/conv/{idx} | R | 0 | triage_server.py:188 |
| cortex | dispatcher poll | long-poll /api/atlas/next-directive | R | 0 | dispatcher/poll.py:1 |
| cortex | inpact_run | POST /inpact/run/{module} | W | 2 | atlas.surface.json:41 |
| optogon | session_run | POST /session/run | W | 2 | atlas.surface.json:41 |
| optogon | signals_list | GET /signals | R | 0 | main.py:345 |
| uasc-executor | exec_command | POST /exec | W | 3 | atlas.surface.json:35 |
| droplist | drop | POST /api/drop | W | 1 | droplist surface + `DROPLIST_ATLAS_SIGNALS_URL` wired at launch.json:355 |
| memory-hub | search | POST /search | R | 0 | memory-hub surface |
| aegis-fabric | list_approvals | GET /api/v1/approvals | R | 0 | atlas.surface.json:77 · aegis-client.ts:56 confirms delta-kernel reader |

### SCAFFOLDED / DORMANT (gate flag or missing caller cited)

| Surface | Capability | Gate flag / dead-end proof |
|---|---|---|
| delta-kernel | governance daemon start | Gated `GOVERNANCE_DAEMON === '1'` (server.ts:83). Set by `scripts/start_atlas.ps1:21`. A bare `npx tsx src/api/server.ts` runs daemon-off. |
| atlas-map-api | any write via /call | Gated `DESCRIBE_GATEWAY_WRITES=1` (docs/archive/2026-07/STACK_INTEGRATION_AUDIT_2026-06-26.md; seam docs; server enforces 501 refusal without it) |
| atlas-map-api | CLI-kind surfaces via /call | Gated `DESCRIBE_GATEWAY_CLI=1` (SEAM.md:88) |
| optogon | Signal emit into delta-kernel | Gated `OPTOGON_SIGNAL_EMIT=1` (config.py:27). Set in launch.json:156 — so LIVE when optogon booted from atlas-setup; DORMANT if optogon started ad-hoc |
| aegis-fabric | submit_agent_action + policy pipeline | Route declared at :3002, but grep of delta-kernel `server.ts` for POST to `/api/v1/agent/action` returns 0 — no wired writer. Verified 3-angle: symbol search `AegisAgentAction`, route search `/api/v1/agent/action`, schema search `AegisAgentAction.v1`. Only the READ side (aegis-client.ts:56 lists approvals) is wired. |
| cortex | submit_task bypass | criticality 3 · `exposure: internal` · only reachable with root token · zero UI button |
| delta-scp-demo | job persistence | jobs live in in-memory `Map` (demo-server.ts:98) — id does not survive server restart (atlas.surface.json:24) |
| canvas-engine | Atlas control-plane integration | Wired to nothing in delta-kernel. `handleSignalIngest` never fires from canvas-engine; canvas envelopes are not consumed by any Atlas surface. Isolated. |
| ws-gateway | signal streaming | Present at :3013 but no UI subscribes to it. `/api/work/subscribe` (server.ts:1955) uses its own SSE, not ws-gateway. |
| /api/atlas/close-signal | outcome closure | POST route lives at server.ts:2160 · atlas-ai does NOT call it (grep of atlas-ai.ts returns zero `close-signal` hits) · the closure loop calls `/api/law/close_loop` instead. Two closure paths, one dead. |

---

## (e) Adoption-friction diagnostic · MAPE-K gap analysis

Evidence-only. Each gap cites the dead-end.

### Monitor gap · signals captured but never surfaced to the operator

- **Cognitive-sensor triage decisions.** `POST /api/decide` (triage_server.py:212) upserts a verdict and fires `_run_sync_pipeline` on a daemon thread (triage_server.py:232). The pipeline mutates `governance_state.json` (SYSTEM_MAP.md:107). **No UI reflects that the mutation happened.** Operator triages 20 threads, and nothing changes in atlas-setup or mission-control.
- **Life-signals bulk.** POST /api/life-signals/bulk (server.ts:3153) accepts energy/finance/skills/network in one call. There is no UI aggregator that reads back the composite `LifeSignals.v1` picture. Only atlas-ai in a CLI does (atlas-ai.ts:339-376).

### Analyze gap · telemetry hits a dead end without producing a directive

- **Signal → Directive coupling is weak.** `handleSignalIngest` (server.ts:1983) stores and (conditionally) forwards to Optogon at server.ts:2007 only when `signal.source_layer === 'optogon' && signal.signal_type === 'approval_required'` (server.ts:2045). All other source_layers (droplist, ghost_executor, claude_code, site_pull — per signals.js:45-51) stop at the store. **The DirectiveEmitter (server.ts:2078) does not consult individual signals** — it builds from `delta_state + cognitive_state + work_ledger + user_preferences`. So a signal you fire from droplist is invisible to the next-directive path.
- **`atlas/next-directive` returns 204 silently** (server.ts:2079-2081) when nothing to say. The operator polling gets nothing and has no reason to keep polling. No "here is why the well is dry" surface.

### Plan gap · system prepares an action but does not notify

- **`createPendingAction` writes an entity** (cockpit.ts:499); governance_daemon.ts:1058 is its only caller in the repo (per grep). Delivery is entirely **inPACT-tab pull** (signals.js:35 polls every 5-30s). If inPACT is not open, the pending action is silent. Neither `atlas-setup.html` nor `atlas-mission-control.html` render `/api/actions/pending`. Verified 2-angle: grep of both HTML files for `pendingAction|actions/pending` returns zero hits.
- **`/api/notifications` is misleadingly named** (server.ts:2540). It is `timeline.query({ limit: 50 })` — a *pull* over past events, not a push notifier.

### Execute gap · operator context-switches to CLI to close a loop a UI button could close

- **atlas-ai CLI is the closure hammer.** atlas-ai.ts hits `/api/law/close_loop` at four different sites (384, 390, 712, 815). No UI button in atlas-setup, mission-control, cycleboard shell, or the Atlas map view calls `/api/law/close_loop`. Verified 2-angle: repo-wide grep of `*.html` for `close_loop` returns zero. Operator must open a terminal.
- **`/api/atlas/close-signal` (server.ts:2160) exists in parallel to `close_loop`** — two closure endpoints, and the CLI uses the other one. Neither has a UI button.

### Knowledge gap · state exists that no surface renders

- **Cockpit endpoint returns a rich object** (mode, signals, prepared actions, top tasks, drafts, leverage moves, mode_since — server.ts:2094-2100). **No HTML dashboard renders cockpit end-to-end.** Verified 2-angle: grep of Pre Atlas *.html for `/api/atlas/cockpit` returns zero.
- **`mode_since` stamp** (server.ts:2098) is load-bearing but only visible in JSON. Operator has no "how long have I been in COMPOUND" gauge.
- **Work-queue metrics** (server.ts:1938) and SSE stream (server.ts:1955) exist. No mission-control panel subscribes. Mission-control polls `/status` every 2s (mission-control.html:69) but that is the atlas-map-api status snapshot, not delta-kernel work-queue signal.
- **aegis-fabric hash-chained delta ledger** (surface capability list_deltas, verify_hash_chain) has zero UI. Operator cannot see what the fabric decided.

**Summary of the friction shape:** Atlas ingests, indexes, analyzes, plans, and executes — but the **notification edge is missing everywhere except the inPACT tab**. Every other UI (setup, mission-control, cycleboard, atlas-map viewer) is *observability of infrastructure*, not *presence of pending human decisions*. The system asks "is delta-kernel up?" fluently and "does the operator have anything queued for them?" only inside inPACT. If inPACT is not the tab in front, Atlas is silent.

---

## (f) Chronological layering · stratigraphy

Reconstructed from `git log --diff-filter=A` on entrypoints and `git log --all` on cycleboard.

| Layer | First evidence | What was added | Wired to prior layer? |
|---|---|---|---|
| **L0 · CycleBoard iframes** | 2026-01-12 `ed9986b` initial commit; 2026-02-09 `3cbce3e` "Add missing iframe sources for ATLAS CORE tabs" | Static shell, iframe host, tab UI | — |
| **L1 · Realtime state stream** | 2026-01-12 `5385eb5` "Add realtime unified state streaming" | Unified state stream endpoint | Wires L0 iframes to a live backend feed |
| **L2 · Governance pipeline + monetization** | 2026-03-24 `13f57e7` "Close-to-ship: wire governance pipeline, add tests, deployment & monetization assets" | Governance pipeline scaffold | First control-plane bridge into L1 stream |
| **L3 · CycleBoard live wiring** | 2026-03-25 `b37e794` "Wire all disconnected CycleBoard elements to live data (CW0001)" | CW0001 fest — disconnected UI wires filled | Explicitly rewires L0 to L1 (CycleBoard had drift since day one) |
| **L4 · Phase 0 stability** | 2026-04-05 `32c29d9` "Phase 0 stability patches — process lock, atomic writes, loop bridge, sync prompt" | Process lock, atomic writes, loop bridge | Fixes concurrency in L1-L3 |
| **L5 · auto_actor + embedded queue** | 2026-04-06 `59dd935` + `82a17cc` "auto_actor — system does the work, not you" + "Phase 2 — pipeline autonomy + embedded execution queue" | The self-doing daemon; execution queue inside delta-kernel | New autonomous execute plane on top of L2 governance |
| **L6 · UASC bridge + full state sync** | 2026-04-14 `4c45676` "full system state sync — UASC bridge, auto_actor, CycleBoard, dead code cleanup" | UASC-executor wired, CycleBoard sync back-flow | Fanout: L5 → uasc + back to L0 |
| **L7 · Universal Triage Inbox / Optogon-stack** | 2026-04-19 `633a0ab` + 2026-04-06 `306e6f7` "Phase 3 integration - Atlas emits, Cortex consumes, InPACT renders" | Optogon (Universal Triage Inbox); Atlas→Cortex→InPACT hand-off | Adds cognitive-sensor + inPACT as consumers of L5 |
| **L8 · Cycleboard push bridge** | 2026-04-20 `f0a4334` "cycleboard_push bridge — auto_actor output lands on CycleBoard" | auto_actor → cycleboard write-back | Round-trip closes L0 ← L5 |
| **L9 · Thread lifecycle + aegis logging** | 2026-04-27 `ee69cdc` "thread lifecycle tracking + aegis_client logging + harvester pipeline" | aegis-client.ts reader path; thread lifecycle | aegis-fabric introduced as a READ-only consumer of delta-kernel activity |
| **L10 · CS ingest.py + atlas_explorer + galaxy view** | 2026-05-27 `76a5a2c` + `990caf2` + `1cffd2c` | Full corpus refresh; clickable atlas explorer; WebGL galaxy | New indexing/sorting layer over cognitive-sensor corpus |
| **L11 · Item backbone + GPS live state** | 2026-06-20 `e8f7767` + `e0dea1c` + `1435bf4` + `69743f9` + `c6cc7ae` | items backbone unified read; atlas-map drives services (start/stop/restart); inPACT feeds off the backbone; lattice renders droplist DAGs | The **unification wave** — 4 fragmented item stores collapsed to one endpoint; the map now can *do*, not just describe |
| **L12 · Self-describing surfaces + call gateway** | 2026-06-24 `6c6585d` + `c3cbc99` "self-describing surfaces — 35/35 capability registry" + "layer-3 call gateway — POST /call, registry-enforced proxy" | atlas.surface.json overlays; POST /call proxy | Meta layer: every surface can now narrate itself — the front door |
| **L13 · Seam / cognitive-sensor loop_clearer** | 2026-06-26 `a79c620` "perceive->compile->carry stack (SEAM #1)" · 2026-07-06 `54206ef` "loop_clearer UI to drain open-loop backlog" · `ef62908` "per-capability call counter" | Seam CLI wraps 7 tools with Receipts; loop_clearer UI; call telemetry | Adds outcome ledger + observability of /call traffic |
| **L14 · Cortex/InPACT stale-mode fix** | 2026-07-07 `3485186` "stale today.json was overriding the live mode gate" | Bugfix + regression tests | Fixes lava-layer drift where L11 today.json shadowed L5 mode gate |
| **L15 · LangGraph Skill Lattice** | 2026-07-15 `5b14a6d..1c784a9` Seq 1-7 shipped in one week | Seam Receipts persisted by run_id; LangGraph spine; Skill→Receipt adapters; bandit node; learn-loop; live viewer; Supervisor resumes killed runs | Wires Atlas→lattice→delta-kernel work-queue closure |
| **L16 · /route dispatch + autopilot capability** | 2026-07-15 `11ddefd` "add /route dispatch layer + wire autopilot as a capability" | Free-text intent → (surface, capability) routing | Completes the L12 self-description trilogy: describe / call / route |
| **L17 · Unified /status + inPACT Gcal sync** | 2026-07-20 `603928c` + `51cd417` | GET :3072/status one-shot; mission-control feeds off it; inPACT calendar sync | Aggregator layer — the "one place" for observability |
| **L18 · GOVERNANCE_DAEMON gate** | 2026-07-20 `b11b59c` "gate governance daemon behind GOVERNANCE_DAEMON=1 (AC0002 Wave 1.1)" | Daemon off by default in bare `tsx` runs | Fest AC0002 consolidation wave; **live layer that closed a footgun** |

### Lava-layer strata identified

| Stratum | Symptom | Never-wired-to-prior evidence |
|---|---|---|
| **canvas-engine :3050** | No signal/directive integration | Zero grep hits for `canvas-engine` in delta-kernel `server.ts`. Isolated island. |
| **aegis-fabric write path** | Reader wired (aegis-client.ts:56), writer never | delta-kernel `server.ts` has no `POST /api/v1/agent/action` call. Verified 3-angle. |
| **`/api/atlas/close-signal`** | Parallel closure path to `/api/law/close_loop` | atlas-ai CLI closes via `close_loop` only; `close-signal` route has no CLI/UI caller in the audited surfaces. |
| **`/api/notifications`** | Misnamed — is a timeline query | server.ts:2544 does `timeline.query`; no distinct notification store |
| **cortex `POST /tasks/submit`** | criticality 3 bypass with no UI button | atlas.surface.json:49 declares "bypasses delta-kernel queue"; no wired caller in audit trail |
| **ws-gateway :3013** | No subscriber of its ws topics | work-queue SSE at server.ts:1955 uses its own transport |
| **delta-scp-demo jobs** | In-memory Map, no persistence | atlas.surface.json:24: "jobs live in an in-memory Map (demo-server.ts:98), so an id does not survive a server restart" |

---

## Verification ledger · deduped, sorted

- `.claude/launch.json:21` — atlas-map-api entry (referenced order)
- `.claude/launch.json:156` — `OPTOGON_SIGNAL_EMIT=1` set on optogon start
- `.claude/launch.json:355` — `DROPLIST_ATLAS_SIGNALS_URL=http://localhost:3001/api/signals/ingest`
- `.claude/launch.json:357` — `DROPLIST_DAEMON=1`
- `apps/inpact/js/signals.js:35` — `PENDING_ENDPOINT` = `/api/actions/pending`
- `apps/inpact/js/signals.js:107-115` — banner priority style (approval_required / urgent / info)
- `apps/inpact/js/signals.js:117-124` — banner card DOM render
- `atlas-mission-control.html:69` — polls `:3072/status` every 2s
- `atlas-mission-control.html:93-94` — HUB const, POLL_MS
- `atlas-setup.html:68-69` — mission-control + status links from setup
- `ATLAS_CONSOLIDATION_PRESEARCH.md:106` — GOVERNANCE_DAEMON gate design
- `docs/archive/2026-07/SEAM.md:88` — DESCRIBE_GATEWAY_CLI / WRITES gates
- `docs/archive/2026-07/STACK_INTEGRATION_AUDIT_2026-06-26.md:35` — CLI hardening
- `scripts/start_atlas.ps1:21` — `GOVERNANCE_DAEMON='1'` set at fleet start
- `services/aegis-fabric/atlas.surface.json:22-155` — 18 capabilities incl. list_approvals, decide_approval
- `services/atlas-map-api/atlas.surface.json:5-13` — 8 capabilities incl. describe, route, items status
- `services/atlas-map-api/SELF_DESCRIBE.md:56-62` — 10 surfaces, 74 capabilities as of 2026-06-24
- `services/atlas-map-api/src/atlas_map_api/server.py:39` — items backbone import
- `services/atlas-map-api/src/atlas_map_api/server.py:513-523` — GET /items aggregator
- `services/atlas-map-api/src/atlas_map_api/server.py:526-534` — POST /items/{id}/status write
- `services/atlas-map-api/src/atlas_map_api/server.py:552-557` — GET /items/{id}/workflow
- `services/atlas-map-api/src/atlas_map_api/server.py:748` — GET /status
- `services/atlas-map-api/src/atlas_map_api/items.py:75, 89, 111, 133, 191, 299` — item backbone sources (droplist, cycleboard, inpact, festival)
- `services/canvas-engine/atlas.surface.json:1-76` — 8 canvas-engine capabilities
- `services/cognitive-sensor/atlas.surface.json:22-24` — post-decide fires _run_sync_pipeline
- `services/cognitive-sensor/auto_triage.py:189` — cortex_bridge emit
- `services/cognitive-sensor/SYSTEM_MAP.md:105-107` — cortex_bridge + decisions_to_atlas.py flow
- `services/cognitive-sensor/triage_server.py:188` — GET /api/conv/{idx}
- `services/cognitive-sensor/triage_server.py:212` — POST /api/decide
- `services/cognitive-sensor/triage_server.py:232` — daemon thread _run_sync_pipeline
- `services/cortex/atlas.surface.json:41-53` — inpact_run + submit_task (criticality 3)
- `services/cortex/README.md:10` — Atlas → Directive.v1 → Cortex → TaskPrompt.v1 → Claude Code
- `services/cortex/README.md:60` — upstream deps
- `services/cortex/src/cortex/dispatcher/poll.py:1` — long-polls delta-kernel next-directive
- `services/cortex/src/cortex/inpact/client.py:14` — /api/cycleboard wrapper
- `services/cortex/src/cortex/inpact/client.py:74` — POST /api/signals/bulk feeds Markov core
- `services/cortex/src/cortex/main.py:186` — /tasks/submit bypasses delta-kernel queue
- `services/delta-kernel/atlas.surface.json:4-12` — 7 delta-kernel capabilities
- `services/delta-kernel/src/api/server.ts:83` — `if (process.env.GOVERNANCE_DAEMON === '1')` daemon start
- `services/delta-kernel/src/api/server.ts:144` — GET /api/auth/token
- `services/delta-kernel/src/api/server.ts:361-403` — /api/state{,/unified,/unified/stream}
- `services/delta-kernel/src/api/server.ts:429` — PUT /api/state
- `services/delta-kernel/src/api/server.ts:498-585` — tasks CRUD
- `services/delta-kernel/src/api/server.ts:650-746` — goals CRUD + criteria + close
- `services/delta-kernel/src/api/server.ts:783` — POST /api/ingest/cognitive
- `services/delta-kernel/src/api/server.ts:880` — GET /api/daily-brief
- `services/delta-kernel/src/api/server.ts:945-1322` — law endpoints incl. close_loop
- `services/delta-kernel/src/api/server.ts:1701-1955` — work queue set
- `services/delta-kernel/src/api/server.ts:1983-2000` — handleSignalIngest + aliases
- `services/delta-kernel/src/api/server.ts:2007` — `OPTOGON_URL`
- `services/delta-kernel/src/api/server.ts:2045` — optogon forward gate: source_layer=optogon + approval_required
- `services/delta-kernel/src/api/server.ts:2064-2091` — next-directive emitter (returns 204 on empty)
- `services/delta-kernel/src/api/server.ts:2102` — cockpit endpoint
- `services/delta-kernel/src/api/server.ts:2137` — `storage.loadEntitiesByType<PendingActionData>('pending_action')`
- `services/delta-kernel/src/api/server.ts:2160` — POST /api/atlas/close-signal (parallel closure path)
- `services/delta-kernel/src/api/server.ts:2178-2187` — preferences GET/POST
- `services/delta-kernel/src/api/server.ts:2219-2246` — lattice viewmodel + correct
- `services/delta-kernel/src/api/server.ts:2273-2322` — timeline endpoints
- `services/delta-kernel/src/api/server.ts:2451-2465` — daemon status + run
- `services/delta-kernel/src/api/server.ts:2540-2554` — /api/notifications is a timeline query
- `services/delta-kernel/src/api/server.ts:2558-2576` — CLI manifest
- `services/delta-kernel/src/api/server.ts:2710-2729` — cycleboard
- `services/delta-kernel/src/api/server.ts:2763-2954` — pending action set (GET/POST/confirm/cancel)
- `services/delta-kernel/src/api/server.ts:3066-3153` — life-signals endpoints
- `services/delta-kernel/src/cli/atlas-ai.ts:339-376` — life-signals CLI writers
- `services/delta-kernel/src/cli/atlas-ai.ts:384, 390, 712, 815` — close_loop CLI callers
- `services/delta-kernel/src/cli/atlas-ai.ts:622-631, 1290, 1349` — work-queue CLI callers
- `services/delta-kernel/src/cli/atlas-ai.ts:767+` — timeline event writers (CHECKPOINT/DAY_WRAP/INBOX_PROCESSED/RESEARCH_COMPLETED/DRAFTS_GENERATED)
- `services/delta-kernel/src/clients/aegis-client.ts:6, 56` — aegis approvals READER (no writer path)
- `services/delta-kernel/src/core/cockpit.ts:499` — `createPendingAction` definition
- `services/delta-kernel/src/governance/governance_daemon.ts:19` — imports createPendingAction
- `services/delta-kernel/src/governance/governance_daemon.ts:1058` — the ONLY caller of createPendingAction
- `services/droplist/atlas.surface.json:5-13` — 8 droplist capabilities
- `services/memory-hub/atlas.surface.json:1-51` — 5 memory-hub capabilities
- `services/optogon/atlas.surface.json:22-65` — 7 optogon capabilities incl. session_run + signals_list
- `services/optogon/src/optogon/config.py:23-27` — OPTOGON_SIGNAL_EMIT ladder
- `services/optogon/src/optogon/main.py:345` — GET /signals endpoint
- `services/search-stack/atlas.surface.json:1-49` — 5 search-stack capabilities
- `services/uasc-executor/atlas.surface.json:5-38` — 4 uasc capabilities incl. exec_command criticality 3
- `tools/delta-scp-demo/atlas.surface.json:24` — in-memory Map, no restart persistence
- git log — chronology anchors (see section f)
- `contracts/schemas/` — 49 canonical schemas cataloged; key ones: Signal.v1, Directive.v1, CloseSignal.v1, WorkLedger.v1, ModeContract.v1, CompoundState.v1, LifeSignals.v1, CortexTask.v1, TaskPrompt.v1, OptogonNode.v1, OptogonPath.v1, AegisAgent/AegisPolicy/AegisApproval/AegisWebhook/AegisTenant, AtlasArtifact.v1, IdeaRegistry.v1, TimelineEvents.v1

**UNVERIFIED items (pending):**
- Anthropic/OpenAI-side LLM proxy inside `atlas-setup.html` — the "Interpret & plan" flow at line 112. Needs a full read of the LLM handler to confirm it never sends secrets to backend. Recommend `security-reviewer` sweep before adopting.
- ws-gateway :3013 topic list — the surface has no `atlas.surface.json` overlay declaring topics; the readme in `services/ws-gateway/` was not inspected in this pass.
- crucix, perception, triangulation, openclaw internal telemetry — probed only via atlas.surface.json existence; internal state model not audited.

---

*Generated by /groundwork · delta-scp orient step skipped (skeleton derived from atlas_status + launch.json + git log). code-recon evidence trail complete. fest step skipped per operator directive (single-artifact audit).*
