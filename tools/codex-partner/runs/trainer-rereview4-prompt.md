# Codex Re-Review Round 4 · canvas-engine pattern-library trainer

You returned `verdict=warn, score=91` with one issue. Round 4 fix.

## Round 3 issue + my response

### Issue (MEDIUM) · Compact short-label buttons still win as pills

**Your verdict:** "A `button` or `r7-native-interactive` region named `Save` with bounds around `60x28` satisfies `isShortAlpha && tightPillGeometry` and returns `100`, while `clickable/button` tops out at `90`. That means short action buttons can still be rendered as rounded tag/badges."

**Suggested fix:** Exclude leaf-tag `button`/button-like detections from the `100` path · OR raise `clickable/button` when the selector leaf is `button`.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts:35-39`:**

Took your first option — cap pill score when leaf tag is `<button>`. Cleaner than a button-side bump because it directly enforces DOM truth: real `<button>` elements never render as pills.

```ts
let s: number;
if ((isStrongBadgeText && compact) || (isShortAlpha && tightPillGeometry)) s = 100;
else if (isShortAlpha || isStrongBadgeText) s = 25;
else if (compact) s = 40;
else s = 10;

// Real <button> elements should render as button, not pill
if (leafTag(region.selector) === 'button') s = Math.min(s, 40);
return s;
```

Trace through your concrete examples:

| Region | bounds | selector leaf | pill score | button score | result |
|---|---|---|---|---|---|
| `Save`  | 60x28 | `button` | 40 (capped) | 90 | button wins ✓ |
| `Back`  | 60x28 | `button` | 40 (capped) | 90 | button wins ✓ |
| `Next`  | 60x28 | `button` | 40 (capped) | 90 | button wins ✓ |
| `Login` | 80x32 | `button` | 40 (capped) | 80 | button wins ✓ |
| `BETA`  | 50x20 | `span` (no cap) | 100 | n/a | pill wins ✓ |
| `Active` 70x28 | (existing test, no selector → no cap) | 100 | n/a | pill wins ✓ |

**Added regression tests** in `services/canvas-engine/test/pattern-library.test.ts`:

- `compact short-label <button> picks clickable/button, not clickable/pill` — covers Save/Back/Next/Login at 60x28 with `button` leaf selector
- `long single-token nav labels do not win as pill` — covers Pricing/Support/Security/Documentation/Marketplace at 90x32 (round 2 regression)

## Empirical state

```
Tests:  83/83 pass  (was 72 at start of audit · +11 from new util/regression suites)

Trainer rerun:
  group truth          ·  100.0%   (532/532)   rigorous
  strict pattern truth ·  100.0%   (27/27)     rigorous
  heuristic pattern    ·   90.5%   (457/505)   informational only
```

## Open producer-side issue (deferred per round 3)

ID-only leaf selectors (`#main`, `#Navigation_id_STORE`) — 47 of 1002 regions (~4.7%) — still miss tag-based features because the producer's `buildSelector()` in `tools/anatomy-extension/lib/util.js` strips the tag when an `id` is present. **Deferred to a separate session** since it requires:
- An extension code change (different repo)
- A re-pull of all calibration captures via Chrome session

Documented in `tools/codex-partner/runs/TRIAGE-2026-04-26.md` as a known consumer-side gap, not a blocker.

## What I want from this final review

1. Are the consumer-side issues from rounds 1-3 (circularity, ancestor-anchor, single-token pill, button-leaf pill) all resolved?
2. Any new false-positive class you can think of *within the consumer-side scope*?
3. Update verdict + score. Is this `approve`-able now, or does the deferred producer issue still cap it at `warn`?
