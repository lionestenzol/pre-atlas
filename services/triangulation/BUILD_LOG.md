# Triangulation Labeler Build Log

Running architectural memory.

---

## Phase A - Scaffold + spatial.py
**Date:** 2026-04-26
**Status:** Complete
**Summary:** Stood up the package per Bruke's brief. `schema.py` materializes the input/output contracts as dataclasses. `spatial.py` fully implements all 5 functions in pure numpy. `visual.ReferenceLibrary` is fully implemented (no model needed); `visual.Embedder.embed` raises `NotImplementedError` until Phase B. `consensus.aggregate` is fully implemented with cold-start tolerance. `api.py` is a Phase C stub. Tests cover schema, spatial 5/5 functions including 0/1/1000+ edge cases, and consensus verdict logic with mocked signals.

**Key decisions:**
- Located at `services/triangulation/`. Mirrors `services/cortex/` and `services/perception/`.
- Inputs as `dataclass(frozen=True)`, outputs mutable so consensus can enrich. Caller passes raw dicts; we materialize via `ElementInput.from_dict(d)` helper.
- `text_extractor`-style choice: brief shows inputs as dicts, but internal API accepts `ElementInput` for type safety. `from_dict` keeps the wire format ergonomic.
- `find_alignment_groups` returns `list[list[str]]` (IDs) per brief signature. Other spatial functions take element dicts (so they can read bbox without a separate lookup).
- Cold-start path: `visual.score_element` returns `score=None` BEFORE calling embedder if the library has no entries for the element's label. Phase A can therefore exercise the cold-start verdict logic without the model.
- Visual deps gated as `[visual]` extra. Default install is numpy + pytest only.
- API deps gated as `[api]` extra. Phase A package has no FastAPI surface.
- `find_alignment_groups` axis semantics: `axis='y'` means cluster by top edge (same horizontal row); `axis='x'` means cluster by left edge (same vertical column). `check_spacing_regularity` interprets `axis` the same way - alignment axis, with spacing computed along the perpendicular axis.

**Tolerances are placeholders (per brief):**
- `ALIGNMENT_TOLERANCE_PX = 4`
- `LABEL_CONSISTENCY_THRESHOLD = 0.85`
- `SIGNAL_WEIGHTS = {dom: 0.30, spatial: 0.35, visual: 0.35}`
- DO NOT TUNE until Phase D real-data calibration.

**Open questions for Bruke:**
- Confirm location: `services/triangulation/`. OK?
- Confirm API port: `3010` (next after cortex `3009`).
- Confirm `ElementInput.from_dict` materialization approach (vs accepting raw dicts everywhere).
- Confirm visual deps should be optional `[visual]` extra (not runtime).

**Punted to later phases:**
- Phase B: `visual.Embedder.embed` with SigLIP-2.
- Phase C: `api.py` FastAPI surface.
- Phase D: Tolerance tuning against 100+ real anatomy-extension outputs.
- Stretch: `behavioral_score` field in `VerifyResult` exists but no code populates it.

**Test results post-execution:** 46/46 passing. Coverage:
- `__init__.py` 100%, `config.py` 100%, `schema.py` 98%, `spatial.py` 98%, `consensus.py` 98%
- `verify.py` 33% (untested cold-start path; covered indirectly via consensus tests)
- `visual.py` 28% (`Embedder.embed` Phase B stub; `score_element` warm-path Phase B)
- `api.py` 0% (Phase C stubs)
- TOTAL 76% (Phase A target hit; gaps are Phase B/C territory).

**Codex review of Phase A source (read-only sandbox):**
Codex found 3 real bugs + 1 false positive:
- [BUG] FALSE POSITIVE: `check_label_consistency` "missing axis param". Brief explicitly says `(group) -> dict` with no axis. No fix needed.
- [BUG] FIXED: `find_alignment_groups` was anchor-based clustering (all elements compared to first edge). Switched to chain-connected (single-linkage) - each element compared to previous in sorted order. Robust to subpixel drift across long aligned runs. Test `test_find_alignment_groups_chain_connected` added to lock the new semantics.
- [BUG] FIXED: `consensus.aggregate` auto-confirmed when both signals were cold-start (score=None). Per brief, cold-start "doesn't penalize" but also shouldn't auto-confirm without evidence. Added `spatial_agrees`/`visual_agrees` predicates. New behavior: confirmed requires at least one non-DOM signal to actively agree. Both-cold-start now flags. Test `test_flagged_when_both_signals_cold_start` added.
- [BUG] FIXED: `visual_disagrees` ignored `visual_score`, keying only off `nearest_label`. Defensive: now requires both `visual_score is not None` AND `visual_nearest is not None` AND `visual_nearest != element.label`. Future visual paths that decouple score from label can't accidentally trigger disagreement.
- [WARN] DEFERRED: `check_spacing_regularity` returns 1.0 when mean gap ~ 0 (overlapping/touching elements). Acceptable Phase A; flag for Phase D real-data review.
- [WARN] DEFERRED: `score_element` calls `find_alignment_groups` 2N times for N elements (O(n² log n)). Within the 2s/100-element budget per brief; cache groups per page if Phase D shows it as the hot path.
- [WARN] DEFERRED: `VerifyResult.signals` is `dict[str, Any]` storing dicts but the comment says "SpatialSignal/VisualSignal". Consistent at runtime (everything goes through `to_dict`); revisit as type tightening when Phase B+C land.

**Codex's review style note:** Codex is a useful second pair of eyes but not infallible - the false positive on `axis` parameter shows it can hallucinate brief-fidelity claims. Verify against the actual brief before acting on every flag.

**Items NOT changed (Phase A):**
- Tolerance values (per brief: do not tune)
- Schema dataclass placement
- API surface (Phase C)
- Embedder model loading (Phase B)
- Performance optimizations (Phase D)
