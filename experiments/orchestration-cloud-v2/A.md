# Trial A · Map-first · v2

## Sanity check
- branch: experiment/cloud-orch-A-v2-2026-06-16
- HEAD: 5b96bf0f422abda1ff32fd50f0d1c62f03876312 (base: claude/main-triage-26f4a5)
- services/droplist exists: yes

## Map phase
- delta-scp invoked? no — `services/delta-scp/` directory exists but is empty (no README, no source files); uninvocable in <1 min, fell back immediately to Glob+Grep.

### Skeleton output

```
services/droplist/
├── BIBLE.md
├── DOCTRINE.md
├── PACKETS/
│   ├── 001_remove_router_orphan.md
│   ├── 002_windows_portable_python.md
│   ├── 003_python_command_actually_invokable.md
│   ├── 004_audit_path_assumes_invocable.md
│   ├── 005_atlas_seam_contract.md         ← Signal.v1 contract definition
│   └── 006_live_atlas_signal_emission.md  ← live-wire PKT
├── README.md
├── demo_data/
│   ├── llm_calls.jsonl
│   ├── packets.jsonl
│   └── run_log.jsonl
├── droplist/                              ← Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── agents.py                          run_agent, _heuristic, _parent_results
│   ├── atlas_signal.py                    ★ dag_to_signal, emit_signal  [EMIT core]
│   ├── classifier.py                      heuristic_classify, classify
│   ├── cli.py                             cmd_drop, cmd_graph, main, …
│   ├── clock.py                           now_iso, today, parse
│   ├── command_brief.py                   build_brief
│   ├── completion.py                      complete
│   ├── dag_builder.py                     build_dag, validate_dag
│   ├── dag_update.py                      apply_review
│   ├── daily.py                           build_brief
│   ├── dispatcher.py                      get_ready_nodes, get_node
│   ├── engine.py                          process_drop, ship_from
│   ├── entities.py                        resolve_from_packet, attach_dag
│   ├── graph_engine.py                    ★ _maybe_emit_atlas_signal, run_graph  [EMIT trigger]
│   ├── hashing.py                         normalize, input_hash, ClassificationCache
│   ├── inventory.py                       scan, run_inventory
│   ├── llm.py                             call_json, log_call
│   ├── node_reviewer.py                   review
│   ├── node_router.py                     classify, execute
│   ├── retrieval.py                       retrieve, retrieve_external
│   ├── review.py                          build_review
│   ├── router.py                          select_workflow, nodes_for
│   ├── schema.py                          WorkPacket, MiniShipPacket
│   ├── state.py                           add_recurring, due_recurring, lock_ref
│   ├── storage.py                         append, save_dag, load_dag, log_run
│   ├── toolrouter.py                      run_tool, _n8n_webhook, _calendar, …
│   └── watcher.py                         tick
├── test_atlas_emit.py                     ★ PKT-006 acceptance (live HTTP server)
├── test_atlas_signal.py                   ★ PKT-005 acceptance (structural check)
├── test_drops.py
├── test_graph.py
├── test_persist.py
├── test_retrieval_external.py
└── test_tools.py
```

Files marked ★ are directly involved in Signal.v1 emit/validate.

---

## Emit sites

| file | line | snippet | confidence |
|---|---|---|---|
| `droplist/atlas_signal.py` | 87 | `def dag_to_signal(dag: dict, source_layer: str = "optogon") -> dict[str, Any]:` | high |
| `droplist/atlas_signal.py` | 143–151 | `return {"schema_version": "1.0", "id": "sig_" + uuid.uuid4().hex[:12], "emitted_at": clock.now_iso(), "source_layer": source_layer, "signal_type": signal_type, "priority": priority, "payload": payload}` | high |
| `droplist/atlas_signal.py` | 154 | `def emit_signal(signal: dict, url: str, timeout: float = 10.0) -> dict[str, Any]:` | high |
| `droplist/atlas_signal.py` | 162–169 | `body = json.dumps(signal).encode("utf-8"); req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")` | high |
| `droplist/graph_engine.py` | 40 | `sig = atlas_signal.dag_to_signal(dag)` | high |
| `droplist/graph_engine.py` | 42 | `resp = atlas_signal.emit_signal(sig, url)` | high |
| `droplist/graph_engine.py` | 203 | `_maybe_emit_atlas_signal(dag)` (called after DAG settles in `run_graph()`) | high |

