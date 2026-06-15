# DropList / DAG Engine Product Bible

**Status:** Living document. The contract for the DropList Packet Engine.
**Doctrine card:** see `DOCTRINE.md`. Quote it at the top of every Execution Packet.
**Workflow:** see §14. The Bible is the source. Execution Packets in `PACKETS/` are the bites.

---

## §1. Product Definition

DropList is a capture-to-execution system. It takes messy real-world input and turns it into structured operating state.

DropList is **not**:
- a note app
- a chatbot
- a linear task list

The core function:

```
Drop -> Packet -> Graph -> Dispatch -> Result -> Review -> Update -> Next Node
```

DropList helps a user capture fragmented reality, preserve context, detect dependencies, move ready work, and prevent already-finished work from being reopened.

---

## §2. Core User Problem

The user does not think in linear checklists. The user thinks in connected systems: dependencies, blockers, parallel paths, recurring loops, and unfinished nodes.

Most productivity tools force linear lists. Most AI tools respond with paragraphs. DropList gives messy input an execution structure.

---

## §3. Product Principle

**The graph has authority.**

Agents, tools, automations, and users can propose. The graph controls state.

- No node is done without evidence.
- No tool action runs without a node.
- No dependency is removed without reason.
- No completed core is reopened unless validation fails.

---

## §4. Core Loop

1. User drops messy input.
2. System creates a structured packet.
3. Packet becomes a DAG.
4. Dispatcher finds ready nodes.
5. Nodes are routed to human, AI, tool, or automation.
6. Results are captured as evidence.
7. Reviewer checks result against `done_condition`.
8. Graph updates.
9. Newly unblocked nodes become ready.
10. System summarizes current state.

---

## §5. Key Objects

### Drop
Raw user input. Text, voice transcript, photo note, list, log, idea, bug report, or observation.

### Packet (`droplist/schema.py::WorkPacket`)
Structured interpretation of a drop. Closed enum fields: `type, domain, assigned_to, status`.

Required fields: `drop_id, created_at, raw_input, normalized_input, input_hash, type, domain, entities, retrieved_context, assigned_to, next_action, stop_condition, allowed_actions, blocked_actions, confidence, needs_human_decision, memory_update, status`.

### DAG (`droplist/dag_builder.py::build_dag`)
A dependency graph created from a packet.

Fields: `dag_id, source_drop, domain, type, goal, raw_input, nodes, status, created_at, updated_at, project, entity_refs, links`.

DAG status: `running, complete, failed, needs_human, stalled, blocked`.

### Node
A unit of executable work.

Fields: `id, title, type, status, depends_on, agent, tool_type, tool_action, inputs_required, done_condition, result, result_refs, evidence, retry_count, max_retries, domain, project, entity_refs, parent_dag, priority_score, stale_after_hours, created_from, recurs, do_not_reopen_refs`.

### Result
Output from a human, AI agent, script, or tool.

Fields: `node_id, status, result, evidence, confidence, new_nodes, receipt` (for tool nodes).

### Review (`droplist/node_reviewer.py::review`)
Validation layer. Returns `review_status, mark_node_as, reason, approved_new_nodes`.
`review_status` in `{pass, fail, retry, blocked}`.

### Entity (`droplist/entities.py`)
A long-lived thing drops attach to. Drops resolve to the same entity across days.

Entity types: `animal, project, person, asset`.
Fields: `entity_id, name, type, related_dags, open_nodes, observations, last_observation, next_check, created_at, updated_at`.

### Recurring Node
A node the watcher materializes one-per-day-per-recurrence. Stored in `data/state/recurring_nodes.json`.

### Do-Not-Reopen Lock
A registry of refs that cannot be redesigned. Stored in `data/state/do_not_reopen.json`. Enforced at DAG build time.

---

## §6. Node Statuses

| Status | Meaning |
|---|---|
| `ready` | Can run now. All deps satisfied. |
| `running` | Currently assigned (transient). |
| `waiting` | Depends on unfinished nodes. |
| `blocked` | Missing required input or awaiting human. |
| `review` | Result exists and needs validation. |
| `done` | Completed and validated. |
| `failed` | Attempted and failed. |
| `archived` | No longer active. |

---

## §7. Required System Behavior

The system must always be able to answer:

- What exists?
- What is ready?
- What is blocked?
- What is waiting?
- What is done?
- What evidence proves it?
- What should not be reopened?
- What is the next executable node?

