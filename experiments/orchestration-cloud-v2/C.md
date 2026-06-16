# Trial C · Sweep-first · v2

## Sanity check
- branch: experiment/cloud-orch-C-v2-2026-06-16 (based on claude/main-triage-26f4a5)
- HEAD: 5b96bf0f422abda1ff32fd50f0d1c62f03876312
- services/droplist exists: yes

---

## Sweep phase

### Inv 1 — Emission sites (emit/publish/send/post patterns)
Raw hits across services/droplist:

| # | file | line | pattern |
|---|---|---|---|
| 1 | droplist/graph_engine.py | 203 | `_maybe_emit_atlas_signal(dag)` call at settle point |
| 2 | droplist/graph_engine.py | 21–48 | `_maybe_emit_atlas_signal()` helper definition |
| 3 | droplist/graph_engine.py | 40 | `sig = atlas_signal.dag_to_signal(dag)` |
| 4 | droplist/graph_engine.py | 42 | `resp = atlas_signal.emit_signal(sig, url)` |
| 5 | droplist/atlas_signal.py | 154–176 | `emit_signal()` function — stdlib urllib POST |
| 6 | droplist/toolrouter.py | 82–106 | `_n8n_webhook()` — POSTs raw payload to `DROPLIST_N8N_URL` |

- Inv 1 hits: 6

### Inv 2 — Consumption sites (read/receive/handle/subscribe patterns)
Raw hits across services/droplist:

| # | file | line | pattern |
|---|---|---|---|
| 1 | test_atlas_emit.py | 47–61 | `_CaptureHandler.do_POST()` — mock consumer in test |
| 2 | test_atlas_emit.py | 53–57 | `received.append(...)` — stores captured Signal.v1 |
| 3 | BIBLE.md | 274 | `POST /api/signals/ingest` (external delta-kernel consumer, cited in docs) |
| 4 | PACKETS/005_atlas_seam_contract.md | 34 | `POST /api/signals/ingest -> 202 { ok, signal_id }` (same external endpoint) |

Note: No consume-side code within droplist for Signal.v1. Real consumer is delta-kernel (out of scope). Only test-internal mock.

- Inv 2 hits: 4

### Inv 3 — Schema/type defs for Signal.v1
Raw hits:

| # | file | line | pattern |
|---|---|---|---|
| 1 | droplist/atlas_signal.py | 28–36 | `_STATUS_TO_SIGNAL_TYPE` dict — dag status → signal_type closed enum |
| 2 | droplist/atlas_signal.py | 39–54 | `_derive_priority()` — priority closed enum logic |
| 3 | droplist/atlas_signal.py | 143–151 | Signal.v1 dict construction (schema_version, id, emitted_at, source_layer, signal_type, priority, payload) |
| 4 | test_atlas_signal.py | 27–33 | VALID_SOURCE_LAYERS, VALID_SIGNAL_TYPES, VALID_PRIORITIES, REQUIRED_TOP, REQUIRED_PAYLOAD |
| 5 | PACKETS/005_atlas_seam_contract.md | 38–42 | Field list from contracts/schemas/Signal.v1.json |
| 6 | BIBLE.md | 285–298 | Full field mapping table in §16 |

- Inv 3 hits: 6

### Inv 4 — Tests exercising Signal flow
Raw hits:

| # | file | coverage |
|---|---|---|
| 1 | test_atlas_signal.py | PKT-005 gate: 4 fixture DAGs → dag_to_signal → structural_check + optional jsonschema strict validation |
| 2 | test_atlas_emit.py | PKT-006 gate: positive case (env set → one POST + audit event) + negative case (env unset → no POST, no event) |

- Inv 4 hits: 2 test files / 6 test cases

**Total before verify: 18**

---

## Verify phase

Each finding below was re-verified from 2+ independent angles (code read + doc cross-check, or two code reads).

### Emit sites

**E1: `_maybe_emit_atlas_signal(dag)` is the sole Signal.v1 emit point**
- Angle 1: `grep emit_signal services/droplist` → only `graph_engine.py:42` calls it
- Angle 2: `grep atlas_signal services/droplist` → only `graph_engine.py` imports and calls it for emission; `test_atlas_signal.py` calls `dag_to_signal` only (pure fn, no I/O)
- VERIFIED ✓

