# Codex Re-Review Round 3 · canvas-engine pattern-library trainer

You returned `verdict=warn, score=89` with two issues. Round 3 addresses both.

## Round 2 issues + my responses

### Issue 1 (HIGH) · `leafTag()` returned null for ID-only selectors

**Your verdict:** "`leafTag()` still returns `null` for ID-only selectors like `#checkout` or `#search`, but the producer emits exactly that shape whenever an element has a valid `id`."

**Suggested fix:** Stop emitting bare `#id` from buildSelector(), or extend the region payload with explicit leaf tag.

**My response — empirical check + scoping decision:**

I queried all 1002 regions across the .canvas captures. **47 (~4.7%) have ID-only leaf selectors** — examples:
- `#main` (placeholder)
- `#Navigation_id_STORE`
- `#Dashboard_id_DASHBOARD`

You're right that these miss tag-based features (anchor leaf-bump, group overrides). But the fix is in the producer (`tools/anatomy-extension/lib/util.js` buildSelector), not the consumer. Changing the producer requires:
1. Edit anatomy extension's buildSelector() to always include tag (`a#docs-link` not `#docs-link`)
2. Re-pull all calibration captures so old data conforms

**I am intentionally deferring this to a separate session** because:
- It's a producer-side change in a different repo (`tools/anatomy-extension/`)
- It requires re-pulling captures via Chrome session (out of band)
- The current consumer behavior is graceful: 4.7% of regions fall through to detection-based routing (which is still group-correct, just misses sub-pattern tag refinement)

I've added this as a known gap in `tools/codex-partner/runs/TRIAGE-2026-04-26.md`. Treat as a deferred-fix, not a blocker for this consumer-side review.

### Issue 2 (MEDIUM) · `nameLength <= 6` still too broad as a standalone signal

**Your verdict:** "Compact nav/tab labels such as `Search`, `People`, `Orders`, `About`, `Docs`, or `Teams` will still score as pills and can beat `clickable/link` at 100 vs 95."

**Suggested fix:** Require an additional badge-like cue for alphabetic words. Gate length behind stronger geometry or detection evidence.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts:7-44`:**

Took your second suggestion: gate length behind tighter geometry. The new scorer:

```ts
const isStrongBadgeText =
  /^[A-Z][A-Z0-9]*$/.test(name) ||      // BETA, AI, ML
  /^[\d+\-*#%]+$/.test(name);           // +5, 99%, 1234
const isShortAlpha = nameLength <= 6;    // Active, Beta, About

const compact          = w >= 30 && w <= 150 && h < 36;   // generic compact
const tightPillGeometry = w >= 28 && w <= 80 && h <= 28;  // pill-only tight

// Strong pill = badge text + compact, OR short alpha + tight geometry
if ((isStrongBadgeText && compact) || (isShortAlpha && tightPillGeometry)) return 100;
```

Coverage check against your concern set, assuming typical nav-link bounds (~80x32 or 90x36):
- "Search" 80x32 — isShortAlpha ✓, tightPillGeometry: h=32 NOT ≤28 ✗. isStrongBadgeText (S+earch) ✗. → 25 (loses to link 95). ✓
- "People" 80x32 — same path. ✓
- "Orders" 80x32 — same. ✓
- "About" 70x32 — same. ✓
- "Docs" 60x32 — same. ✓
- "Teams" 70x32 — same. ✓
- "Active" 70x28 (existing test) — isShortAlpha ✓, tightPillGeometry (28≤70≤80, 28≤28) ✓ → 100. ✓ (existing pill test still passes)
- "BETA" 50x20 — isStrongBadgeText ✓, compact ✓ → 100. ✓
- "+5" 30x18 — isStrongBadgeText ✓, compact (30≥30, 18<36) ✓ → 100. ✓
- "Beta" 35x18 — isShortAlpha ✓, tightPillGeometry (28≤35≤80, 18≤28) ✓ → 100. ✓
- "Documentation" (13 chars, your earlier example) — fails all signals → 10. ✓

Real-world impact on the 1226-region test corpus: pill fires dropped from previous round, but the 100% rigorous metrics held. Heuristic accuracy moved 90.7% → 90.5% (negligible · the heuristic report is opinion-vs-opinion anyway).

## Empirical state

```
GROUP-LEVEL ACCURACY                  100.0%   (532/532)   rigorous
STRICT PATTERN ACCURACY (7 tags)      100.0%   (27/27)     rigorous
HEURISTIC PATTERN REPORT               90.5%   (457/505)   informational only
```

81/81 vitest tests pass.

## What I want from this final review

1. Is the new pill scorer's geometry gate sufficient to address Issue 2, or do you see another false-positive class?
2. Is my decision to defer the producer-side ID-only selector fix to a separate session (with a TRIAGE entry) reasonable?
3. Can you upgrade the verdict from `warn` if the consumer-side scope is clean? Or if not, what specifically blocks an `approve`?