`command_brief.build_brief()` is the canonical answer surface.

---

## §8. First Build Target (shipped: MVP 1-4)

Local-first infrastructure before complex UI.

Required folders under `data/`:

```
packets.jsonl       drops -> packets
mini_ships.jsonl    promoted packets
llm_calls.jsonl     classifier + agent call log
run_log.jsonl       execution memory (every CLI run)
agent_runs.jsonl    agent outputs
reviews.jsonl       reviewer decisions
tool_runs.jsonl     tool receipts (evidence)
dag_events.jsonl    DAG lifecycle events
dags/<id>.json      per-DAG full state
results/            file_writer artifacts (sandboxed)
state/              recurring_nodes.json + do_not_reopen.json
entities/<id>.json  long-lived things
memory_index/       inventory output
```

Required modules: `schema, hashing, storage, classifier, retrieval, completion, engine, dag_builder, dispatcher, agents, toolrouter, node_router, node_reviewer, dag_update, graph_engine, clock, entities, state, watcher, command_brief, daily, review, inventory, llm, cli`.

---

## §9. First Working Flow

Input: a messy text drop.
Output: a packet JSON, a DAG JSON, a list of ready nodes, a node result (real or templated), a review decision, an updated DAG, a state summary.

```
drop --graph "the doe is limping and not eating"
```

does this end-to-end.

---

## §10. Build Rules

- Do not optimize interface before proving state.
- Do not add agents before proving dispatch.
- Do not add tool integrations before proving review.
- Do not add memory before proving graph updates.
- Do not redesign working modules unless tests prove failure.

---

## §11. Done Condition for First Complete Build

The first complete build is done when 5 real drops can move through:

```
drop -> packet -> dag -> dispatch -> result -> review -> update -> summary
```

At least 4 of 5 must produce usable state without manual rescue.

**Shipped at MVP 2. Reinforced at MVP 3 and 4. Currently 5/5 across all gates.**

---

## §12. Acceptance Gates

| Gate | Script | Coverage | Status |
|---|---|---|---|
| MVP 1 packet engine | `test_drops.py` | 20 drops, 7 criteria | 5/5 |
| MVP 2 recursive DAG loop | `test_graph.py` | 5 drops, 6 criteria each | 5/5 |
| MVP 3 tool-connected execution | `test_tools.py` | 3 drops, 6 criteria each | 3/3 |
| MVP 4 persistent operating layer | `test_persist.py` | 7-day clock-driven simulation, 7 checks | 7/7 |
| PKT-005 Atlas seam mapping | `test_atlas_signal.py` | 4 fixture DAGs -> Signal.v1, structural + strict jsonschema | 4/4 |
| PKT-006 live Atlas emission | `test_atlas_emit.py` | stdlib HTTP fixture, positive + negative case | 2/2 |

Before any Execution Packet is closed, *all four* gates must still pass.

---

## §13. Open Questions

First-class artifacts. Execution Packets resolve these by name.

