# Codex Review Request · canvas-engine pattern-library trainer

## What I built (this session)

The canvas-engine pattern library (services/canvas-engine/src/pattern-library/) classifies anatomy.json regions into 7 groups (clickable, heading, landmark, card, list, form, default) and 23 concrete patterns (clickable/link, clickable/button, heading/hero, etc) for rendering React clones.

I added a self-grading "trainer" that uses **the leaf tag in each region's selector path as independent ground truth** to grade the picker. The key insight: the producer-side cascade can lossy-flatten detection labels (r7-native-interactive covers `<a>`, `<button>`, `<input>`, `<textarea>` all the same), but the DOM tag in the selector path is browser-emitted and cannot be lied about.

**Files I want reviewed:**

1. `services/canvas-engine/test/trainer-vs-truth.mjs` — NEW · grades picker against leaf-tag truth at both group level and pattern level (sub-patterns)
2. `services/canvas-engine/src/pattern-library/normalize.ts` — added TAG_OVERRIDES that route input/textarea/select → form, ul/ol → list based on selector leaf tag (overriding any detection-based routing)
3. `services/canvas-engine/src/pattern-library/util.ts` — added `isAnchorSelector()` helper (matches `> a` anywhere in the path)
4. `services/canvas-engine/src/pattern-library/patterns/clickable-link.ts` — added `+35` score bump when isAnchorSelector(selector) is true
5. `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts` — rewrote scorer to require pill-text signal (≤8 chars OR single-token OR numeric/symbolic) before awarding the "perfect match" 100 score · previously any short name + compact bounds got 100, which made pill the default-winner

**Empirical results (1226 total regions, 532 decidable, 13 captures):**

```
Group-level accuracy:    100.0%   (532/532) on five groups
Pattern-level accuracy:   90.0%   (479/532)
  clickable/link        86.9%   (344/396 fires acceptable)
  clickable/button      97.4%   (38/39 fires acceptable)
  All other patterns   100.0%

Mistake categories the trainer surfaced:
  46 × <a>      picked clickable/link    (some should be cta, some icon-button)
   6 × <button> picked clickable/link    (should be button)
   1 × <button> picked clickable/button  (should be icon-button)
```

72/72 vitest tests still pass after my changes.

## What I want you to evaluate

1. **Methodology · is the leaf-tag-as-truth approach sound?**
   - Does grading the picker against an independent label (selector tag) actually constitute "training"?
   - The trainer's truth function `acceptablePatterns()` in trainer-vs-truth.mjs encodes *my* opinion of what each tag should map to. Does that contaminate the audit (turning it into self-confirmation)?
   - Could the 90% sub-pattern number be misleading — e.g. is the truth function too lenient by allowing multi-element acceptable sets ({link, pill}) for stylistically-flexible cases?

2. **Rule additions · are they clean or hacky?**
   - TAG_OVERRIDES in normalize.ts (input → form, ul → list) — is this trustworthy or does it short-circuit signals the picker would have used productively?
   - `isAnchorSelector` regex `\>\s*a(?=$|[\s>:.\[#])` — does this correctly distinguish anchor leaves from `<a>` in the middle of a path? Edge cases?
   - The `+35` anchor bump in clickable-link.ts is a magic number tuned to overcome button's `r7+30 +bounds+10 = 90` ceiling. Is there a cleaner formulation?
   - Pill scorer's `isPillText` check — `nameLength <= 8 || /^\S+$/.test(name) || /^[\d+\-*#%]+$/.test(name)` — is the "single-token always counts" branch too permissive? It would accept "Documentation" as pill-text.

3. **Calibration · over-fit risk**
   - I tuned scorers based on what the trainer surfaced from existing on-disk captures. Did I over-fit to specific sites (HN/Linear/Figma)?
   - The trainer's truth function was hand-written based on spot-checking these same captures. Is that circular?

4. **Soundness of the loop**
   - The pitch is: future cascade changes get auto-graded against a growing truth set. Each new pull strengthens the corpus. Is this reasoning correct, or are there failure modes (e.g. truth function rotting as capture vocabulary evolves)?

## Out of scope

- Don't review the producer-side anatomy extension cascade rules (different repo concern).
- Don't ask for new tests — vitest passes 72/72.
- Don't suggest unrelated refactors.

Be concrete. If you flag an issue, point at the specific file:line and propose a specific replacement. Mark severity honestly — only "high" or "critical" if there's a real correctness or methodological problem.