**E2: Call is at settle point — line 203 of run_graph()**
- Angle 1: Read `graph_engine.py:195–204` — `_maybe_emit_atlas_signal(dag)` is the last non-return line after `_finalize(dag)` / `state_summary(dag)` / `storage.save_dag(dag)` / `storage.append(...settled...)`
- Angle 2: PKT-006 doc confirms "One new line at the settle point: `_maybe_emit_atlas_signal(dag)`"
- VERIFIED ✓

**E3: `_n8n_webhook` is a distinct path, not Signal.v1-shaped**
- Angle 1: `toolrouter.py:84–86` — sends `{"node_id", "dag_id", "workflow", "summary", "drop_id"}` (minimal payload, no schema_version/signal_type/etc.)
- Angle 2: BIBLE.md §16 diagram explicitly shows n8n as a separate "transform" layer between DropList and delta-kernel; it is per-node not per-DAG-settle
- VERIFIED ✓

### Schema/type defs

**S1: Signal.v1 required top-level fields**
- Angle 1: `test_atlas_signal.py:31–32` — `REQUIRED_TOP = ["schema_version", "id", "emitted_at", "source_layer", "signal_type", "priority", "payload"]`
- Angle 2: `PKT-005:38` — "required: id, emitted_at, source_layer, signal_type, priority, payload, schema_version"
- VERIFIED ✓

**S2: source_layer default is "optogon" (not "droplist")**
- Angle 1: `atlas_signal.py:87` — `def dag_to_signal(dag: dict, source_layer: str = "optogon")`
- Angle 2: `BIBLE.md §16:290` — "source_layer | "optogon" (placeholder until OQ-17 extends the enum)"
- VERIFIED ✓

**S3: Status-to-signal_type mapping is complete**
- Angle 1: `atlas_signal.py:28–36` — complete/failed/needs_human/stalled → completion/error/approval_required/blocked
- Angle 2: `BIBLE.md §16:291` — matches the same 4-way mapping; test_atlas_signal.py FIXTURES assert each
- VERIFIED ✓

### Consume side

**C1: No droplist-internal Signal.v1 consumer; only test mock**
- Angle 1: `grep "subscribe|on_signal|listen|signal.*read" services/droplist` → zero matches in Python source
- Angle 2: BIBLE.md §16 "No back-channel today. Atlas doesn't reach into DropList." + PKT-005 "DropList -> Atlas direction only for v1."
- VERIFIED ✓

### Drift findings

**D1: `DROPLIST_DIRECT_SIGNALS_URL` in docs vs `DROPLIST_ATLAS_SIGNALS_URL` in code**
- Angle 1: `grep DROPLIST_DIRECT_SIGNALS_URL` → only `BIBLE.md:316` and `PKT-005:87` (architecture diagrams); ZERO Python files
- Angle 2: `grep DROPLIST_ATLAS_SIGNALS_URL` → `graph_engine.py:22,28`, `test_atlas_emit.py:4,85,126,138`, `BIBLE.md:330` (live-wire section), `PKT-006:42`
- DRIFT VERIFIED ✓ — The "bypass n8n" diagram in BIBLE §16 and PKT-005 plan doc show `DROPLIST_DIRECT_SIGNALS_URL`, but the actual PKT-006 implementation chose `DROPLIST_ATLAS_SIGNALS_URL`. The stale label exists only in those two diagram blocks; the rest of BIBLE §16 correctly uses `DROPLIST_ATLAS_SIGNALS_URL`.

**D2: label field truncation — PKT-005 says 80 chars, code + BIBLE say 140**
- Angle 1: `atlas_signal.py:103` — `label = (dag.get("goal") or "").strip()[:140] or "DropList DAG"`
- Angle 2: `PKT-005:66` — "payload.label | dag.goal (trimmed to 80 chars)" vs `BIBLE.md §16:295` — "dag.goal (trimmed to 140 chars)"
- DRIFT VERIFIED ✓ — PKT-005 was a planning doc; implementation chose 140. BIBLE and code agree (140). PKT-005 was never updated.

### Items dropped after Phase 2

- Demo data JSONL files (`demo_data/packets.jsonl`, `demo_data/run_log.jsonl`) appeared in grep as emit/post keyword hits — these are static sample data, not live code. Dropped as false positives.
- `retrieval.py:89` (`method="POST"`) appeared in Inv 1 sweep — POSTs to search stack for retrieval, unrelated to Signal.v1. Dropped.
- `test_retrieval_external.py` appeared in Inv 2 sweep — tests search stack, not Signal. Dropped.

