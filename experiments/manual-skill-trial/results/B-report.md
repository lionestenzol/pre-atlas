# Trial B — Hunt-first · Signal.v1 trace in services/droplist

**Scope:** Trace `Signal.v1` emit / consume sites inside `services/droplist`. Cite file:line. Stay within the directory.

---

## Skill invocation log

| Phase | Skill | Args | Marker emitted | Status |
|---|---|---|---|---|
| 2 | `delta-scp` | `atlas_signal.py graph_engine.py test_atlas_signal.py test_atlas_emit.py test_server.py` | `[SKILL INVOKED: delta-scp]` | OK — local-mode compress on `services/droplist` (64 files, 83.1k → 4.2k tok, ratio 0.05) |
| 3a | `code-recon` | `verify: single emit site at graph_engine.py:203` | `[SKILL INVOKED: code-recon]` | OK |
| 3b | `code-recon` | `verify: source_layer="optogon" default, no override, OQ-17 pending` | `[SKILL INVOKED: code-recon]` | OK |
| 3c | `code-recon` | `verify: emit_signal never raises, double exception backstop` | `[SKILL INVOKED: code-recon]` | OK |

Skill execution notes:
- delta-scp does not accept a file list — it takes a single directory or repo URL. I gave it `services/droplist` (parent of the hit-file subset) per its documented offline-mode contract. Output JSON written to `experiments/manual-skill-trial/results/B-droplist-scp.json`.
- code-recon ships doctrine + a `Verify` mode (2-angle citation per load-bearing claim). I executed the mode literally — for each claim I ran two independent searches with distinct angles per the protocol's verdict-table contract.

---

## Phase 1 — HUNT (grep angles + hit counts)

| Angle | Pattern | Hits in `services/droplist` |
|---|---|---|
| Literal Signal name | `Signal\.v1` | 41 lines (BIBLE.md, PACKETS/005-010, tests, atlas_signal.py) |
| Env-gate string | `DROPLIST_ATLAS_SIGNALS_URL` | 6 (graph_engine.py × 1, test_atlas_emit.py × 3, test_server.py × 2 — guard to ensure not set during unrelated tests) |
| Public mapper | `dag_to_signal\(` | 3 (definition + 1 prod caller + 1 test caller) |
| Public POSTer | `emit_signal\(` | 2 (definition + 1 prod caller) |
| Local wrapper | `_maybe_emit_atlas_signal\(` | 2 (definition + 1 prod call site) |
| Enum field | `source_layer` | 5 (1 def, 1 doc string, 1 envelope, 2 in test invariants) |
| Receive-side shapes | `def.*signal|read_signal|GET.*signal|@app.*signal` | 0 in-droplist consumers (only emit-side defs match) |

Other patterns from the spec (`signal_v1`, `publish`, `send_signal`) returned no in-droplist code hits.

---

## Phase 2 — LOCAL MAP (delta-scp symbol slice)

```
=== droplist/atlas_signal.py | 6276 B, 1569 tok ===
  def _derive_priority               line 43
  def _node_summary                  line 57
  def _collect_action_options        line 68
  def dag_to_signal                  line 87
  def emit_signal                    line 154

=== droplist/graph_engine.py | 8803 B, 2200 tok ===
  def _maybe_emit_atlas_signal       line 21
  def run_graph                      line 126     <-- emit call site at line 203
  def _finalize                      line 207
  def state_summary                  line 221

=== test_atlas_emit.py | 6653 B ===
  class _CaptureHandler                line 47
  def case_positive_emits_signal       line 79
  def case_negative_no_env_no_emit     line 132

=== test_atlas_signal.py | 9402 B ===
  def fixture_animal_needs_human       line 51
  def fixture_build_problem_complete   line 71
  def fixture_money_task_failed        line 85
  def fixture_general_idea_stalled     line 102
  def structural_check                 line 131
  def strict_check                     line 172
```

Full JSON map at `B-droplist-scp.json` (64 files, 95% token reduction).

---

## Emit sites

