---
fest_type: task
fest_id: 01_split_daily_renderer.md
fest_name: split-daily-renderer
fest_parent: 02_renderer_split
fest_order: 1
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:19.6797893-05:00
fest_tracking: true
---

# Task: split-daily-renderer

## Objective

Make `ScreenRenderers.Daily()` a dispatcher over two lenses, leaving the existing
Full Plan renderer behaviourally unchanged.

## Requirements

- [x] `Daily()` dispatches on `state.UI.dailyView`
- [x] Full Plan renderer is unchanged apart from gaining the toggle
- [x] Defaults to Minimal when `state.UI` is absent

## Implementation

`apps/inpact/js/screens.js:494-503` — `Daily()` now reads the plan once and dispatches:
`state.UI?.dailyView === 'full' ? this.renderDailyFull(plan) : this.renderDailyMinimal(plan)`.
Optional chaining means a state without `UI` falls through to Minimal rather than throwing.

The former 230-line `Daily()` body became `renderDailyFull(todayPlan)` — same method object,
plan now a parameter instead of a local `Helpers.getDayPlan()` call. No markup changed except
the added `${_dailyViewToggle('full')}` above the `<h1>`.

Kept as sibling methods on `ScreenRenderers` (not top-level functions) so the 230-line body
did not have to move out of the object literal — a pure rename plus a dispatcher, which keeps
the diff reviewable.

## Done When

- [x] `node --check apps/inpact/js/screens.js` passes
- [x] LIVE PROOF — `state.UI.dailyView='full'` renders the Full Plan (h1 "Daily Plan",
      winTarget input present, `.ip-minimal` absent); `'minimal'` renders `.ip-minimal`
      with the planning inputs gone. Both directions verified via the real toggle buttons.
