---
fest_type: task
fest_id: 02_add_time_block_helpers.md
fest_name: add-time-block-helpers
fest_parent: 01_state_and_helpers
fest_order: 2
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:09.8439023-05:00
fest_tracking: true
---

# Task: add-time-block-helpers

## Objective

Add the derivation helpers Minimal Mode needs, reading only existing DayPlan/Routine
state. No new data model.

## Requirements

- [x] `getCurrentTimeBlock(plan)` — the block you're inside now; `null` before the first
- [x] `getNextTimeBlock(plan)` — the next block that hasn't started
- [x] `getActiveRoutine(plan)` — routine on the current block, with step progress
- [x] `isPlanReady(plan)` — does the plan have any time blocks

## Implementation

Added to `apps/inpact/js/helpers.js:266-330`, after `getAverageProgress()`.

**Key finding that shaped this task.** `block.time` is stored in TWO formats:
- seeded blocks use 12-hour text: `'6:00 AM'` (`apps/inpact/js/state.js:68`)
- blocks edited via `input[type=time]` store 24-hour: `'13:00'` (`apps/inpact/js/screens.js:619`)

A naive `parseInt(block.time.split(':')[0])` reads `'3:00 PM'` as hour 3 and sorts the
afternoon before the morning, so NOW would pick the wrong block. The app already has the
canonical normalizer for both shapes — `convertTo24Hour()` at
`apps/inpact/js/functions.js:297` — so `_blockMinutes()` builds on it rather than adding
a second parser.

Supporting privates: `_blockMinutes(block)`, `_sortedBlocks(plan)` (copies before sorting,
per the immutability rule), `_nowMinutes()`.

`getActiveRoutine` reuses `_findRoutineMatch()` (`apps/inpact/js/screens.js:304`) so
Minimal and Full can't drift on what counts as a routine match.

NOT added: `getDailyProgress(plan)` from the original spec. `Helpers.calculateDailyProgress()`
(`apps/inpact/js/helpers.js:67`) already returns exactly that shape; a second one would be a
duplicate. The renderer calls the existing helper.

## Done When

- [x] All four helpers exist in `apps/inpact/js/helpers.js` and `node --check` passes
- [x] LIVE PROOF (browser, real state) — parser handles every trap:
      `6:00 AM`=>360, `3:00 PM`=>900, `12:45 PM`=>765, `12:30 AM`=>30, `17:00`=>1020, `09:15`=>555
- [x] LIVE PROOF — mixed-format plan `['6:00 AM','3:00 PM','17:00','6:00 PM']` sorts in that
      order; at 17:xx `getCurrentTimeBlock` = "Evening Routine" (17:00),
      `getNextTimeBlock` = "Shutdown / Review" (18:00), `getActiveRoutine` = "Evening 1/4"
- [x] LIVE PROOF — with `time_blocks: []`, `isPlanReady` = false and `getCurrentTimeBlock` = null
