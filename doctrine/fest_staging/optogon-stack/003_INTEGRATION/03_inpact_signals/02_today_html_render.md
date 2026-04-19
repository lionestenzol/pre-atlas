# Task: Today Html Render

## Objective
Add apps/inpact/js/signals.js + today.html block to render Signals.

## Requirements
- Reuse existing today.html ls-* blocks (per feedback_one_lesson_template.md)
- Light theme only (per locked design)
- No em dashes in any rendered text (per feedback_no_em_dashes_in_ui.md)
- Polls /api/signals every 30s with exponential backoff

## Implementation Steps
1. Author signals.js — fetch + render loop
2. Add signal feed block to today.html using existing classes
3. Verify in browser via preview_start name='inpact'

## Definition of Done
- [ ] Signals visible in today.html when present
- [ ] preview_inspect confirms light theme styling
- [ ] No em dashes in rendered output
