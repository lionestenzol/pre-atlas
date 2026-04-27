# Codex Re-Review Round 5 · canvas-engine pattern-library trainer

You returned `verdict=warn, score=92` with one issue. Round 5 fix.

## Round 4 issue + my response

### Issue (MEDIUM) · Button-like ARIA controls bypass pill cap

**Your verdict:** "For a compact `div`/`span` with `detection='r9-aria-role'`, label `Save`, and bounds around `60x28`, `clickable/pill` still scores `100`."

**Suggested fix:** Cap pill when detection is `r9-aria-role` AND the region is compact short-label, OR boost button for ARIA controls.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-pill.ts:39-46`:**

Extended the cap: pill is capped at 40 when EITHER leaf is `<button>` OR detection is `r9-aria-role`:

```ts
const isButtonLike =
  leafTag(region.selector) === 'button' ||
  region.detection === 'r9-aria-role';
if (isButtonLike) s = Math.min(s, 40);
```

I noted in the comment that `r9-aria-role` is currently a single literal — once the producer distinguishes `role=button` from `role=link/tab`, the cap can be tightened to button-only ARIA. For now it's slightly over-broad (would penalize `<div role="tab">` styled as a pill), but that's a known small-volume trade-off — the dataset has only ~18 r9-aria-role regions across all captures.

**Added regression test** in `services/canvas-engine/test/pattern-library.test.ts`:
```ts
it('aria-role button-like compact controls do not win as pill', () => {
  // Regression for Codex round-4 finding
  const r = region({ ..., detection: 'r9-aria-role', name: 'Save', bounds: 60x28 });
  expect(pickPattern(r, registry).pattern.name).not.toBe('clickable/pill');
});
```

## Empirical state

```
Tests:  84/84 pass  (was 72 at start · +12 from rounds 1-4 audit)

Trainer:
  group truth          ·  100.0%   (532/532)   rigorous
  strict pattern truth ·  100.0%   (27/27)     rigorous
  heuristic pattern    ·   90.7%   (458/505)   informational only
```

## All round-1-through-4 issues resolved + tested

| Round | Issue | Fix | Regression test |
|---|---|---|---|
| 1 | Trainer was circular | Split STRICT/HEURISTIC reports | structural separation in trainer-vs-truth.mjs |
| 1 | isAnchorSelector matched ancestors | Made leaf-only | `a > span` → false test |
| 1 | Pill ≤8 + bare single-token loose | Tightened to ≤6 + structural check | "Documentation"/"Marketplace" tests |
| 2 | leafTag null on bare `#id`/`a.cta` selectors | Combinator-aware splitter | 9 leafTag/isAnchorSelector cases |
| 3 | Pill ≤6 still beat link on `Search`/`People` | Added tightPillGeometry gate | "Pricing"/"Support" non-pill tests |
| 4 | Save/Back/Login on `<button>` leaf still won pill | Cap pill on button leaf | Save/Back/Next/Login pick-button test |
| 5 | r9-aria-role on div/span still won pill | Extend cap to ARIA | aria-role pill-cap test |

## Open producer-side issue (deferred per round 3, untouched)

ID-only leaf selectors (4.7% of regions). Documented in TRIAGE-2026-04-26.md. Producer fix needed.

## Final review questions

1. With the ARIA cap in place, are all consumer-side false-positive classes you've identified now covered or capped?
2. Can the verdict move to `approve` for the consumer-side scope, with the deferred producer issue tracked separately?
3. Any new issues you can think of *strictly within the consumer-side bundle* (canvas-engine pattern-library + trainer)?
