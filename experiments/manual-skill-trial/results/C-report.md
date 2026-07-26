# Trial C · Sweep-first · Signal.v1 emit/consume in services/droplist

**Method:** Sweep 4 logically-independent angles, pool findings, then run every load-bearing claim through the `code-recon` skill for 2-angle verification. Drop anything that doesn't survive.

---

## Skill invocation log

Every claim that landed in the verified tables below was sent through the `code-recon` skill via the Skill tool (not silently emulated). Markers, in order:

| # | Claim sent to code-recon | Marker printed |
|---|---|---|
| 1 | `dag_to_signal` at atlas_signal.py:87 returns Signal.v1-shaped dict with 7 required fields | `[SKILL INVOKED: code-recon]` |
| 2 | `emit_signal` at atlas_signal.py:154 is the POST helper using stdlib urllib (zero-dep) | `[SKILL INVOKED: code-recon]` |
| 3 | `graph_engine.run_graph` calls `_maybe_emit_atlas_signal` at line 203; def at line 21 | `[SKILL INVOKED: code-recon]` |
| 4 | `DROPLIST_ATLAS_SIGNALS_URL` env gates the emit; unset = silent no-op | `[SKILL INVOKED: code-recon]` |
| 5 | **Absence claim:** zero Signal.v1 *consumption* sites inside services/droplist | `[SKILL INVOKED: code-recon]` |
| 6 | Signal.v1 JSON schema lives outside droplist at contracts/schemas/Signal.v1.json | `[SKILL INVOKED: code-recon]` |
| 7 | `source_layer="optogon"` default is a documented drift (OQ-17 pending) | `[SKILL INVOKED: code-recon]` |

All 7 invocations completed; no skill errors recorded.

---

## Phase 1 — SWEEP hit counts

| Investigation | Pattern shape | Total raw hits | Unique source files (excl. docs) |
|---|---|---:|---:|
| Inv 1 — emit/publish/send/post | `emit\|publish\|send_signal\|post.*signal\|atlas_signal\|AtlasSignal` | 100 hits across BIBLE/PACKETS/code | 5 (atlas_signal.py, graph_engine.py, server.py, cli.py, inventory.py) |
| Inv 2 — consume/subscribe/handle | `consume\|subscribe\|on_signal\|handle_signal\|receive\|read.*signal` | 18 hits | 1 code file (test_atlas_emit.py — the receiver is a test HTTP fixture, not production droplist code) |
| Inv 3 — schema/type defs for Signal.v1 | `Signal\.v1\|class Signal\|signal.*schema` | 70 hits | 3 (atlas_signal.py, test_atlas_signal.py, test_atlas_emit.py) — no schema literal in droplist |
| Inv 4 — Signal-flow tests | `def test.*signal\|def test.*atlas\|test_atlas\|signal.*test` | 19 hits | 2 (test_atlas_signal.py, test_atlas_emit.py) |

**Pooled candidate set for verification:** `droplist/atlas_signal.py`, `droplist/graph_engine.py`, `droplist/server.py`, `test_atlas_signal.py`, `test_atlas_emit.py`, plus `contracts/schemas/Signal.v1.json` (external boundary).

---

## Phase 2 — Verify results

7 load-bearing claims sent through code-recon. **7 verified, 0 dropped.**

| # | Claim | Verdict | Evidence (2+ angles) |
|---|---|---|---|
| 1 | `dag_to_signal` at atlas_signal.py:87 produces a Signal.v1-shaped dict with `schema_version, id, emitted_at, source_layer, signal_type, priority, payload` | ✅ verified | (a) `rg ^def dag_to_signal` → line 87 hit. (b) Read of lines 143-151: literal dict with exactly the 7 claimed keys. |
| 2 | `emit_signal` at atlas_signal.py:154 is the live POST helper using stdlib urllib (zero-dep) | ✅ verified | (a) `rg` → def at :154, `urllib.request.Request` at :163, `urllib.request.urlopen` at :169. (b) `grep` of pyproject.toml: no `requests/httpx/aiohttp` deps — zero-dep claim holds. |
| 3 | `graph_engine.run_graph` calls `_maybe_emit_atlas_signal` at :203; def at :21 | ✅ verified | (a) `rg _maybe_emit_atlas_signal` → exactly 2 hits in droplist code: def at graph_engine.py:21, call at :203. (b) Read of :195-204: the call sits after `_finalize(dag)` and the "settled" event append, confirming "after settle" causality. |
| 4 | `DROPLIST_ATLAS_SIGNALS_URL` env gates the emit; unset = silent no-op | ✅ verified | (a) `rg` → graph_engine.py:28 reads env, :29-30 has `if not url: return`. (b) test_atlas_emit.py:138 pops the var for negative case + assertion that 0 POSTs happen. |
| 5 | **Absence:** zero Signal.v1 consumption sites in services/droplist | ✅ verified (3 angles for absence) | (a) `rg "loadSignals\|readSignals\|consume.*signal"` in droplist/ → 0 code hits (only docstring mentions of the *external* `/api/signals/ingest` endpoint in atlas_signal.py:3,159). (b) `rg "signal_type\|source_layer\|schema_version 1.0"` → only 1 file (atlas_signal.py, the producer). (c) `rg "urlopen"` → 4 hits total, all outbound POST/GET (atlas_signal:169 emit, retrieval:92 search, toolrouter:97,153 tools) — none read signals. |
| 6 | Signal.v1 JSON schema lives outside droplist at contracts/schemas/Signal.v1.json | ✅ verified | (a) `glob **/Signal.v1.json` machine-wide → canonical at `contracts\schemas\Signal.v1.json` (worktree copies are dupes). (b) `glob **/*.json` inside services/droplist → only `.weapon/mission.json` + `data/*.json` instance files; no Signal.v1.json. |
| 7 | `source_layer="optogon"` default is documented drift (OQ-17 pending) | ✅ verified | (a) Read of Signal.v1.json:21-23 → enum = `["site_pull","optogon","atlas","ghost_executor","claude_code"]`, "droplist" absent. (b) atlas_signal.py:87 default + :92-93 docstring + BIBLE.md:241 (OQ-17 row) cite the same drift. |

