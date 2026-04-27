# Perception System Build Log

Running architectural memory. Read this before writing code in any session.

---

## Step 1 - Schema + Skeleton
**Date:** 2026-04-26
**Status:** Complete
**Summary:** Established the canonical `Element` schema verbatim from spec §2, the `perceive()` orchestrator verbatim from spec §4, and stubbed every module the orchestrator calls. All stubs raise `NotImplementedError("Step N - <module>")` so silent pass-throughs are impossible (per spec §6). Project mirrors `services/cortex/` Python service convention (`src/<package>/`, `tests/` sibling, `pyproject.toml`).

**Key decisions:**
- Located at `services/perception/`. Mirrors `services/cortex/`. `tools/` is for browser extensions, `apps/` is for frontends.
- Schema verbatim from spec §2. No additions, no renames.
- One small additive support type: `ChapterResult(elements, chapters)`. Required because spec §4 accesses `chaptered.elements` and `chaptered.chapters`. Flagged here for explicit Bruke approval at Step 1 review. Alternative: `tuple[list[Element], list[Chapter]]`, but the named dataclass reads better.
- Each module fetches URL independently per spec's literal `scan(url)` / `extract(url)` signatures. Shared-DOM optimization deferred until duplicate fetching demonstrably hurts.
- `text_extractor.extract` returns `list[Element]` (spec offered choice between `list[Element]` and parallel `TextContent` list keyed by position). Document choice here so future maintainers don't litigate it.
- `ElementType(str, Enum)` so `ElementType.NAV == "nav"` evaluates True and `dataclasses.asdict` JSON round-trips cleanly.
- `EvidenceStream` stays `Literal[...]` per spec — small fixed value set, never compared with enum-style `is`.
- `Signature` defines a custom `__hash__` so it can be used as a dict key for repetition-group bucketing in Step 4.
- No `slots=True` in any dataclass — defers to Step 8 if memory matters; avoids `from __future__ import annotations` + slots interaction trap.

**Open questions for Bruke:**
- Confirm location: `services/perception/`. OK?
- Confirm annotator is retired. Spec §1 describes it but spec §4's `perceive()` doesn't invoke it. Lexicon + priors + reconciler absorb its job.
- Confirm `ChapterResult` helper is acceptable.
- Confirm `text_extractor` returning `list[Element]` (vs parallel `TextContent` list).

**Spec asset paths - resolved during Step 1 (CORRECTION 2026-04-26):**
The first plan-mode pass missed half the existing infrastructure. After Bruke's "look at site map and chrome extension and use es search" prompt:

| Spec placeholder | Actual asset | Path |
| --- | --- | --- |
| `<SCANNER_PATH>` | anatomy-extension content.js (`gatherCandidatesV2`, classifyClickable, auto-label cascade) driven by Playwright | `tools/anatomy-extension/content.js` |
| `<ANNOTATOR_PATH>` | The 12-rule classifyClickable cascade inside the extension itself | same file |
| `<VIEWER_PATH>` | The HUD overlay rendered by the extension + `.anatomy-pinned-outline` overlays + the anatomy-map skill | extension + `~/.claude/skills/anatomy-map/` |
| `<FUZZ_TEST_PATH>` | **EXISTS** - full Playwright runner + 25 deterministic shapes + sitepull pull/vendor pipeline | `services/cognitive-sensor/fuzz/` (runner.py:32-44 reads `.anatomy-pinned-outline` records) |

Site map / sitepull: `web-audit/bin/sitepull.mjs` (M-mode multi-file), Playwright snapshot (S-mode), emits `.sitepull-manifest.json`. Already integrated as `atl fuzz pull/vendor`.

**Implication for Step 2 (planning revision required before Step 2 starts):**
The previously-considered "subprocess to web-audit/lib/anatomy.js" strategy is the WRONG choice for `scanner_adapter`. The right strategy is to **reuse the fuzz runner's Playwright bootstrap** (`services/cognitive-sensor/fuzz/runner.py:212-303`). Specifically:
- Load anatomy-extension into Playwright Chromium (`--load-extension=...`)
- Trigger auto-label
- Read `.anatomy-pinned-outline` elements + their `getBoundingClientRect()` via `page.evaluate`
- Adapt anatomy-v1 region records → Element schema

The fuzz corpus also doubles as Step 12's end-to-end fixture suite. The 25-shape synthetic generator + sitepull-pulled real corpora give us deterministic + real-world ground truth for free.

This does NOT change Step 1's deliverables - schema and skeleton are independent of which scanner Step 2 uses. But Step 2's plan needs a fresh planning pass that reuses these existing modules instead of subprocessing into Node.