| # | File:line | Symbol | Role |
|---|---|---|---|
| 1 | [services/droplist/droplist/atlas_signal.py:87](services/droplist/droplist/atlas_signal.py:87) | `dag_to_signal(dag, source_layer="optogon")` | Pure mapper · DAG → Signal.v1 dict |
| 2 | [services/droplist/droplist/atlas_signal.py:154](services/droplist/droplist/atlas_signal.py:154) | `emit_signal(signal, url, timeout=10.0)` | POSTer · stdlib urllib · returns `{ok, error?}` |
| 3 | [services/droplist/droplist/graph_engine.py:21](services/droplist/droplist/graph_engine.py:21) | `_maybe_emit_atlas_signal(dag)` | Env-gated wrapper · invokes mapper + POSTer + audit log |
| 4 | [services/droplist/droplist/graph_engine.py:40](services/droplist/droplist/graph_engine.py:40) | `atlas_signal.dag_to_signal(dag)` | Prod call site for mapper |
| 5 | [services/droplist/droplist/graph_engine.py:42](services/droplist/droplist/graph_engine.py:42) | `atlas_signal.emit_signal(sig, url)` | Prod call site for POSTer |
| 6 | [services/droplist/droplist/graph_engine.py:203](services/droplist/droplist/graph_engine.py:203) | `_maybe_emit_atlas_signal(dag)` | The single emit trigger — fires at the end of `run_graph` after `_finalize` |

Audit log: every emit attempt appends a record `{dag_id, event:"atlas_signal_emit", url, signal_id, ok, error}` to `data/dag_events.jsonl` (graph_engine.py:48). Independent of success/failure.

---

## Consume sites (inside services/droplist)

**None.** services/droplist is producer-only. Verified via two angles:

| Angle | Search | Result |
|---|---|---|
| Receive shapes | `def.*signal\|read_signal\|GET.*signal\|@app.*signal` over `*.py` | 0 in-droplist consumer fns (matches are all emit-side) |
| Server route map | `Signal.v1` / `/api/signals/ingest` in `droplist/server.py` | server.py:23 says **"DropList feeds Lattice indirectly via PKT-006's Signal.v1 emission"** — explicit comment that the consume side lives in delta-kernel, not here |

Per BIBLE.md:234 (OQ-10): consume seam = `POST /api/signals/ingest` on **delta-kernel**, not droplist. Out of scope for this trace.

---

## Drift findings

| # | Drift | Evidence | Severity |
|---|---|---|---|
| D1 | **OQ-17 still pending.** `dag_to_signal` defaults `source_layer="optogon"` because the Signal.v1 enum lacks a `"droplist"` value. Every emitted signal therefore mis-attributes its layer. | atlas_signal.py:87 (default), atlas_signal.py:92 (docstring states why), BIBLE.md:241 (OQ-17 row), PKT-010 §330-331 (still untouched 2026-06-15) | Doctrinal, expected · documented in BIBLE §13 |
| D2 | **Audit-log error truncation is asymmetric.** `_maybe_emit_atlas_signal` truncates both `resp.error` and broad-except messages to 200 chars (graph_engine.py:45,47), while the underlying `emit_signal` already returns the full `str(e)` un-truncated (atlas_signal.py:176). Long stack signatures get clipped at the wrapper, not the source. | atlas_signal.py:176 vs graph_engine.py:45/47 | LOW · audit cosmetics only |
| D3 | **Defensive emit for non-terminal status.** `_STATUS_TO_SIGNAL_TYPE` includes `"running"` → `"status"` and `"blocked"` → `"blocked"` for "should not normally be emitted" cases (atlas_signal.py:33-35). But `_maybe_emit_atlas_signal` runs unconditionally after `_finalize` (graph_engine.py:203), and `_finalize` (graph_engine.py:207-) only resolves to `complete`/`failed`/`needs_human` — never `running` outright. The defensive mapping is dead under current call-graph. | atlas_signal.py:33-35; graph_engine.py:207-214 | LOW · belt-and-braces; can stay |
| D4 | **No emit on `stalled`** is in the schema mapping (`stalled` → `blocked`), but `_finalize` does not produce a `"stalled"` status — its terminal set is `{complete, failed, needs_human}` plus pass-through. `stalled` is reachable only if upstream code stamps it before `run_graph` returns. | atlas_signal.py:32; graph_engine.py:207-214 (no `stalled` branch) | LOW · loose coupling between mapper and finalizer |

