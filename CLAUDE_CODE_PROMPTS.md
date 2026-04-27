# Claude Code Prompt Pack — Perception System Build

Run Claude Code from the repo root (`C:\Users\bruke\Pre Atlas`). Paste each prompt in order. Wait for Claude Code to finish and confirm before pasting the next.

---

## Asset audit (pre-flight findings)

Before pasting Prompt 0, know that I searched the repo for the four placeholder paths in the spec. Results:

| Spec placeholder      | Resolved path                                                                                | Confidence | Notes |
|-----------------------|-----------------------------------------------------------------------------------------------|------------|-------|
| `<SCANNER_PATH>`      | `tools/anatomy-research/browser-use/browser_use/dom/serializer/serializer.py`                | HIGH       | DOMTreeSerializer emits bounding boxes from URL → DOMSnapshot pipeline. Adjacent files (`enhanced_snapshot.py`, `clickable_elements.py`, `element.py`) are part of the same scanner. |
| `<ANNOTATOR_PATH>`    | **NOT FOUND**                                                                                 | —          | Repo classifies elements as clickable/decorative but has no semantic-section labeler (nav/hero/cta/feature/pricing/footer). Spec says "do not modify, repoint inputs" — but there's nothing to repoint. **This is a gap; resolve before Step 1.** |
| `<VIEWER_PATH>`       | `tools/anatomy-research/JSON-Alexander/src/viewer.ts`                                         | MEDIUM     | TypeScript, not React. Spec says "React component (UI Runtime artifact, attached separately)" — the React viewer may be the *separately-attached* artifact, not this file. **Confirm with user before Step 10.** |
| `<FUZZ_TEST_PATH>`    | `tools/anatomy-research/browser-use/tests/ci/browser/test_dom_serializer.py`                  | HIGH       | Stress-tests serializer against 15+ real sites. `services/cognitive-sensor/requirements-fuzz.txt` is a different system (cognitive-sensor) — ignore. |

---

## Prompt 0 — Kickoff (paste first)

```
You are going to execute a multi-step build spec for a "Perception System" that reads webpages. The spec is long and strict. Read it twice before writing any code.

## Repo location
We are in `C:\Users\bruke\Pre Atlas`. The build will live in a new `perception/` directory at the repo root.

## Resolved placeholder paths (the spec uses placeholders like <SCANNER_PATH>)
- SCANNER_PATH = `tools/anatomy-research/browser-use/browser_use/dom/serializer/serializer.py`
  (the DOMTreeSerializer; adjacent files in `browser_use/dom/` — `enhanced_snapshot.py`, `clickable_elements.py`, `element.py`, `views.py` — are part of the same scanner subsystem)
- FUZZ_TEST_PATH = `tools/anatomy-research/browser-use/tests/ci/browser/test_dom_serializer.py`

## Known gaps — do not invent paths; flag these in your first response
- ANNOTATOR_PATH: no existing annotator was found. Repo only classifies clickable/decorative, not nav/hero/cta/etc. The spec says "do not modify, repoint inputs" — but there's nothing to repoint. Decide whether (a) the annotator should be built fresh inside `perception/` as a new module, or (b) we wait for the user to point at one. Do not assume.
- VIEWER_PATH: there is `tools/anatomy-research/JSON-Alexander/src/viewer.ts`, but it's TypeScript, not the React component the spec describes. The spec says the viewer is "attached separately" — the React file may not be in the repo yet. Flag this and ask before Step 10.

## Your first task (this is from §12 of the spec — follow it literally)
Do not write any code yet.
1. Read the entire spec below.
2. Restate the architecture in your own words (≤300 words).
3. List ambiguities, gaps, contradictions.
4. List assumptions you'd be making that should be confirmed (especially around the two known gaps above).
5. Propose your concrete plan for Step 1.
6. Stop and wait for my confirmation.

Open and read these files before responding so your understanding of the existing scanner is real, not inferred:
- `tools/anatomy-research/browser-use/browser_use/dom/serializer/serializer.py`
- `tools/anatomy-research/browser-use/browser_use/dom/views.py`
- `tools/anatomy-research/browser-use/tests/ci/browser/test_dom_serializer.py` (skim)

## The spec begins below — read it in full

[PASTE THE FULL "Perception System — Build Spec" HERE]
```

> Paste the full spec text where indicated. Don't summarize it — Claude Code needs the original.

---

## Prompt 1 — Approve plan and start Step 1

After Claude Code returns its restatement, gaps, and Step 1 plan, review carefully. Then paste:

```
Plan approved with these adjustments: [edit or write "no changes"].

For the annotator gap: [pick one]
  (a) Build a fresh `perception/annotator.py` module that runs on reconciler output, owned by this build. Treat the spec's "repoint inputs" instruction as N/A.
  (b) Skip annotator integration entirely for now; reconciler + lexicon + priors are sufficient to produce labels.

For the viewer gap: defer the viewer integration question until Step 10. Build everything else assuming the viewer will be wired in later.

Proceed with Step 1 (Schema + project skeleton). Follow the spec's "Done when" criteria literally. After tests pass:
  1. Append a Step 1 entry to BUILD_LOG.md per §10's protocol.
  2. Stop and report. Do not start Step 2.
```

---

## Prompts 2–9 — Step continuations

After each step finishes and you've reviewed the BUILD_LOG entry + diff, paste the next prompt. The pattern is the same; just change the step number and name.

```
Step 1 reviewed and accepted. Proceed with Step <N> — <Module Name>.

Constraints (re-stated so you don't drift):
- Do not deviate from the canonical Element schema. If you need a new field, stop and propose it in BUILD_LOG.md instead of adding it.
- Do not skip writing tests. Every module needs them before the step is considered done.
- Use only allowed dependencies (stdlib, dataclasses, pytest, numpy if calibrator needs it). Justify any other addition in BUILD_LOG.md.
- Honor the "Done when" line in the spec for this step — that's the acceptance gate.

After tests pass, append the Step <N> entry to BUILD_LOG.md and stop. Do not start Step <N+1>.
```

Step names for reference:
- Step 2 — Stub reconciler + scanner adapter
- Step 3 — Text extractor
- Step 4 — Calibrator
- Step 5 — Lexicon
- Step 6 — Priors
- Step 7 — Pattern library
- Step 8 — Real reconciler
- Step 9 — Chapter extractor

---

## Prompt 10 — Step 10, with viewer gap resolution

```
Step 9 reviewed and accepted. Before starting Step 10, the viewer question:

[Pick one and edit before pasting]
  (a) The React viewer artifact lives at <PATH>. Wire correction hooks into it.
  (b) The React viewer is not in the repo yet. Build only `perception/corrections_log.py` for now; emit a stub `viewer_hooks.md` documenting the exact contract the future viewer must satisfy (event names, payload shape, file path). I will wire it in later.

Proceed with Step 10. Same constraints as before. Append BUILD_LOG entry and stop.
```

---

## Prompts 11–12 — Final steps

```
Step 10 reviewed and accepted. Proceed with Step 11 — `scripts/update_from_corrections.py`. Same constraints. Append BUILD_LOG entry and stop.
```

```
Step 11 reviewed and accepted. Proceed with Step 12 — End-to-end fixture suite.

This is the final step. Definition of done for the whole project (§11):
- `perceive(url)` runs end-to-end on a real URL and returns a PageGraph.
- ≥85% label accuracy and 100% chapter structure match across the fixture suite.
- Reconciler + schema have 100% test coverage; rest ≥80%.
- Viewer renders output and writes corrections to corrections.jsonl (or stub contract documented).
- update_from_corrections.py produces reviewable diffs.
- BUILD_LOG.md has an entry for every step.
- `python -m perception.pipeline <url>` works.

Build at least 3 fixtures (saas_landing, ecommerce_pdp, one of your choice) with hand-labeled expected outputs. Run the full pipeline against each. Report final coverage and accuracy numbers in the Step 12 BUILD_LOG entry, then stop.
```

---

## Recovery prompts (use as needed)

**If Claude Code drifts from spec (adds fields, skips tests, modifies existing scanner):**
```
Stop. Revert that change. The spec's §6 "Do-not list" is non-negotiable. Specifically: <quote the violated rule>. Redo this step honoring that constraint.
```

**If a step's tests don't fully pass but Claude Code wants to move on:**
```
Do not advance. Spec §5 says each step's "Done when" is the acceptance gate. List the failing tests, root-cause each, and either fix or document why the test is wrong (and update it). Then re-run.
```

**If `BUILD_LOG.md` entry is missing or thin:**
```
The BUILD_LOG entry for Step <N> is missing/incomplete. Per §10, every step needs: Date, Status, Summary (one paragraph), Key decisions, Open questions, Test results. Add or expand the entry before we proceed.
```

---

## Notes for you (the human in the loop)

1. **Read every BUILD_LOG entry before approving the next step.** The whole point of this architecture is that learning is legible — that's also true of the build itself.
2. **Don't let the annotator gap drift.** Make a call before Step 1: build it fresh inside `perception/`, or drop it. If you wait until Step 8 to decide, the reconciler will get rebuilt.
3. **Step 8 is the high-risk step.** The reconciler is "the brain." Budget extra review time. Have it write more conflict scenarios than feels necessary.
4. **The fixture suite (Step 12) is where it actually proves itself.** Don't accept fixtures Claude Code generated synthetically — feed it real saved scanner outputs from real URLs.