**Codex review of Step 1 (read-only):**
Codex (gpt-5.2-codex via mcp__codex__codex with sandbox=read-only) reviewed `schema.py` against `pipeline.py` and `tests/test_schema.py`. Verdict: 5 [OK], 3 [WARN], 0 [BUG].
- [OK] All mutable defaults use `field(default_factory=...)`. No `= []` or `= {}`.
- [OK] `Signature.__hash__` includes all 5 fields; `child_types` is a tuple (immutable, hashable).
- [OK] `ElementType(str, Enum)` round-trips JSON correctly via `dataclasses.asdict` + `json.dumps`.
- [OK] `from __future__ import annotations` safe on Python 3.11-3.13. Forward refs (`Optional[Signature]`, `Optional[TextContent]`) resolve cleanly.
- [OK] Spec fidelity: 21 fields exactly. No drift. Guarded by `test_element_field_count`.
- [WARN] `Signature` is hashable but not frozen. Mutating after dict-key use would violate hash invariant. Minor; defer to Step 8 if reconciler depends on Signature immutability.
- [WARN] `Optional[T]` vs `T | None` - stylistic only on 3.11+. Defer.
- [WARN] (FALSE POSITIVE) Codex flagged "stray control characters" in section markers. The characters are the U+00A7 `§` symbol I use to reference spec sections. Verified clean - no actual encoding bug.

---

## Step 1 Tweaks - 2026-04-26 (post-review pass)

After Codex + python-reviewer ran a deeper review, 9 items shipped as tweaks. The python-reviewer's HIGH "circular import will fail on Python 3.11-3.13" was a false alarm (Codex correctly identified [OK]; tests pass; standard submodule fall-through behavior). Not acted on.

**Real fixes:**
1. `config.py` path constants - now `Path(__file__).parent`-anchored. JSON/JSONL files moved from project root to `src/perception/`. Wheel-safe.
2. `pyproject.toml` - declares `[tool.setuptools.package-data]` so `lexicon.json` / `priors.json` / `corrections.jsonl` ship with the wheel.
3. `pyproject.toml` - dropped `numpy>=1.26` runtime dep (Step 1 doesn't use it; re-add at Step 4).
4. `tests/test_schema.py::test_corrections_jsonl_exists_empty` - now uses `config.CORRECTIONS_PATH` directly (single source of truth).
5. `tests/test_schema.py::test_no_silent_exception_handlers` - regex broadened to `except[^:\n]*:\s*\n\s*pass\b` with `re.MULTILINE`. Verified catches `except Exception as e: pass`, tuple-excepts, multi-line variants.
6. Added `test_config_paths_anchored_to_package` and `test_lexicon_priors_files_ship_with_package` to lock the path-resolution invariant.

**Refinements:**
7. `pipeline.py` - absolute `from perception import (...)` -> relative `from . import (...)`. All stub modules also use relative imports now. Less fragile coupling.
8. `config.py` - `EVIDENCE_WEIGHTS` typed as `dict[EvidenceStream, float]`. Type-checker now catches typo'd keys at static-check time.
9. `config.py` - deleted dead `PIPELINE_VERSION = VERSION` duplication. Keep `VERSION` only.
10. `tests/test_schema.py::test_perceive_calls_stubs_in_order` - now captures and asserts `reconciler.fuse(geometric=, text=, debug=)` kwargs by identity, not just call order. Catches kwarg drift in future refactors.

**Discretionary decision shipped:**
- `text_extractor.extract` return type changed from `list[Element]` to `list[TextContent]`. Honest typing - text doesn't have geometry until merged. `lexicon.apply` 2nd param and `reconciler.fuse` `text` param updated to match.

**Items NOT changed:**
- Schema (verbatim spec §2)
- `ChapterResult` placement (defensible either way; codex/python-reviewer split LOW)
- `corrections_log.append(dict)` typing (TypedDict deferred to Step 10)
- `Optional[T]` vs `T | None` (stylistic)
- `Signature` not frozen (Step 8 territory)

**Test results post-tweak:** 30/30 passing. Coverage 100% across all 13 modules. Step 1 still meets done-criteria.

**Test results:** 25/25 passing. Schema coverage: 100%. Stub modules at trivial coverage (single-line raises). Run: `pytest -v tests/test_schema.py`.

**Punted to later steps:**
- Real subprocess to `web-audit/lib/anatomy.js` (Step 2).
- anatomy-v1 envelope -> `Element` field mapping (Step 2).
- Calibrator clustering math (Step 4).
- `lexicon.json` content (Step 5).
- `priors.json` content (Step 6).
- Reconciler weighted-vote fusion (Step 8).
- Chapter typography heuristic (Step 9).
- Viewer correction hooks (Step 10).
- `update_from_corrections.py` diff generator (Step 11).
- End-to-end fixture suite (Step 12).
