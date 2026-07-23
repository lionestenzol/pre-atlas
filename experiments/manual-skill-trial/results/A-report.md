# Trial A · Map-first · Signal.v1 emit/consume inside `services/droplist`

**Date:** 2026-06-16
**Working dir:** `C:\Users\bruke\Pre Atlas`
**Scope:** `services/droplist` only
**Approach:** delta-scp (MAP) → grep (RECON) → code-recon (VERIFY)

---

## 1. Skill invocation log

| # | Phase | Skill | Args | Marker | Result |
|---|-------|-------|------|--------|--------|
| 1 | MAP   | `delta-scp` | `services/droplist` | `[SKILL INVOKED: delta-scp]` | OK — skeleton compressed offline (64 files, raw≈83161 → comp≈4158 tok, yield 79003, ratio 0.05) |
| 2 | VERIFY (claim 1) | `code-recon` | `verify: atlas_signal.py:87 defines dag_to_signal …` | `[SKILL INVOKED: code-recon]` | OK — Verify mode |
| 3 | VERIFY (claim 2) | `code-recon` | `verify: graph_engine.py:203 calls _maybe_emit_atlas_signal once …` | `[SKILL INVOKED: code-recon]` | OK — Verify mode |
| 4 | VERIFY (claim 3) | `code-recon` | `verify: ZERO Signal.v1 consume sites within droplist …` | `[SKILL INVOKED: code-recon]` | OK — Verify mode (absence) |

No skill errors. No silent fallback. Phase 2 RECON used `Grep` directly (per task spec — skills required for Phase 1 and Phase 3 only).

Skeleton artifact: [A-droplist-skeleton.json](A-droplist-skeleton.json).

---

## 2. Candidate files (picked from skeleton)

Picked by symbol-name match to `*signal*` / `emit*` / `dag_to_signal`:

| File | Why shortlisted |
|---|---|
| `droplist/atlas_signal.py` | Has both `dag_to_signal` (line 87) AND `emit_signal` (line 154) symbols — canonical mapper + POSTer |
| `droplist/graph_engine.py` | Has `_maybe_emit_atlas_signal` (line 21) — the env-gated wrapper |
| `droplist/server.py` | FastAPI app — would host any internal consumer if one existed |
| `test_atlas_signal.py` | PKT-005 acceptance test for the mapper |
| `test_atlas_emit.py` | PKT-006 acceptance test for live POST |
| `PACKETS/005_*.md`, `PACKETS/006_*.md`, `PACKETS/008_*.md` | Doctrine — confirm intended seam shape |

---

## 3. Emit sites

| File:line | Symbol | Snippet | Confidence |
|---|---|---|---|
| [services/droplist/droplist/atlas_signal.py:87](services/droplist/droplist/atlas_signal.py:87) | `dag_to_signal(dag, source_layer="optogon")` | `def dag_to_signal(dag: dict, source_layer: str = "optogon") -> dict[str, Any]:` — pure mapping DAG → Signal.v1 dict | ✅ High |
| [services/droplist/droplist/atlas_signal.py:154](services/droplist/droplist/atlas_signal.py:154) | `emit_signal(signal, url, timeout=10.0)` | `def emit_signal(signal: dict, url: str, timeout: float = 10.0) …` — POST via stdlib urllib | ✅ High |
| [services/droplist/droplist/graph_engine.py:21](services/droplist/droplist/graph_engine.py:21) | `_maybe_emit_atlas_signal(dag)` | env-gated wrapper; reads `DROPLIST_ATLAS_SIGNALS_URL`, calls `atlas_signal.dag_to_signal` then `atlas_signal.emit_signal`, logs to `dag_events.jsonl` | ✅ High |
| [services/droplist/droplist/graph_engine.py:203](services/droplist/droplist/graph_engine.py:203) | call site `_maybe_emit_atlas_signal(dag)` | one call per `run_graph()` settle, immediately after `storage.save_dag` and the `"settled"` event append | ✅ High |
| [services/droplist/droplist/graph_engine.py:42](services/droplist/droplist/graph_engine.py:42) | `atlas_signal.emit_signal(sig, url)` | indirect emit through `_maybe_emit_atlas_signal` — same chain as row 3, listed for completeness | ✅ High |

**Returned Signal.v1 shape** (atlas_signal.py:143–151):
```python
return {
    "schema_version": "1.0",
    "id": "sig_" + uuid.uuid4().hex[:12],
    "emitted_at": clock.now_iso(),
    "source_layer": source_layer,          # default "optogon"
    "signal_type": signal_type,            # closed enum from _STATUS_TO_SIGNAL_TYPE
    "priority": priority,                  # closed enum
    "payload": payload,
}
```

---

## 4. Consume sites

| File:line | Symbol | Snippet | Confidence |
|---|---|---|---|
| — | — | (none within `services/droplist`) | ✅ High (absence) |

`services/droplist` is **producer-only** for Signal.v1. The consumer is `delta-kernel POST /api/signals/ingest` — outside scope, lives at `services/delta-kernel/src/atlas/signals-store.ts` per `PACKETS/005_atlas_seam_contract.md:44`.

Test-fixture handlers in `test_atlas_emit.py` do `do_POST` (lines 50, 24 of the two test files) — they **simulate** the delta-kernel consumer; they are not droplist consumers.

