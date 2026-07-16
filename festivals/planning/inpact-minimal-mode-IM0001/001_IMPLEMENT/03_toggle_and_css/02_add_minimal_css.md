---
fest_type: task
fest_id: 02_add_minimal_css.md
fest_name: add-minimal-css
fest_parent: 03_toggle_and_css
fest_order: 2
fest_status: complete
fest_autonomy: medium
fest_created: 2026-07-16T16:48:19.9091936-05:00
fest_tracking: true
---

# Task: add-minimal-css

## Objective

Mobile-first CSS for the Minimal lens: one viewport, sticky NOW, 44px controls.

## Requirements

- [x] Sticky NOW header
- [x] All interactive controls >= 44px
- [x] Mobile-first single column
- [x] Matches existing token conventions

## Implementation

Appended to `apps/inpact/css/tokens.css:861-1031`, using the file's existing
`var(--ip-*)` tokens and rem sizing.

- `.ip-now` — `position: sticky; top: 0`, inverted black card so NOW reads first
- 44px (`2.75rem`) min-height on `.ip-now-check`, `.ip-min-step`, `.ip-min-reset`,
  `.ip-minimal-open`, and the toggle pills
- `.ip-minimal` capped at `32rem`, single column
- `.ip-min-card` for the read-only cards; `.ip-min-next` dashed to read as not-yet
- `.ip-minimal-empty` for the empty-plan branch

Per Atlas UI law, no em dashes in any of the rendered strings — separators are `.` and `·`.

## Done When

- [x] LIVE PROOF (mobile 375x812) — measured heights: `.ip-now-check` 44px,
      `.ip-min-step` 44px, `.ip-min-reset` 44px, `.ip-minimal-open` 44px,
      toggle pill 44px. All exactly at the 44px floor.
- [x] LIVE PROOF — with the backbone suppression in place `.ip-minimal` renders at
      `top: 73px`; NOW is the first thing on screen. Screenshot captured.