| ID | Question | Current behavior |
|---|---|---|
| OQ-1 | What happens when evidence is insufficient AND retry budget is exhausted? | Node marked `failed`. No recovery path. No re-triggering when world changes. |
| OQ-2 | What happens when two drops produce overlapping DAGs (same entity, same goal)? | Separate graphs, cross-link exists, no merge. |
| OQ-3 | Can a DAG depend on another DAG? | No. Only intra-DAG node deps. |
| OQ-4 | How is a `done` node re-validated when the world changes? | It is not. `done` is terminal. |
| OQ-5 | What is the canonical entity-resolution path beyond hardcoded `_TOKEN_MAP`? | String match against fixed dict; misses unknown names. |
| OQ-6 | How does the LOCK guard distinguish "intentional redesign after validation failure" from "accidental reopen"? | All reopen attempts produce LOCK nodes; no human-override path. |
| OQ-7 | What is the contract for cross-DAG `links`? | One-directional (new -> old). No backlink. No semantics on link type. |
| OQ-8 | Should reviews link to receipts (so "why failed?" doesn't require manual join)? | No link today. Same `node_id`, different files. |
| OQ-9 | Should stale-age be per-node or per-DAG? | Per-DAG today, which is coarse. |
| OQ-10 | ~~What is the Atlas seam, exactly?~~ | **RESOLVED by PKT-005** (2026-06-08). Seam = `POST /api/signals/ingest` on delta-kernel, accepting `Signal.v1`. Mapping defined in §16. Live emission wire is PKT-006. |
| OQ-11 | MVP 1 (engine + router + completion) and MVP 2-4 (dag_builder + graph_engine) are two parallel pipelines. Is that intentional, or should they converge? | Both active. MVP 1 produces a finished packet; MVP 2-4 produces an executing graph. They share `(domain, type)` input but emit different shapes. Surfaced by PKT-001 abort. |
| OQ-12 | The packet's `current_node` / `next_node` (router-DAG vocabulary: `"inventory_metadata"`, `"identify_project"`) is a different concept from the graph's ready-node IDs (`N1, N2`). Any external consumer reading the packet field would get the wrong "where am I" answer. | Field exists, no documented consumer. Decide rename / remove only if Atlas substrate plans to read it. |
| OQ-13 | ~~Windows portability: `dag_builder.py` hardcodes `tool_action="python3 test_drops.py"`.~~ | **RESOLVED by PKT-003** (PKT-002 was incomplete). Fix: invocation-probe (`subprocess.run([cand, "--version"])`) at module load, returns bare command word so allowlist prefix match still applies. |
| OQ-14 | ~~`test_tools.py` code/build drop ends DAG with 0 nodes done despite tool actions firing.~~ | **RESOLVED by PKT-003** (was a symptom of incomplete OQ-13 fix). `shutil.which()` returned a `.BAT` shim path; subprocess can't exec `.BAT` without shell, AND the path failed the allowlist prefix match. Invocation-probe sidesteps both. |
| OQ-15 | ~~`shutil.which()` is the wrong primitive on Windows for "what command should I exec?"~~ | **RESOLVED by PKT-004** (2026-06-08). Audit found no other instances. Latent class-of-risk documented via guardrail comment at `toolrouter._SAFE_SCRIPT_PREFIXES`. |
| OQ-16 | Verification discipline: PKT-002 marked done after three of four gates passed. Strict gate (test_tools 3/3) failed silently because the other tests' criteria were tolerant of script_runner failures. Should `done` require strictest-gate-green, not majority-gate-green? | Bible §14 now requires re-investigation when verification shows partial gate-pass. PKT-002 retroactively superseded by PKT-003. |
| OQ-17 | `Signal.v1.source_layer` enum does not include `"droplist"`. PKT-005 uses `"optogon"` as a placeholder. Should the enum be extended? | Pending. Touches `contracts/schemas/Signal.v1.json` (settled core). Move only when DropList is a real producer Atlas-side cares about distinguishing. |
| OQ-18 | ~~DropList exposes `/api/lattice/viewmodel` at :3071 — but `apps/lattice/index.html:2368` hardcodes `ATLAS_BASE=http://127.0.0.1:3001` and delta-kernel already serves the same route via `lattice-projection.ts` (`server.ts:2003`). Two providers, one consumer pointed at the other.~~ | **RESOLVED by PKT-007** (2026-06-14). Duplicate route + `lattice_viewmodel.py` mapper removed from droplist. delta-kernel keeps the canonical Lattice surface. DropList feeds Lattice indirectly via PKT-006 Signal.v1 emission. Discovered by code-recon verify mode after a /weapon run shipped the duplicate. |
| OQ-19 | Consumer side of the DropList -> Lattice seam is not wired. PKT-006 emits Signal.v1 to delta-kernel's `/api/signals/ingest`, but `services/delta-kernel/src/atlas/lattice-projection.ts` only reads `cognitive-sensor/idea_registry.json`. Signals arrive in delta-kernel's in-memory ring and are dropped on the floor by the viewmodel build. Settled droplist DAGs do not appear in `apps/lattice`. | **RESOLVED by PKT-008** (2026-06-15). Wire shipped: `lattice-projection.ts` extends `LatticeProvenanceSource` with `'droplist'`, projects signals filtered by `payload.data.dag_id` as `LatticeItem`s (dedup by `task_id`, newest `emitted_at` wins), inserted before correction overlay so user corrections still apply. Server injects `listSignals` at `/api/lattice/viewmodel` via prototype-chain wrapper. UI consumer follow-ups (right-click correction gate widening for `drop_*` ids; ctx menu `'droplist'` branch; E2E smoke) queued as PKT-009. |
| OQ-20 | Should claude's chat-side outputs (explanations, widgets, recon snapshots) become substrate, and if so, what's the contract? | Defined by PKT-010 — `AtlasArtifact.v1` is the sibling contract to `Signal.v1`. Sits alongside §16's Signal seam under new §17. PKT-011+ wire the runtime path. |

---

## §14. Workflow

When working in this repo:

1. Read `DOCTRINE.md`.
2. For any change, find the relevant Execution Packet in `PACKETS/`.
3. If no packet exists for the change you want to make, **write the packet first**. Do not start work.
4. **Pre-flight grep.** Before any deletion or rename, `grep -rn` the symbols you plan to touch. Paste the results into the packet's `Pre-flight evidence` section. No scope is final before the grep is run. (Added 2026-06-07 after PKT-001 abort.)
5. Quote the doctrine + Bible §s the packet touches.
6. Treat the packet's `Do not touch` list as a hard fence.
7. Verify the `Done condition` before marking the packet `done`.
8. If the work surfaces a new question, add it to §13 with a new OQ-id.
9. If the work proves the premise was wrong, mark the packet `ABORTED` with a `Why aborted` section. Aborted packets are kept as record. The cost of an aborted packet is zero; the cost of an unaborted wrong assumption is real.

The Bible is the source. The Doctrine is the always-loaded preamble. Execution Packets are the bites.

The MVP ladder is retired. New work is a packet against the Bible, not a new MVP.

---

## §16. Atlas Seam

The wire from DropList into the Atlas substrate. Resolves OQ-10. Defined by PKT-005.

### Endpoint

```
POST  http://<delta-kernel>/api/signals/ingest
  Content-Type: application/json
  Body:        Signal.v1 (see contracts/schemas/Signal.v1.json)
  Response:    202 { ok: true, signal_id }   on success
               400 { ok: false, error, details }   on schema validation failure
```

`delta-kernel` defaults to `127.0.0.1:3001` in Bruke's stack. Atlas-side store is in-memory ring (MAX_SIGNALS=500); signals are act-on-or-log-and-forget.

### Mapping: DropList settled DAG -> Signal.v1

Implemented in `droplist/atlas_signal.py::dag_to_signal()`. Pure function, I/O-free, fully tested by `test_atlas_signal.py` (4 fixtures, strict schema validation when `jsonschema` is installed).

| Signal field | Source |
|---|---|
| `schema_version` | literal `"1.0"` |
| `id` | `f"sig_{uuid4().hex[:12]}"` |
| `emitted_at` | `clock.now_iso()` (test-controllable via `DROPLIST_NOW`) |
| `source_layer` | `"optogon"` (placeholder until OQ-17 extends the enum) |
| `signal_type` | `complete -> completion`, `failed -> error`, `needs_human -> approval_required`, `stalled -> blocked` |
| `priority` | `urgent` if `dag.type in {warning, problem}` OR any node `priority_score >= 80`; `low` if `domain == general`; else `normal` |
| `payload.task_id` | `dag.source_drop` |
| `payload.label` | `dag.goal` (trimmed to 140 chars) |
| `payload.summary` | `"{domain}/{type}: {n_done}/{n_total} done; status={dag.status}"` |
| `payload.data` | `{ dag_id, domain, type, dag_status, nodes[], evidence_refs, entity_refs, links }` |
| `payload.action_required` | `True` iff `signal_type == "approval_required"` |
| `payload.action_options` | list of `{ id: node_id, label: node.title, risk_tier: "low" }` for human-blocked nodes (required by schema when action_required=true) |

### Three layers, decoupled

```
                 minimal payload                  Signal.v1
DropList graph -------------------> n8n flow ----------------------> delta-kernel
graph_engine    (toolrouter         (transforms                       POST /api/signals/ingest
                 _n8n_webhook;       per BIBLE §16)
                 per-node, today)
```

Or, bypass n8n for testing / dev:

```
                Signal.v1
DropList helper ----------------------> delta-kernel
atlas_signal     (when                   POST /api/signals/ingest
.emit_signal()    DROPLIST_DIRECT_SIGNALS_URL set)
```

### Guarantees and non-guarantees

- **One settled-DAG event = one Signal.** Replays produce new `id`s.
- **Pure mapping is idempotent** for a given DAG snapshot (same DAG -> same Signal up to id and emitted_at).
- **No persistence Atlas-side.** Ring buffer. If the consumer is down, signals are lost. PKT-006 should add a retry buffer on the DropList side.
- **No back-channel today.** Atlas doesn't reach into DropList. That's OQ-3 + OQ-4 territory.

### Live wire (shipped by PKT-006)

`graph_engine.run_graph()` calls `_maybe_emit_atlas_signal(dag)` after every settle. Behavior:

- **Env-gated:** emission happens only when `DROPLIST_ATLAS_SIGNALS_URL` is set. Unset = silent no-op (no network, no log noise).
- **Fail-isolated:** any exception during mapping or POST is caught. `run_graph` returns normally regardless of emission outcome.
- **Audited:** every emission attempt appends one record to `dag_events.jsonl`:
  ```json
  {"dag_id": "...", "event": "atlas_signal_emit", "url": "...",
   "signal_id": "sig_...", "ok": true, "error": null}
  ```
  Reconstructable trace of every emission attempt without joining files.

### Open follow-ups

- **OQ-17** extends `Signal.v1.source_layer` enum to include `"droplist"` once Atlas-side cares about distinguishing.
- **Retry buffer.** Failed emissions are logged but not retried. Add a buffered re-emit when the consumer comes back online (deferred — opens a new OQ if needed).
- **n8n flow** itself (`n8n_flows/droplist_to_atlas_signal.json`) is a separate config artifact; pattern documented above, JSON not yet committed.

---

## §17. Artifact Seam

The wire from agents (claude, recon, anatomy-map) into the Atlas substrate. Resolves OQ-20. Defined by PKT-010.

### Endpoint

```
POST  http://<delta-kernel>/api/atlas/artifacts/ingest
  Content-Type: application/json
  Body:        AtlasArtifact.v1 (see contracts/schemas/AtlasArtifact.v1.json)
  Response:    202 { ok: true, artifact_id }   on success
               400 { ok: false, error, details }   on schema validation failure
```

Endpoint is defined by this Bible section; the route is wired in PKT-011.

### How artifacts differ from signals

| | Signal (§16) | Artifact (§17) |
|---|---|---|
| Carries | Behavioral state | Derived knowledge |
| Lifetime | Ephemeral (ring) | Durable (persisted via Storage class as `entity_type='artifact'`) |
| Producer | DropList, optogon, ghost-executor | claude_code primarily; recon scripts; anatomy-map |
| Re-renderable | No | Yes — `payload.widgets[].source` is the source of truth |

The two seams stay separate so Signal.v1 (settled core) doesn't bend to carry payloads it wasn't designed for, and so each seam can evolve independently.

### Three layers, decoupled (same shape as §16)

```
                       AtlasArtifact.v1
claude / /show hook ----------------------> delta-kernel
show_capture.js          POST /api/atlas/artifacts/ingest      (PKT-015 wires the producer; PKT-011 wires the route)
```

### Guarantees and non-guarantees

- **One render = one artifact.** Re-runs produce new `id`s.
- **Pure storage is idempotent** for a given input — same input → same artifact body (modulo `id` and `created_at`).
- **Persistence Atlas-side.** Unlike signals, artifacts are kept indefinitely via the Storage class. Deletion is a future packet.
- **No back-channel today.** Atlas doesn't reach into the producer. (Mirror of §16 same-named constraint.)

---

## §15. What is deliberately deferred

- ~~**Vector retrieval (Chroma/Qdrant).** Interface already returns `{source, snippet, relevance}`; swap is local.~~ **External half wired 2026-06-08 via services/search-stack** (`retrieve_with_external()` in `retrieval.py` + `external_search` tool in `toolrouter.py`, gated by `DROPLIST_EXTERNAL_SEARCH=1`). Internal vector swap (Chroma/Qdrant over the local packets corpus) still deferred — current internal retrieval is still token-overlap, but the {source, snippet, relevance} interface is now production-shaped.
- ~~**Atlas wire.** `n8n_webhook` is the seam. Needs a defined endpoint contract on the Atlas side. See OQ-10.~~ **Contract defined in §16 (PKT-005). Live wire pending in PKT-006.**
- **Mini Ship promotion semantics.** `--ship` + `--ship-from` wired; promotion doctrine needs a Bible §.
- **Inventory deep-read tier.** `deep_read_selected -> cleanup_plan -> ask_before_move_delete` nodes designed; not built.
- **UI surface.** TGT Law (Tree, Graph, Time) must pass before makeup.
- **LangGraph.** Not used. Add only when sub-DAGs genuinely need parallelism / retries / streaming the current dispatcher can't handle.
