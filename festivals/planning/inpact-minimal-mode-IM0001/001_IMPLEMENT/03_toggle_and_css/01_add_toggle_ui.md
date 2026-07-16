---
fest_type: task
fest_id: 01_add_toggle_ui.md
fest_name: add-toggle-ui
fest_parent: 03_toggle_and_css
fest_order: 1
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:19.8960343-05:00
fest_tracking: true
---

# Task: add-toggle-ui

## Objective

Persistent `[ Minimal ] [ Full Plan ]` toggle inside the Daily header, on both lenses.

## Requirements

- [x] Toggle renders in both Minimal and Full
- [x] Writes `state.UI.dailyView` and re-renders
- [x] Survives reload

## Implementation

`_dailyViewToggle(active)` at `apps/inpact/js/screens.js:311-321`, next to `_bridges()` —
called from `renderDailyFull` (above the `<h1>`) and from `renderDailyMinimal` (both the
normal and empty-plan branches).

Reuses the app's existing toggle idiom `.td-btn-pill` + `.active`
(`apps/inpact/css/tokens.css:503-516`) rather than inventing a new button class. Carries
`aria-pressed` for the pressed state.

`setDailyView(view)` at `apps/inpact/js/functions.js:2843` validates the value, lazily
creates `state.UI`, then `stateManager.update({ UI: state.UI })` + `render()`. Exported at
`functions.js:3007` alongside the other window-scoped handlers.

Note: `stateManager.update()` saves through a 1000ms debounce (`state.js:345`), so
persistence is not observable synchronously after a click — it is real, just delayed.

## Done When

- [x] LIVE PROOF — clicking "Full Plan" sets `state.UI.dailyView='full'`, removes
      `.ip-minimal`, restores the planning inputs; clicking "Minimal" restores `.ip-minimal`
- [x] LIVE PROOF — after the debounce, localStorage holds `UI.dailyView='full'`; a real
      `location.reload()` came back up in Full and rendered Full
