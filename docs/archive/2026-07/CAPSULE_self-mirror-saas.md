# CAPSULE · "Reckon" (working name) — a forensic fact-check about the builder

**Captured:** 2026-06-26 · **Status:** CAPSULED (do not build until the core close is done — see gate)
**Origin:** Reaction to the Pre Atlas forensic dossier ("being able to scan my git and give me a fact check ABOUT ME... what if we turn it into a micro SaaS").

> This file exists so the idea is preserved and sharp without becoming a new open loop. It is the carrot at the end of the close, not a parallel sprint.

---

## One-liner
Point it at your git history. It tells you the truth about *how you build* — not your stats, your patterns.

## Why now (the wedge)
GitHub Wrapped / "year in code" tools sell **vanity**: streaks, commit counts, top language. This sells **judgment**:
- build : close ratio (feat vs merged-to-main)
- scope-drift / open-loop detection
- cadence fingerprint (when you actually work)
- blind spots, candidly named
- the trajectory arc

In a voice that **stings and is screenshottable.** The viral reaction is "I'm screaming" — that *is* the growth loop. Nobody ships honest self-reflection. That is the gap.

## The moat (assemble-first — do NOT rebuild git analytics)
Git parsing is a solved category. Named candidates to ASSEMBLE, not generate:
- extraction: raw `git log` + awk, or `pygit2` / libgit2, or `git-of-theseus` (line survival over time), `git-quick-stats`
- synthesis engine: Claude API (the part that turns metrics into candid, specific, voiced judgment)
- share card: `satori` / og-image or `node-canvas`

**The product value is the synthesis + the behavioral lens (Pre Atlas open-loop / closure-ratio doctrine) + the voice.** That is the only part worth hand-building. Everything below it is commodity.

## MVP (smallest shippable atom)
1. **Input:** a repo — local path, git URL, or upload.
2. **Extract** (the exact metrics from the dossier run): commit cadence by day/hour, feat:fix:test ratio, ahead/behind main, file births & deaths, churn, rename:delete ratio, biggest-day bursts.
3. **Synthesize:** Claude → (a) a one-page candid dossier, (b) a shareable "reckoning card."
4. **Output:** the card (viral surface) + the full dossier (depth surface).

## Privacy stance (differentiator + matches Bruke's ethos)
**Local-first.** Runs on the user's machine; code never leaves. Optional cloud for convenience only. Fits the Ollama-lockdown / local-CC posture and is the honest wedge against any cloud competitor.

## Pricing (micro)
- Free: one-shot roast of a public repo or upload.
- Paid: private repos · longitudinal tracking ("are you closing more over time?") · team/org mode · the deep multi-agent dossier.

## Relation to Pre Atlas (why this is NOT scope drift)
- Pre Atlas's founding thesis = "behavioral governance through analysis." This is that thesis, pointed at git.
- `user_atlas_vision.md` already names the multi-tenant branch ("others get their own isolated instance via Aegis bones"). This is that branch, productized.
- The forensic engine already exists in this repo: `REPO_FORENSIC_TRACE_2026-06-26.md` + the `pre-atlas-forensic-dossier` workflow. The SaaS is that workflow, packaged.

## GATE (use Bruke's own CLOSURE rule on this idea)
Do not open a repo for this until BOTH are true:
1. The core Pre Atlas pipeline (delta-kernel · cognitive-sensor · contracts · projection loop) runs end-to-end autonomously (the original vision priority).
2. The unmerged-branch capsules are tagged + indexed in `CAPSULES.md`.

Rationale: building this now is the exact AI-driven scope-drift the dossier diagnosed and the vision note warned about. Capsule first. Close first. Then this is what you close *toward*.
