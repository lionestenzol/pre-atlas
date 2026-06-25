# Trial D — Hybrid (delta-scp + code-recon) — Signal.v1 in `services/droplist`

**Trial:** D · Hybrid · Manual skill trial
**Working dir:** `C:\Users\bruke\Pre Atlas`
**Scope:** `services/droplist` only (no cross-service traversal)
**Date:** 2026-06-16

---

## Skill invocation log

| Phase | Skill | Args (verbatim) | Marker printed | Result |
|---|---|---|---|---|
| 1 | `delta-scp` | `services/droplist` | `[SKILL INVOKED: delta-scp]` | OK — 64 files compressed |
| 3a | `code-recon` | `verify: Signal.v1 emission only occurs from graph_engine.run_graph() -> _maybe_emit_atlas_signal() -> atlas_signal.emit_signal(), gated by env DROPLIST_ATLAS_SIGNALS_URL, fail-soft on all errors. No alternate emission path exists in services/droplist.` | `[SKILL INVOKED: code-recon]` | OK — verified |
| 3b | `code-recon` | `verify: droplist has zero in-process Signal.v1 consumers — service.py and CLI commands never read a Signal.v1 payload, no HTTP route ingests signals, no test reads back an emitted signal as input.` | `[SKILL INVOKED: code-recon]` | OK — verified |
| 3c | `code-recon` | `verify: payload.data emits 'links' field at atlas_signal.py:124 but PKT-005 contract table (lines 51-70) lists evidence_refs + entity_refs and omits links — minor documentation drift, not a schema violation since Signal.v1.payload.data is additionalProperties-permissive.` | `[SKILL INVOKED: code-recon]` | OK — verified |
| 3d | `code-recon` | `verify: test_atlas_signal.structural_check asserts only payload.label + payload.summary; payload.task_id and all 8 payload.data sub-fields (dag_id, domain, type, dag_status, nodes, evidence_refs, entity_refs, links) have zero presence/type assertions in any droplist test. test_atlas_emit's positive case delegates to the same structural_check and skips strict jsonschema validation when the library is absent.` | `[SKILL INVOKED: code-recon]` | OK — verified |

No skill errored. Five total skill invocations (1× delta-scp, 4× code-recon).

---

## Phase 1 — delta-scp output

- **Files scanned:** 64 (0 skipped)
- **Raw tokens:** 83,161
- **Compressed tokens:** 4,158
- **Token yield:** 79,003 saved (ratio 0.05 — 95% compression)
- **Languages:** python (38), markdown (19), json (6), toml (1)
- **Output file:** [D-droplist-scp.json](D-droplist-scp.json)

The skeleton surfaced 5 load-bearing Signal.v1 anchors before any slice ran:
1. `droplist/atlas_signal.py` — `dag_to_signal:87`, `emit_signal:154`
2. `droplist/graph_engine.py` — `_maybe_emit_atlas_signal:21`, `run_graph:126`
3. `droplist/server.py` — read-only API (no emit/ingest routes)
4. `test_atlas_signal.py` — `structural_check:131`, `strict_check:172`
5. `test_atlas_emit.py` — `case_positive_emits_signal:79`, `case_negative_no_env_no_emit:132`

That scope-list drove the 4 slice prompts; without it the slices would have re-discovered the same files via grep, burning context.

---

## Phase 2 — parallel slice findings

| Slice | Findings | Top claim |
|---|---:|---|
| 1 · Emission paths | 8 citations | Emission only via `graph_engine.run_graph() → _maybe_emit_atlas_signal:21 → atlas_signal.emit_signal:154`, gated by `DROPLIST_ATLAS_SIGNALS_URL`, fail-soft. |
| 2 · Consumption paths | 5 citations | Zero in-process consumers — `allow_methods=["GET"]`, no @app.post/put/patch, no signal-deserializer code. |
| 3 · Schemas / contracts | 13 citations | `payload.data.links` emitted at atlas_signal.py:124 but absent from PKT-005 contract mapping table — documentation drift. |
| 4 · Tests | 10 citations | structural_check enforces only `label`+`summary` on payload; 8 `payload.data.*` sub-fields + `payload.task_id` untested. |

Findings total: **36 evidence citations** across the 4 slices.

