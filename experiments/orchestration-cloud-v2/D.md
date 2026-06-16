# Trial D · Hybrid · v2

## Sanity check
- branch: experiment/cloud-orch-D-v2-2026-06-16 (base: claude/main-triage-26f4a5)
- HEAD: 5b96bf0f422abda1ff32fd50f0d1c62f03876312
- services/droplist exists: yes

## Map phase
- delta-scp invoked? no (services/delta-scp/README.md absent on this branch)
- skeleton:
```
services/droplist/
├── BIBLE.md
├── DOCTRINE.md
├── PACKETS/
│   ├── 001_remove_router_orphan.md
│   ├── 002_windows_portable_python.md
│   ├── 003_python_command_actually_invokable.md
│   ├── 004_audit_path_assumes_invocable.md
│   ├── 005_atlas_seam_contract.md        ← Signal.v1 contract definition
│   └── 006_live_atlas_signal_emission.md ← live POST wire PKT-006
├── README.md
├── demo_data/
│   ├── llm_calls.jsonl
│   ├── packets.jsonl
│   └── run_log.jsonl
├── droplist/
│   ├── __init__.py
│   ├── __main__.py
│   ├── agents.py
│   ├── atlas_signal.py   ← Signal.v1 builder + HTTP emitter
│   ├── classifier.py
│   ├── cli.py
│   ├── clock.py
│   ├── command_brief.py
│   ├── completion.py
│   ├── dag_builder.py
│   ├── dag_update.py
│   ├── daily.py
│   ├── dispatcher.py
│   ├── engine.py
│   ├── entities.py
│   ├── graph_engine.py   ← orchestrates run + emit trigger
│   ├── hashing.py
│   ├── inventory.py
│   ├── llm.py
│   ├── node_reviewer.py
│   ├── node_router.py
│   ├── retrieval.py
│   ├── review.py
│   ├── router.py
│   ├── schema.py
│   ├── state.py
│   ├── storage.py
│   ├── toolrouter.py     ← n8n_webhook (separate path, not Signal.v1)
│   └── watcher.py
├── pyproject.toml
├── test_atlas_emit.py    ← PKT-006 acceptance gate
├── test_atlas_signal.py  ← PKT-005 acceptance gate
├── test_drops.py
├── test_graph.py
├── test_persist.py
├── test_retrieval_external.py
└── test_tools.py
```

## Parallel slices
- Slice 1 (emission): 6 verified sites
- Slice 2 (consumption): 1 in-codebase consumer (test mock only); production consumer is out-of-scope delta-kernel
- Slice 3 (schemas): 2 drift findings between contract doc and implementation
- Slice 4 (tests): 2 acceptance test files (PKT-005, PKT-006), 6 total gates

## Verify phase
- Verified: 8
- Dropped: 0

## Emit sites (verified)

| file | line | snippet | confidence |
|---|---|---|---|
| `droplist/atlas_signal.py` | 87 | `def dag_to_signal(dag: dict, source_layer: str = "optogon") -> dict[str, Any]:` | high |
| `droplist/atlas_signal.py` | 100 | `signal_type = _STATUS_TO_SIGNAL_TYPE.get(dag_status, "status")` | high |
| `droplist/atlas_signal.py` | 103 | `label = (dag.get("goal") or "").strip()[:140] or "DropList DAG"` | high |
| `droplist/atlas_signal.py` | 146 | `"emitted_at": clock.now_iso(),` | high |
| `droplist/atlas_signal.py` | 154 | `def emit_signal(signal: dict, url: str, timeout: float = 10.0) -> dict[str, Any]:` | high |
| `droplist/graph_engine.py` | 21 | `def _maybe_emit_atlas_signal(dag: dict) -> None:` — env-gated, fail-safe wrapper | high |
| `droplist/graph_engine.py` | 40 | `sig = atlas_signal.dag_to_signal(dag)` | high |
| `droplist/graph_engine.py` | 203 | `_maybe_emit_atlas_signal(dag)` — sole call site, after DAG settles | high |

## Consume sites (verified)

| file | line | snippet | confidence |
|---|---|---|---|
| `test_atlas_emit.py` | 54-57 | `class _CaptureHandler(BaseHTTPRequestHandler): do_POST` — stdlib mock server capturing Signal.v1 POSTs | high |
| `test_atlas_emit.py` | 115-122 | `emit_events = [e for e in new_events if e.get("event") == "atlas_signal_emit"]` — audit trail assertion | high |

**Note:** There is no production consumer within `services/droplist`. Signal.v1 is a pure outbound contract; the ingest endpoint is `delta-kernel POST /api/signals/ingest` (out of scope per mission rules). Consumption is entirely in test fixtures.

## Drift findings

1. **`source_layer` is hardcoded `"optogon"` — Signal.v1 enum has no `"droplist"` value**
   Evidence: `atlas_signal.py:87` (`source_layer: str = "optogon"` default) vs `atlas_signal.py:92-93` (docstring: "because the Signal.v1 enum does not yet include 'droplist'. See OQ-17 in BIBLE §13.") + `graph_engine.py:40` calls `dag_to_signal(dag)` without overriding `source_layer`, so every live emission carries `"optogon"`. OQ-17 is acknowledged open. Semantically wrong (identity mismatch) but structurally valid against the current enum.

2. **`payload.label` truncation: contract doc says 80 chars; implementation uses 140**
   Evidence: `PACKETS/005_atlas_seam_contract.md:66` (`dag.goal (trimmed to 80 chars)`) vs `atlas_signal.py:103` (`[:140]`). The action_options label also uses `[:140]` (`atlas_signal.py:76`). Tests do not assert on label length, so this drift passes all gates silently. The implementation likely reflects the actual Signal.v1 JSON Schema `maxLength`, but the contract doc was never updated.

3. **Two parallel outbound paths with distinct env vars — potential ops confusion**
   Evidence: `toolrouter.py:87` (`DROPLIST_N8N_URL`) fires per-node tool events via `_n8n_webhook` (not Signal.v1 shaped); `graph_engine.py:28` (`DROPLIST_ATLAS_SIGNALS_URL`) fires settled-DAG Signal.v1. These are architecturally intentional (PKT-005 §"Mechanism: 3 layers"), but the distinction is documented only in PKT-005 and BIBLE §16. If an operator sets only `DROPLIST_N8N_URL`, they get node-level pings but no Signal.v1 Atlas events; if they set only `DROPLIST_ATLAS_SIGNALS_URL`, they get Signal.v1 but no n8n automation. No runtime guard warns when one is set without the other.

## Claims with evidence: 8
## Claims without evidence: 0

## Self assessment
- What was easy: The Signal.v1 flow is well-isolated in `atlas_signal.py` + `graph_engine.py`; PKT-005 and PKT-006 packets provided clear contract documentation to cross-check against.
- What was hard: Verifying absence of production consumers within scope (needed to confirm nothing else imports `atlas_signal`). The dual env-var architecture (N8N vs Atlas) required careful distinction to avoid conflating the two paths.
- What might be missed: If `cli.py` has any direct emit path (checked: only `--ship` flag adds a Mini Ship packet, not Signal.v1). The `watcher.py` was not read in detail — if it wraps `run_graph()` it would also trigger Signal.v1 via the same call site, but that wouldn't be a new emit site. No calls to `atlas_signal` outside `graph_engine.py` were found.
- Confidence: high

## Tool calls (approximate): 14
## Wall-clock: ~6 minutes
