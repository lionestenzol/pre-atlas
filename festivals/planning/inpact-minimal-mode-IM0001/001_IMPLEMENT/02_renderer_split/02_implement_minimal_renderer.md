---
fest_type: task
fest_id: 02_implement_minimal_renderer.md
fest_name: implement-minimal-renderer
fest_parent: 02_renderer_split
fest_order: 2
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:19.7742843-05:00
fest_tracking: true
---

# Task: implement-minimal-renderer

## Objective

`renderDailyMinimal(plan)` — the act-now lens. Read-only on everything the morning ritual
decided; the only writes are the ones made while executing.

## Requirements

- [x] Shows: NOW block, active routine + steps, TODAY COUNTS IF, TOP 3, THE LEVER,
      RESET MOVE, NEXT block, daily PROGRESS, `[ Open Full Plan ]`
- [x] TOP 3 / LEVER / RESET MOVE are read-only
- [x] Empty-plan routing instead of an empty execution lens
- [x] Hides: Atlas Backbone, planning questions, PIGPEN selectors, task-link dropdowns,
      add/delete block controls, journal/reflection forms, contingencies

## Implementation

`apps/inpact/js/screens.js:735-847`.

Reads only existing state: `getTodayFields()` for winTarget/p1-3/lever/resetMove,
`Helpers.calculateDailyProgress()` for the progress line, and the four new helpers for
block/routine selection. Sections render conditionally, so an unfilled field costs no space.

Writes reuse existing handlers — `toggleTimeBlockCompletion()` (`functions.js:498`) and
`toggleRoutineStep()` (`functions.js:1031`). No parallel write path.

**Atlas Backbone required a real fix, not just omission.** `backbone.js` mounts
`<section id="atlas-backbone">` at `afterbegin` of the shared container and a MutationObserver
re-mounts it on every screen swap (`apps/inpact/js/backbone.js:79`), so the renderer cannot
out-render it. Measured live: it pushed `.ip-minimal` to `top: 1615px` — the NOW block was
below the fold, which defeats the lens. Fixed at the source in
`apps/inpact/js/backbone.js:63-71`: a `suppressed()` check makes the backbone stay out of
Daily/minimal and remove any stale copy. After the fix `.ip-minimal` sits at `top: 73px`.

`activateResetMove()` (`functions.js:2843`) is new: reset move was display-only text with no
activation path anywhere in the app. It logs to the existing `History.timeline` via
`Helpers.logActivity` — no new data model.

## Done When

- [x] LIVE PROOF (mobile 375x812) — NOW = "Evening Routine", routine "Evening 1/4 steps"
      with the done step struck through, TODAY COUNTS IF, TOP 3, lever, reset move, next,
      progress, Open Full Plan. Screenshot captured.
- [x] LIVE PROOF — hidden set measured inside `.ip-minimal`: backbone absent, 0 text
      inputs/textareas, 0 selects, no "Add block", 0 `removeTimeBlock` controls, no Contingencies
- [x] LIVE PROOF — "Mark done" flipped the current block false->true and progress recomputed
      "Blocks 2/4 . Overall 18%" -> "Blocks 3/4 . Overall 26%"
- [x] LIVE PROOF — reset move click appended one `reset_move_used` entry to History.timeline
- [x] LIVE PROOF — `time_blocks: []` renders `.ip-minimal-empty` with a "Plan your day" CTA
      and no NOW card