---

## Phase 3 — verify results (verdict table)

| # | Claim | Verdict | Evidence angles |
|---|---|---|---|
| 1 | Emission only via run_graph → _maybe_emit → emit_signal, env-gated, fail-soft | ✅ verified | (a) `rg "emit_signal"` → 1 prod call site at graph_engine.py:42; (b) `rg "_maybe_emit_atlas_signal"` → 1 def (graph_engine.py:21) + 1 call site (graph_engine.py:203); (c) `rg "DROPLIST_ATLAS_SIGNALS_URL"` → gate at graph_engine.py:28; (d) read graph_engine.py:39-48 → `try: ... except Exception as e: ... storage.append(DAG_EVENTS, record)` — fail-soft confirmed |
| 2 | Zero Signal.v1 consumers inside droplist | ✅ verified | (a) `rg "@app\.(post|put|patch|delete)"` → 0 matches; (b) `rg "signals/ingest\|ingest_signal\|consume_signal"` → only emit-side + doc mentions; (c) server.py:32 `allow_methods=["GET"]` literal; (d) server.py:11-25 docstring explicitly states "DropList feeds Lattice indirectly via PKT-006's Signal.v1 emission to delta-kernel" |
| 3 | `payload.data.links` is drift vs PKT-005 contract table | ✅ verified | (a) atlas_signal.py:124 emits `"links": list(dag.get("links") or [])`; (b) PACKETS/005:68 mapping table lists `{dag_id, domain, type, dag_status, nodes, evidence_refs, entity_refs}` — `links` omitted; (c) Signal.v1.json:40 declares `"data": {"type": "object"}` with no `additionalProperties:false` → schema permissive, drift is documentation-only |
| 4 | 8 `payload.data.*` sub-fields + `payload.task_id` are untested | ✅ verified | (a) read test_atlas_signal.py:131-165 `structural_check` → checks REQUIRED_TOP + REQUIRED_PAYLOAD (`label`,`summary`) + action_required invariant; nothing else; (b) read test_atlas_emit.py:111 → delegates to same structural_check; (c) `rg "dag_id\|evidence_refs\|entity_refs\|dag_status\|task_id"` in test_*.py — all hits are fixture INPUT dicts (test_atlas_signal.py:53-115) or unrelated tests (test_server, test_persist, test_tools), no `sig["payload"]["data"][...]` assertions; (d) strict_check at test_atlas_signal.py:172-193 returns `"SKIPPED"` if jsonschema absent — and Signal.v1.json doesn't constrain `data` sub-fields anyway |

**All 4 claims survived ≥2-angle verification. Zero ⚠️ partials, zero ❌ busted.**

---

## Emit table

| Site | Call | Trigger | Gate | Failure mode |
|---|---|---|---|---|
| `droplist/graph_engine.py:203` | `_maybe_emit_atlas_signal(dag)` | After `_finalize(dag)` in `run_graph` | env `DROPLIST_ATLAS_SIGNALS_URL` (graph_engine.py:28) | Returns silently |
| `droplist/graph_engine.py:42` | `atlas_signal.emit_signal(sig, url)` | Inside `_maybe_emit_atlas_signal` | (inherits parent gate) | try/except Exception → record error in `data/dag_events.jsonl` (graph_engine.py:46-48) |
| `droplist/atlas_signal.py:154` | `urllib POST` | Called by graph_engine.py:42 | (none — caller gates) | URLError/OSError → return `{"ok": False, "error": ...}` (atlas_signal.py:155-176) |
| `droplist/atlas_signal.py:40` | `dag_to_signal(dag)` (pure) | Called by graph_engine.py:40 | (none — pure) | (none — pure function) |

**One production emission chain. No CLI direct-emit. No server emit endpoint.**

---

## Consume table

| Site | Inbound? | Notes |
|---|---|---|
| `droplist/server.py:27-34` | No | FastAPI with `allow_methods=["GET"]` only |
| `droplist/server.py` GET routes | No | `/api/now`, `/api/dag/{id}`, `/api/dags`, `/api/packets`, `/api/state`, `/api/brief`, `/api/entities` — all read DropList state, none accept Signal.v1 |
| `droplist/cli.py` cmd_* | No | All commands read DropList state files or invoke graph_engine; none ingest Signal.v1 |
| `test_atlas_emit.py:47-72` | No | Test-only HTTPServer that *captures* emitted POSTs to assert on — not a runtime consumer |