No load-bearing schema/contract drift detected in-droplist. The producer is consistent with PKT-005 / PKT-006 doctrine and Signal.v1 closed-set enums.

---

## Verified claims (Phase 3)

| # | Claim | Verdict | Evidence (2 angles) |
|---|---|---|---|
| C1 | services/droplist has exactly one Signal.v1 emit site — `graph_engine.run_graph()` line 203 → `_maybe_emit_atlas_signal(dag)`, defined at graph_engine.py:21 | ✅ verified | Angle A (def): `def _maybe_emit_atlas_signal` → 1 hit at graph_engine.py:21. Angle B (callers across `*.py`): `_maybe_emit_atlas_signal\(` → 1 call at graph_engine.py:203; `atlas_signal.emit_signal\(` → 1 inner call at graph_engine.py:42 (inside the wrapper itself). No other emit paths. |
| C2 | `dag_to_signal()` defaults `source_layer` to `"optogon"`, no caller in-droplist overrides it; OQ-17 still pending | ✅ verified | Angle A (def): atlas_signal.py:87 → `source_layer: str = "optogon"`. Angle B (callers): graph_engine.py:40 → `atlas_signal.dag_to_signal(dag)` (1-arg) · test_atlas_signal.py:206 → `atlas_signal.dag_to_signal(dag)` (1-arg). atlas_signal.py:92 docstring + BIBLE.md:241 OQ-17 row confirm pending state. |
| C3 | `emit_signal` never raises — returns `{ok: False, error}` on URLError/OSError; `_maybe_emit_atlas_signal` has its own broad-except backstop, so the graph loop always settles | ✅ verified | Angle A (atlas_signal.py exception path): two `except` clauses at L173 (JSONDecodeError → `{ok: True, raw}`) and L175 (URLError/OSError → `{ok: False, error: str(e)}`). Zero `raise` statements. Angle B (graph_engine.py guard): L43 reads `resp.get("ok")` (not exception), L46 wraps the whole try with `except Exception` and comment `# emission must never break the loop`. |

Total claims surveyed: **3 load-bearing, all ✅**. No partial or busted verdicts.

---

## Self-assessment — what did skills add over Glob/Grep?

**delta-scp added:** a stable symbol→line map for all 6 hit files in one JSON artifact (atlas_signal.py: 5 defs at L43/57/68/87/154; graph_engine.py: 6 defs at L21/51/61/126/207/221) without me having to read each file linearly. The 95% token reduction is a real win for downstream re-prompting — instead of feeding the next agent ~83k tokens of source, I can hand it a 4.2k-token skeleton plus targeted excerpts. For *this* trace specifically (5 files, ~30 KB total), Read+Grep would have got me there too — the skill's value scales with corpus size. Net: useful artifact, marginal gain on this small subset.

**code-recon added:** the *protocol structure* — claims-table, two-angle requirement, verdict labels (✅/⚠️/❌), "demote unverified to suspicion". Grep alone produces hits; the skill produces an audited finding. The two-angle rule caught one near-mistake: I almost claimed "no consumer in droplist" from a single negative grep, but the protocol forced a second angle (server.py:23 doc-comment explicitly disclaiming consumer role), which made the absence claim defensible per the proof-of-absence rule. Net: genuine quality lift on the *report*, not the *raw hits*.

**Where Grep would have sufficed:** the emit-site enumeration (C1) and the source_layer default (C2 angle A) — straight one-shot Grep questions. The skill-overlay paid off most on (a) the absence claim about consumers, (b) the no-raise behavior claim (C3) which requires checking two files' exception/return paths jointly.

**Search angles tried (final count):**
- Phase 1 hunt: 6 distinct grep patterns (Signal.v1 literal, env-var, 3 symbol names, source_layer)
- Phase 3 verify: 6 grep calls (2 angles × 3 claims)
- 1 absence check (receive-shape grep) for the consumer claim

---

MANUAL TRIAL B COMPLETE