---

## 5. Drift findings

| # | Finding | Citation | Severity |
|---|---|---|---|
| D1 | `source_layer` hardcoded to `"optogon"` because `Signal.v1.source_layer` enum lacks `"droplist"`. Known open question OQ-17. | [atlas_signal.py:87](services/droplist/droplist/atlas_signal.py:87), [BIBLE.md:241](services/droplist/BIBLE.md:241) | MEDIUM — semantically misleading but documented |
| D2 | `schema_version` literal `"1.0"` hardcoded. No version-bump path defined. | [atlas_signal.py:144](services/droplist/droplist/atlas_signal.py:144) | LOW |
| D3 | Failed emissions logged to `dag_events.jsonl` but **no retry buffer**. If consumer is down, signals are lost. BIBLE acknowledges this. | [graph_engine.py:21-48](services/droplist/droplist/graph_engine.py:21), [BIBLE.md:326](services/droplist/BIBLE.md:326), [BIBLE.md:345](services/droplist/BIBLE.md:345) | MEDIUM — known, deferred |
| D4 | Defensive fallback synthesizes an `action_options` entry if `signal_type=="approval_required"` but no human-blocked nodes exist. Schema requires `minItems >= 1`. | [atlas_signal.py:131-141](services/droplist/droplist/atlas_signal.py:131) | LOW — defensive, documented |
| D5 | `dag_to_signal` default `source_layer="optogon"` is the *only* caller-side call; never overridden by `_maybe_emit_atlas_signal`, so every emitted signal is tagged `"optogon"`. | [graph_engine.py:40](services/droplist/droplist/graph_engine.py:40) | LOW — D1 in practice |

No undocumented drift found. All gaps are explicitly tracked in BIBLE §16 / OQ-17 / PKT-006.

---

## 6. Claims verified (via code-recon, Verify mode)

| # | Claim | Verdict | Evidence (≥2 angles) |
|---|---|---|---|
| 1 | `atlas_signal.py:87` defines `dag_to_signal(dag, source_layer="optogon")` returning Signal.v1 dict | ✅ Verified | (a) signature match at line 87; (b) returned dict literal at lines 144–150 contains exactly the 7 Signal.v1 keys |
| 2 | `graph_engine.py:203` calls `_maybe_emit_atlas_signal(dag)` exactly once per `run_graph()` settle, env-gated by `DROPLIST_ATLAS_SIGNALS_URL` | ✅ Verified | (a) `rg _maybe_emit_atlas_signal\(` returns exactly 1 callsite (line 203) + 1 def (line 21) inside droplist code; (b) gate at line 28 `os.environ.get("DROPLIST_ATLAS_SIGNALS_URL")` with early return at line 30; (c) `run_graph` defined at line 126, settle block 195–203 |
| 3 | ZERO Signal.v1 consume sites inside `services/droplist` | ✅ Verified | (a) `rg @app\.post\|do_POST\|BaseHTTPRequestHandler` inside `droplist/` finds **no** POST handler; only FastAPI GETs in `server.py:45-140`; (b) `rg signals/ingest` finds only docstring/comment references at `atlas_signal.py:3,159`; (c) PKT-007 explicitly notes "zero hits — no consumer outside droplist itself" at [PACKETS/007_lens_seam_cleanup.md:49](services/droplist/PACKETS/007_lens_seam_cleanup.md:49) |

**Claims count:** 3 verified · 0 partial · 0 busted.

---

## 7. Self-assessment

**Coverage:** All emit sites traced (4 distinct lines across 2 files). Absence claim for consumers triangulated across 3 independent angles. Drift findings cross-referenced against BIBLE.md / PACKETS to distinguish *real drift* from *acknowledged-and-deferred*.

**What did skills add over plain Glob/Grep?**

- **delta-scp** turned 333 KB / 64 files into a 4 KB skeleton with symbol-line indexes I could scan in one Read. The candidate shortlist (`atlas_signal.py` + `graph_engine.py`) fell out of the symbol names directly — `dag_to_signal` and `_maybe_emit_atlas_signal` were visible at line numbers before I opened either file. **Without delta-scp I would have used a much broader rg pass and read more files.** Net: faster orientation, fewer wasted reads.
- **code-recon** in Verify mode forced the absence claim (claim 3) through the proof-of-absence protocol — three independent search angles (POST-handler shapes / file-level word hits / exact API path) where I would normally have stopped at one. The skill's `claim → 2+ angles → verdict table` shape is what kept the report honest: D5 (`source_layer` always tagged `optogon` in practice) is a derived finding I only spotted because Verify mode forced me to re-read the call site in graph_engine.py line 40.
- **Trade-off:** Each skill invocation costs a turn and large reminder text. For tiny scopes (≤5 files, ≤200 LOC), Glob/Grep + Read directly is cheaper. The skills earn their cost when (a) the surface is large enough that a skeleton beats a recursive grep, or (b) the claim is an *absence* or *causal* shape where one search angle is structurally insufficient.

**Confidence:** High. Every load-bearing claim has ≥2 citations. The producer-only architecture is independently corroborated by PKT-007 doctrine.

---

MANUAL TRIAL A COMPLETE
