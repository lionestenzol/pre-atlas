# Codex Re-Review Round 6 · canvas-engine pattern-library trainer

You returned `verdict=warn, score=90` with two issues. Round 6 fixes both.

## Round 5 issues + my responses

### Issue 1 (MEDIUM) · ARIA cap routed to link, not button

**Your verdict:** "The new cap prevents `clickable/pill` from winning for compact `r9-aria-role` controls, but it does not make those controls resolve to `clickable/button`. For the stated regression shape (`detection='r9-aria-role'`, label `Save`, bounds `60x28`), pill is capped to 40, `clickable/button` scores only 50, but `clickable/link` gets the ARIA bonus and wins."

You're right — I capped pill but didn't route the residual to the right pattern. Real fix: give `clickable/button` an ARIA-button bump.

**My response · `services/canvas-engine/src/pattern-library/patterns/clickable-button.ts:8-15`:**

```ts
score(region) {
  let s = 50;
  const det = region.detection || '';
  if (det === 'r7-native-interactive') s += 30;
  if (det === 'r8-event-handler-attrs') s += 20;
  if (det === 'r9-aria-role') s += 35;     // NEW · routes ARIA button-likes to button
  if (region.bounds && region.bounds.w > 60 && region.bounds.w < 240 && region.bounds.h < 80) s += 10;
  return s;
}
```

For your concrete regression case (r9-aria-role, "Save", 60x28):
- pill: 100 → capped to 40
- link:  60 + 10 (r9) + 10 (h<36) = 80
- button: 50 + 35 (r9) + 0 (bounds w=60 not strict>60) = **85** ← winner

For wider ARIA buttons (e.g. 80x32):
- link:  60 + 10 + 10 = 80
- button: 50 + 35 + 10 = **95** ← winner

I noted in the comment that r9-aria-role currently flattens role=button + role=link + role=tab into one literal. The bump is currently a slight over-correction toward button (would route role=tab on a div to button). Once the producer distinguishes roles, this can be split into r9-button vs r9-link/tab.

### Issue 2 (LOW) · Regression test only asserted "not pill"

**Your verdict:** "The new regression test asserts only that the ARIA case is not classified as `clickable/pill`. That allows the same sample to regress to `clickable/link`, which is exactly what the current scoring implies."

**My response · `services/canvas-engine/test/pattern-library.test.ts:267`:**

Tightened the assertion from `not.toBe('clickable/pill')` to `toBe('clickable/button')`:

```ts
it('aria-role button-like compact controls route to clickable/button', () => {
  const r = region({
    detection: 'r9-aria-role',
    selector: 'div > div > div',
    name: 'Save',
    bounds: { x: 0, y: 0, w: 60, h: 28 },
  });
  expect(pickPattern(r, registry).pattern.name).toBe('clickable/button');
});
```

This now catches both the pill regression AND the link regression in a single assertion.

## Empirical state

```
Tests:  84/84 pass
Trainer:
  group truth          ·  100.0%   (532/532)   rigorous
  strict pattern truth ·  100.0%   (27/27)     rigorous
  heuristic pattern    ·   90.7%   (458/505)   informational only
```

Note: heuristic accuracy returned to 90.7% (was 90.5% in round 4) because the ARIA-button route helps a few of the previously-misclassified buttons land in the right bucket.

## Final review

1. With ARIA-button properly routed AND tested, are all consumer-side issues from rounds 1-5 now resolved?
2. Anything new you can think of that's *strictly within consumer-side scope*?
3. Is this `approve`-able now, or still `warn`? If warn, what's the remaining blocker that's NOT the deferred producer-side `#id` selector issue?