No claim was demoted. None of the 7 collapsed under 2-angle scrutiny.

---

## Emit table (verified only)

| Site | File:line | Notes |
|---|---|---|
| Pure mapping (DAG → Signal.v1 dict) | services/droplist/droplist/atlas_signal.py:87 | `dag_to_signal()` — I/O-free, pure |
| Wire helper (POST over urllib) | services/droplist/droplist/atlas_signal.py:154 | `emit_signal()` — zero-dep stdlib |
| Env-gated call site (production wire) | services/droplist/droplist/graph_engine.py:21 (def) / :203 (call inside `run_graph`) | `_maybe_emit_atlas_signal()` — fires after `_finalize` + "settled" event |
| Module re-export | services/droplist/droplist/server.py:11-12 | `from . import atlas_signal` — kept for v2 mutation surface, no runtime use today |

**Settle pipeline:** `engine.process_drop → dag_builder.build_dag → run_graph (loop) → _finalize → storage "settled" event → _maybe_emit_atlas_signal → atlas_signal.dag_to_signal → atlas_signal.emit_signal → POST $DROPLIST_ATLAS_SIGNALS_URL`.

---

## Consume table (verified only)

| Site | File:line | Notes |
|---|---|---|
| _(none inside services/droplist)_ | — | Verified via 3 independent angles (claim 5). All signal consumption is downstream in **delta-kernel**, which is outside this trial's scope. |

---

## Drift findings (verified only)

1. **`source_layer` enum drift (OQ-17).** Schema enum at contracts/schemas/Signal.v1.json:23 does not list `"droplist"`. droplist/atlas_signal.py:87 hard-codes `"optogon"` as a known placeholder, documented in the docstring at :92-93 and in BIBLE.md:241. This is **conscious, tracked drift**, not silent — the placeholder is the right call until Atlas-side cares about distinguishing the producer.

2. **No retry / no buffer.** When the POST in emit_signal fails, the error is captured into dag_events.jsonl via the record dict in graph_engine.py:31-48 but never retried. BIBLE.md:326 and :345 document this as a deferred opening (no separate OQ filed; will open one if/when the consumer goes down for non-trivial windows). Not a bug — it's the explicit fail-safe contract: emission must never break the graph loop (graph_engine.py:24-25).

3. **No schema validation at emit time.** `emit_signal` POSTs the dict without running it through `jsonschema`. Tests (test_atlas_signal.py:178-182) do strict schema validation, but production code does not. Acceptable today because `dag_to_signal` is a closed-mapping function whose enum outputs are exhaustively tested; would become a latent bug if `dag_to_signal` ever became data-driven from runtime config.

No surprises beyond the documented OQs. No undocumented drift was found.

---

## Self-assessment

**What I did:** sweep across 4 logically-disjoint angles, pool 5 candidate code files, send 7 load-bearing claims through code-recon, verify each with at least 2 independent searches (3 for the absence claim), then build emit/consume/drift tables only from the survivors.

**Gate behavior:** 0/7 dropped. Strict gate held — no quietly-believed claim slipped into the report.

**Cost of the skill invocations:** each Skill call re-loads the full code-recon SKILL.md as a system message before returning, which is noticeable token weight per claim. With 7 claims that adds up. The value comes from the *structural enforcement* — having to phrase the claim as a discrete sentence before searching forces sharper claim scoping than a free-form sweep does.

**What did code-recon add over manual 2-angle verification:** Honest answer — for this codebase and these claims, *not much new evidence*. I could have run the same `rg` + `Read` pairs without the skill wrapper, because the protocol the skill prescribes (proof-of-absence needs ≥2 angles, citations required) is the protocol I already follow when treating my own findings as a generated report. What the skill *did* add: (a) a forcing function that I phrase each load-bearing claim as a single sentence before searching, which kept me from collapsing "emit + consume" or "schema + drift" into compound claims that hide weakness; (b) the absence-claim protocol explicitly demanded the *third* angle on claim 5 (I had two, the skill posture pushed me to a third independent search, which surfaced the urlopen-call accounting). Manual 2-angle verification would have given me the same verdicts on claims 1-4, 6, 7 with less ceremony; the explicit skill posture earned its keep on the absence claim and on claim discipline.

**Net for trial purposes:** the skill is most valuable when claims are *causal* or *absence-shaped* and least valuable when claims are *presence at file:line* (which the read tool already over-determines). A pragmatic future shape would be: invoke code-recon for causal/absence claims; do plain rg+Read for presence claims.

MANUAL TRIAL C COMPLETE
