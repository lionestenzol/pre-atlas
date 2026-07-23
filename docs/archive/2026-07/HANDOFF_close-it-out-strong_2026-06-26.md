# HANDOFF · Close It Out Strong — planning input

**Date:** 2026-06-26 · **For:** a long-planning tool, to plan the close of Pre Atlas back to its original goal.
**Read order:** this file → `FORENSIC_DOSSIER_2026-06-26.md` (the self-portrait) → `CAPSULES.md` (the branch museum).

## 0. The mandate
Reconcile five months of fast-expanded scope back to the ORIGINAL goal and finish it. Plan **outcome-first ("back to front")**: start from what DONE looks like for the original goal, trace back to the minimal set that delivers it, treat everything else as a capsule.

## 1. North star · the ORIGINAL goal (genesis sources, verbatim)
From the 2026-01-12 founding docs (README, PHASE_ROADMAP, CONTEXT_PACKET) + `memory/user_atlas_vision.md`:
- **What it is:** a personal OS for *behavioral governance* — analyze conversation history, detect open loops, compute a daily mode, and **route you to close loops before starting new things.**
- **The governor (modes):** `CLOSURE` (blocks new work) · `MAINTENANCE` (build, review first) · `BUILD` (create freely). Full set today: `RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE`.
- **The vision:** remove friction idea → thought → execution. Three pillars: organized/systematized · delegation-ready · **code does the work (deterministic, autonomous, not conversational token-burn).**
- **Stated priority:** *solid functionality over "doneness" — the system runs and executes in your absence.*
- **Your own named anti-pattern (80 days ago):** *"AI-driven scope drift — proposals that sound logical step-by-step but pull away from the core need."*

## 2. Current state · the "back" (git-verified 2026-06-26)
- Two clones: `Pre Atlas` (space) = everything-fork, HEAD `feat/atlas-setup-ui` **134 ahead of main, 0 behind**; `pre-atlas` (hyphen) = delta-scp specialist.
- **~Nothing merged to main in ~5 months.** main is 0-behind, so it can fast-forward: the merge debt is a *decision*, not a labor.
- Core exists: delta-kernel (:3001, TS, tsc clean as of 06-15) · cognitive-sensor (Py/SQLite) · contracts (49 JSON Schemas) · the 4-step pipeline (`scripts/run_all.ps1`).
- **OPEN QUESTION to answer FIRST: does the original 4-step pipeline still run end-to-end autonomously?** That is the #1 vision priority and the gate for everything else.
- 86 branches → 17 capsules (`CAPSULES.md`), ~18 tombstones (zero unique work).

## 3. The pattern to beat
build:close 96:1 · Monday-2pm bursts · fan-out-then-abandon · CLOSURE-mode-locked since February. The plan must make **closing** the deliverable, with proof-gated done-conditions (use `fest`).

## 4. The plan shape (back-to-front)
**DONE looks like:** the original governor runs autonomously end-to-end — ingests history, detects open loops, computes mode, routes you — with no human in the loop; `main` reflects that core; tangents are capsuled.
Minimal path back from DONE:
1. **Capsule + prune** — museum built; pending: `git tag -a capsule/<theme>-<date>` ×17, then prune ~18 tombstones (lossless).
2. **Verify the core runs end-to-end** — the #1 vision priority. If broken, fix the pipeline before anything else. Proof: it produces a daily projection / closes a loop unattended.
3. **Merge to main only the core lineage** — delta-kernel · cognitive-sensor · contracts · projection. Fast-forward is clean. Keep tangents capsuled.
4. **Gate every new build behind the close** — including the Reckon micro-SaaS (`CAPSULE_self-mirror-saas.md`). No repo #9 until the core closes.

## 5. The prize at the finish line
`CAPSULE_self-mirror-saas.md` ("Reckon") — point it at your git, get a candid fact-check about yourself. It IS the multi-tenant productization of the original thesis. Gated behind the core close (you can't sell a stop-scope-drifting tool while scope-drifting).

## 6. Artifacts from this session
- `REPO_FORENSIC_TRACE_2026-06-26.md` — deterministic git forensics.
- `FORENSIC_DOSSIER_2026-06-26.md` — the reflective 8-section self-portrait (24-agent synthesis).
- `CAPSULES.md` — the branch museum (17 capsules).
- `CAPSULE_self-mirror-saas.md` — the Reckon product capsule.
- memory: `project_close_it_out_strong.md` + updated `user_engineering_fingerprint.md`.

## 7. Done-condition for "closed out strong"
- [ ] Core pipeline runs autonomously end-to-end (with a proof artifact).
- [ ] `main` reflects the core.
- [ ] 17 capsules tagged, ~18 tombstones pruned.
- [ ] New-build gate written.

When all four are true: the warehouse is a museum plus a working product, and you've run your own system on yourself.
