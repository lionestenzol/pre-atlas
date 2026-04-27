# Codex Re-Review · canvas-engine pattern-library trainer (post-fix)

You previously reviewed this work and returned `verdict=warn, score=84` with three medium-severity issues. I applied all three. Please re-grade the same scope and confirm whether the issues are resolved.

## Your previous issues + how I responded

### Issue 1 · Trainer was partially circular

**Your verdict:** "`acceptablePatterns()` is presented as independent ground truth, but for sub-pattern grading it reuses policy heuristics that overlap with the scorer logic... That makes the 90% pattern-level number partially circular and likely inflated."

**Suggested fix:** Treat leaf tag as independent truth only for group-level and the small set of sub-patterns determined directly by tag. For stylistic variants, mark them undecidable or move them into a separate explicitly-heuristic report.

**My response · `services/canvas-engine/test/trainer-vs-truth.mjs` (full rewrite):**

The trainer now has **three structurally separate reports**:

1. **GROUP-LEVEL ACCURACY** — deterministic, leaf tag determines group. Rigorous.
2. **STRICT PATTERN ACCURACY** — uses a new `TAG_TO_PATTERN_STRICT` map that contains *only 7 entries* where the leaf tag uniquely determines a single pattern: `header→landmark/header`, `nav→landmark/nav`, `footer→landmark/footer`, `aside→landmark/aside`, `section→landmark/section`, `main→landmark/section`, `h1→heading/hero`. Rigorous.
3. **HEURISTIC PATTERN REPORT** — explicitly labeled "stylistic variants · NOT a truth metric · use only to surface confusion buckets." For tags where multiple patterns are valid (a, button, h2-6, ul, ol, form, input, article).

The previous "90% pattern accuracy" claim has been replaced with two distinct numbers:
- 100.0% strict-truth (27/27)
- 90.7% heuristic (458/505) · clearly labeled as informational

Look at the SUMMARY section at the bottom of the trainer output — three lines, two marked "rigorous", one marked "informational only".

### Issue 2 · isAnchorSelector matched ancestor anchors

**Your verdict:** "`isAnchorSelector()` matches `> a` anywhere in the selector path... `clickable/link` then gets a +35 boost for non-anchor leaves nested inside anchors."

**Suggested fix:** Make leaf-only via `leafTag(selector) === 'a'`.

**My response · `services/canvas-engine/src/pattern-library/util.ts:10-30`:**

Added a shared `leafTag()` helper and rewrote `isAnchorSelector`:

```ts
const LEAF_TAG_RE = /\>\s*([a-zA-Z][a-zA-Z0-9-]*)(?:[:.\[#]|$)/g;

export function leafTag(selector: string | undefined): string | null {
  if (!selector) return null;
  let last: string | null = null;
  for (const m of selector.matchAll(LEAF_TAG_RE)) last = m[1].toLowerCase();
  return last;
}

export function isAnchorSelector(selector: string | undefined): boolean {
  return leafTag(selector) === 'a';
}
```

Strictly leaf-only — does NOT match `... > a > span`. Also consolidated `normalize.ts` to import this same helper instead of maintaining its own inline copy (`services/canvas-engine/src/pattern-library/normalize.ts:8`).

**Empirical confirmation:** Before this fix the trainer reported `6 × <button> picked clickable/link · score=105` (Linear's "Social media · 2", "AI · 2", "Agents · 2"). Those mistakes are now zero — the phantom +35 boost no longer fires on `<button>` leaves whose path contains an ancestor anchor.

### Issue 3 · Pill scorer was too permissive on single tokens

**Your verdict:** "The `^\S+$` branch makes any single-token label count as pill text, so compact single-word labels like `Documentation`, `Integrations`, or `Marketplace` still receive the perfect-match 100 score."

**Suggested fix:** Tighten the signal — bound by length or require additional pill-like evidence.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts:13-18`:**

Dropped the bare single-token branch entirely. The pill-text signal is now:

```ts
const isPillText =
  nameLength <= 8 ||
  /^[\d+\-*#%]+$/.test(name);
```

Pure length cap (≤8) plus numeric/symbolic literals. "Documentation" (13), "Marketplace" (11), "Integrations" (12) all fail. "Beta" (4), "New" (3), "+5" still match.

## What I want you to evaluate

Re-grade the same scope. Specifically:

1. Is the trainer still vulnerable to circularity, or has the structural split into strict/heuristic genuinely fixed it? Look at how the `SUMMARY` section reports two rigorous numbers separately from one informational number.
2. Is `isAnchorSelector` now correctly leaf-only? Any remaining edge cases?
3. Is the pill scorer's new `isPillText` definition tight enough, or still too permissive?
4. Did I introduce any new issues in the rewrite that weren't present before?

72/72 vitest tests still pass.

Be concrete. Update your verdict and score. If new issues appear, flag them.