- Verified: 10
- Unverified (dropped): 0
- Refuted (dropped): 3 (demo JSONL, retrieval POST, retrieval external test)

---

## Emit sites (verified)

| file | line | snippet | confidence |
|---|---|---|---|
| droplist/graph_engine.py | 203 | `_maybe_emit_atlas_signal(dag)` — called after DAG settles | high |
| droplist/graph_engine.py | 21–48 | `def _maybe_emit_atlas_signal(dag)` — env-gated, fail-isolated helper | high |
| droplist/graph_engine.py | 40 | `sig = atlas_signal.dag_to_signal(dag)` — pure mapping call | high |
| droplist/graph_engine.py | 42 | `resp = atlas_signal.emit_signal(sig, url)` — stdlib urllib POST | high |
| droplist/atlas_signal.py | 154–176 | `def emit_signal(signal, url, timeout=10.0)` — urllib Request, method="POST" | high |

Secondary (not Signal.v1, kept for context):

| file | line | snippet | confidence |
|---|---|---|---|
| droplist/toolrouter.py | 82–106 | `def _n8n_webhook(node, dag)` — minimal payload POST to `DROPLIST_N8N_URL`, per-node not per-DAG-settle | high (distinct path) |

---

## Consume sites (verified)

Within `services/droplist`, Signal.v1 has no runtime consumer — the signal is sent outbound to `delta-kernel`. The only in-scope consumer is the test mock server.

| file | line | snippet | confidence |
|---|---|---|---|
| test_atlas_emit.py | 47–61 | `class _CaptureHandler(BaseHTTPRequestHandler)` + `do_POST()` — mock HTTP server captures Signal.v1 POSTs in PKT-006 test | high (test only) |

External consumer (out of scope, cited for completeness): `services/delta-kernel/src/api/server.ts:1803` — `POST /api/signals/ingest → 202 { ok, signal_id }`.

---

## Drift findings

1. **Env var name stale in two diagram blocks**
   Evidence: `BIBLE.md:316` and `PACKETS/005_atlas_seam_contract.md:87` both show `DROPLIST_DIRECT_SIGNALS_URL` in the "bypass n8n / direct emit" architecture diagram. The actual implementation (PKT-006) used `DROPLIST_ATLAS_SIGNALS_URL` throughout: `graph_engine.py:28`, `test_atlas_emit.py:85`, `BIBLE.md:330`. `DROPLIST_DIRECT_SIGNALS_URL` appears in zero Python files.
   Severity: documentation only — the code is self-consistent; only the old planning diagrams are stale.

2. **label truncation: 80 chars in PKT-005, 140 chars in code + BIBLE §16**
   Evidence: `PACKETS/005_atlas_seam_contract.md:66` says "trimmed to 80 chars"; `droplist/atlas_signal.py:103` does `[:140]`; `BIBLE.md:295` says "trimmed to 140 chars". PKT-005 was a planning doc and was not updated after implementation chose 140.
   Severity: documentation only — code and BIBLE agree; PKT-005 is the stale artifact.

---

## Claims with evidence: 10
## Claims without evidence: 0

---

## Self assessment

- **What was easy:** The signal flow is cleanly separated into one module (`atlas_signal.py`) and one hook point (`graph_engine.py:203`). Grep hits converged fast. The PKT-005/PKT-006 packet trail made the design intent vs implementation easy to cross-reference.

- **What was hard:** Distinguishing the `_n8n_webhook` path (per-node, minimal payload, predates Signal.v1) from the `_maybe_emit_atlas_signal` path (per-DAG-settle, Signal.v1 shaped). Both are "emit" in the generic sense but serve different purposes. Also required careful reading to catch the env var name drift — `DROPLIST_DIRECT_SIGNALS_URL` is plausible-sounding and appears in authoritative-looking BIBLE text.

- **What might be missed:** If there are any call sites in `droplist/__main__.py` or `droplist/cli.py` that call `run_graph` from alternate entry points, those would trigger the same `_maybe_emit_atlas_signal` path — I confirmed `run_graph` is the only emit path but did not trace all CLI entry points exhaustively.

- **Confidence:** high

---

## Tool calls (approximate): 14
## Wall-clock: ~8 minutes