**Gating condition** (graph_engine.py:28): emission only occurs when `os.environ.get("DROPLIST_ATLAS_SIGNALS_URL")` is set. With it unset, `_maybe_emit_atlas_signal` returns immediately — zero POSTs.

---

## Consume sites

| file | line | snippet | confidence |
|---|---|---|---|
| `test_atlas_signal.py` | 206 | `sig = atlas_signal.dag_to_signal(dag)` — test harness calls the emitter to validate shape | high (test-only) |
| `test_atlas_emit.py` | 106 | `sig = json.loads(post["body_raw"])` — captures POSTed Signal.v1 from the stub HTTP server | high (test-only) |
| `test_atlas_emit.py` | 111 | `struct_errs = structural_check(sig)` — validates received signal against Signal.v1 closed sets | high (test-only) |

**Key finding:** There are NO production Signal.v1 consume sites within `services/droplist`. Droplist is the **emitter only**. Consumption happens downstream in `delta-kernel` (out of scope per mission rules). The test files validate emit shape but are not production consumers.

---

## Drift findings

### 1. `payload.label` truncation: doc says 80 chars, code uses 140
- **PKT-005 doc** (`PACKETS/005_atlas_seam_contract.md:67`): `payload.label | dag.goal (trimmed to 80 chars)`
- **Implementation** (`droplist/atlas_signal.py:103`): `label = (dag.get("goal") or "").strip()[:140] or "DropList DAG"`
- The contract document and the live code disagree on max label length. The schema file is not checked within droplist (Signal.v1.json is in `contracts/schemas/` outside this service), so whether 140 exceeds the schema's `maxLength` is unverifiable from within droplist scope alone.
- **Confidence:** high (two lines, both read directly)

### 2. `source_layer` enum gap: `"droplist"` does not exist in Signal.v1
- **Implementation** (`droplist/atlas_signal.py:87`, default arg; `atlas_signal.py:143`): hardcoded `"optogon"` placeholder.
- **Test validator** (`test_atlas_signal.py:27`): `VALID_SOURCE_LAYERS = {"site_pull", "optogon", "atlas", "ghost_executor", "claude_code"}` — `"droplist"` absent.
- This is an **acknowledged placeholder** (OQ-17 in BIBLE §13 / PKT-005). Not a silent bug, but it means all Signals emitted by DropList identify as "optogon" at the Atlas end — a semantic misattribution until the enum is extended.
- **Confidence:** high

### 3. `_n8n_webhook` (toolrouter.py) is a parallel outbound path, not Signal.v1-shaped
- `toolrouter._n8n_webhook` (toolrouter.py:82) POSTs a **minimal non-Signal.v1 payload** (`{node_id, dag_id, workflow, summary, drop_id}`) to `DROPLIST_N8N_URL`.
- PKT-005 described this as "Layer 2" (n8n transforms minimal payload → Signal.v1 en route to delta-kernel). The n8n config is an **external artifact** not committed in this repo.
- Risk: if `DROPLIST_N8N_URL` is pointed at the same `POST /api/signals/ingest` endpoint that expects Signal.v1, the delta-kernel's AJV validation will reject the minimal payload.
- **Confidence:** high (code path confirmed; schema mismatch is an inference from the shape difference)

---

## Claims with evidence: 10
## Claims without evidence: 0

---

## Self assessment

- **What was easy:** The Signal.v1 surface in droplist is compact and well-bounded. `atlas_signal.py` is the sole definition module; `graph_engine.py` is the sole production call site. Both were identifiable in one read pass.
- **What was hard:** Distinguishing "no consume sites" from "missed consume sites" — confirmed by exhaustive grep for `Signal`, `atlas_signal`, `emit_signal`, `dag_to_signal`, and `ATLAS_SIGNALS_URL` across all `.py` files. No additional hits beyond the 7 files found.
- **What might be missed:** (a) If `watcher.py` or `daily.py` calls `graph_engine.run_graph()` transitively, they're indirect emit triggers — checked the `watcher.tick()` call chain; it calls `dag_builder.build_dag()` and `storage.save_dag()` but does NOT call `run_graph()`, so no transitive emit. (b) The n8n flow JSON config (the "Layer 2" transform) is not in the repo; its Signal.v1 shape conformance cannot be verified here.
- **Confidence:** high

---

## Tool calls made (approximate): 12
## Wall-clock time: ~8 minutes