**Zero consumers inside droplist.** Lattice consumption happens delta-kernel-side at `services/delta-kernel/src/api/server.ts:1803` per PACKETS/008:40 — outside this scope.

---

## Drift findings

| # | Severity | Drift | Evidence |
|---|---|---|---|
| D1 | Documentation (low) | `payload.data.links` emitted by code but not listed in PKT-005:68 contract mapping table | atlas_signal.py:124 vs PACKETS/005_atlas_seam_contract.md:68 |
| D2 | Doctrine (open, tracked) | `source_layer="optogon"` is a placeholder; `Signal.v1.source_layer` enum (Signal.v1.json:23) doesn't include `"droplist"` even though droplist *is* the producer | atlas_signal.py:147 default + PACKETS/005:62 + BIBLE.md:241 OQ-17 (already open, not new finding) |
| D3 | Test coverage (medium) | `payload.task_id` + 8 `payload.data.*` sub-fields have zero presence/type/value assertions in the test suite. Strict jsonschema validation is a no-op for these because Signal.v1.json declares `data` as bare `{"type":"object"}`. | test_atlas_signal.py:131-165 + Signal.v1.json:40 |
| D4 | Defensive code (low) | atlas_signal.py:134-139 synthesizes a fallback action_option `{id:"DAG", label:..., risk_tier:"low"}` when `_collect_action_options` returns empty for `signal_type="approval_required"`. Comment says "this should never happen in practice" — but if it ever does, the emitted Signal will pass schema validation yet carry a synthetic option that no UI knows how to surface. | atlas_signal.py:128-141 |

---

## Self-assessment

**Did combining scp + recon find anything neither alone would catch?** YES — three concrete cases:

1. **delta-scp gave the parallel slices a pre-scoped target list (5 anchors) in 4,158 tokens.** Without it, each of the 4 slice agents would have started cold with `rg`/`fd`, spending ~20% of their context on orientation before finding the same 5 files. The scp skeleton made the slice prompts surgical instead of exploratory. Slice-1 alone found the full emission chain in 8 citations because it knew exactly where to look.

2. **code-recon's 2-angle proof-of-absence rule caught a subtle would-be confabulation in Slice 4.** The Phase-2 agent claimed "task_id is untested." Verification (Phase 3d, angle c) found that the *strings* `task_id`, `dag_id`, etc. DO appear in test files — but in fixture INPUT dicts (test_atlas_signal.py:53-115), not in `sig["payload"][...]` assertion code. A single-grep verification would have produced a busted claim ("strings appear, therefore tested"); the read-the-file second angle confirmed they're inputs, not assertions. Code-recon's enforcement structure made me check.

3. **The drift in D1 (`payload.data.links`) is invisible to either tool alone.** delta-scp shows file structure but not field-level emission. code-recon would have found it by grepping `"links"`, but only if pointed at it; the parallel emission-vs-contract comparison in Phase 2 Slice 3 surfaced it. Then Phase 3 verification on Signal.v1.json:40 (`"data": {"type": "object"}` with no `additionalProperties` constraint) classified it as documentation-drift rather than a schema violation. That nuance — *drift exists AND is permissive under the formal schema* — required all three artifacts (code, contract doc, JSON Schema).

**Combining scp + recon found things neither alone would catch.**

Cost: ~5 skill invocations + 4 parallel Explore subagents + ~12 grep/read tool calls in the main loop. Token spend dominated by the 4 parallel slice agents, not by the skills themselves.

---

## Counts summary

- delta-scp: 1 invocation, 64 files mapped, 95% compression
- Parallel slices: 4 agents, 36 total citations
- code-recon verifications: 4 invocations, **4/4 ✅ verified**, 0 ⚠️, 0 ❌
- Drift findings: 4 (1 doc, 1 doctrine-tracked, 1 test-coverage, 1 defensive)
- Emit sites: 1 production chain
- Consume sites: 0 inside scope

MANUAL TRIAL D COMPLETE
