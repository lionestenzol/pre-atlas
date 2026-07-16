---
fest_type: task
fest_id: 01_add_state_ui_key.md
fest_name: add-state-ui-key
fest_parent: 01_state_and_helpers
fest_order: 1
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:09.7584525-05:00
fest_tracking: true
---

# Task: add-state-ui-key

## Objective

Add `UI: { dailyView: 'minimal' }` to `getDefaultState()` and a migration guard in
`loadFromStorage()` so existing users without the key get it on next load.

## Requirements

- [x] `state.UI.dailyView` exists in default state with value `'minimal'`
- [x] Migration guard in `loadFromStorage()` adds `UI` for saved states that lack it

## Implementation

1. `apps/inpact/js/state.js:160` — added `UI: { dailyView: 'minimal' }` as the last
   key of the `getDefaultState()` return, after `calendarDate`.
2. `apps/inpact/js/state.js:256-258` — added the migration guard after the
   `DayTypeTemplates` guard, matching the existing `if (!this.state.X) { ... }` idiom.

## Done When

- [x] `grep -n "dailyView" apps/inpact/js/state.js` returns two hits: line 160
      (`getDefaultState`) and line 257 (`loadFromStorage`). Both set `'minimal'`.
- [x] LIVE PROOF: a pre-existing saved state (written before this change) was read
      back in the browser as `{hasUI: true}` — the migration guard fired on real
      persisted data, not a fresh default.
