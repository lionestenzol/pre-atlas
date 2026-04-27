# Codex Re-Review Round 2 · canvas-engine pattern-library trainer

You returned `verdict=warn, score=87` with two issues. Both fixed in this round.

## Your previous issues + my responses

### Issue 1 (HIGH) · `leafTag()` regex required `>` prefix

**Your verdict:** "`leafTag()` only matches tags that are preceded by `>`. Bare/simple selectors like `a`, `a.cta`, `header.site-header`, `form.search`, and `header` return `null`."

**My response · `services/canvas-engine/src/pattern-library/util.ts:10-32`:**

Replaced the regex-based finder with a combinator-aware splitter. Now handles:

```ts
export function leafTag(selector: string | undefined): string | null {
  if (!selector) return null;
  // Split on combinators · `>`, `+`, `~`, or runs of whitespace
  const segments = selector.trim().split(/\s*[>+~]\s*|\s+/);
  const last = segments[segments.length - 1] || '';
  const m = /^([a-zA-Z][a-zA-Z0-9-]*)/.exec(last);
  return m ? m[1].toLowerCase() : null;
}
```

Added comprehensive vitest coverage in `services/canvas-engine/test/util.test.ts`:
- bare/single-segment: `a`, `a.cta`, `header`, `header.site-header`, `form.search`, `button:hover`
- `>` paths: `nav > a`, `td > a > span`, `td > a:nth-of-type(2)`
- descendant whitespace: `nav a`, `main article h2`
- `+` and `~` combinators: `h1 + p`, `h1 ~ p.note`
- null cases: `.foo > .bar`, `[type=button]`, `#main`, `''`, `undefined`

`isAnchorSelector` is also tested directly to confirm leaf-only behavior:
- `'a > span'` returns `false` (ancestor anchor, leaf is span)
- `'a > div > button'` returns `false`

72 → 81 tests, all green.

### Issue 2 (MEDIUM) · Pill scorer's `nameLength <= 8` was still too loose

**Your verdict:** "`nameLength <= 8` is still broad enough to classify many short nav labels (`Pricing`, `Support`, `Security`, `Platform`) as pill text. If those regions are compact, `clickable/pill` still gets 100 and can beat `clickable/link`'s 95."

**Suggested fix:** Require additional pill-specific signal beyond length alone.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts:13-21`:**

Tightened length cap from ≤8 to ≤6, AND added two specific signals:

```ts
const isPillText =
  nameLength <= 6 ||
  /^[A-Z][A-Z0-9]*$/.test(name) ||      // BETA, NEW, PRO, AI, ML
  /^[\d+\-*#%]+$/.test(name);            // +5, 1234, 99%
```

Coverage check against your concern set:
- "Pricing" (7) — fails all three. Pill loses to link. ✓
- "Support" (7) — fails all three. ✓
- "Security" (8) — fails all three. ✓
- "Platform" (8) — fails all three. ✓
- "Active" (6) — passes ≤6. ✓ (existing test still picks pill)
- "Beta" (4) — passes ≤6. ✓
- "BETA" (4) — also passes all-caps branch. ✓
- "+5" — passes numeric/symbolic. ✓

The existing pill test (`Active` at 70x28) still picks clickable/pill (length 6 satisfies the ≤6 branch).

## Empirical results after both fixes

```
GROUP-LEVEL ACCURACY                  100.0%   (532/532)   rigorous
STRICT PATTERN ACCURACY (7 tags)      100.0%   (27/27)     rigorous
HEURISTIC PATTERN REPORT               90.7%   (458/505)   informational only
```

81/81 vitest tests pass.

## What I want from this review

1. Is `leafTag()` correctness now sound across the cases you flagged? Any new edge cases?
2. Is the pill scorer's signal set tight enough, or do you see further false-positive classes?
3. Are there any *new* issues introduced by the rewrite?
4. Update verdict + score.
