# Task: Run Ship Inpact Lesson Twice

## Objective
Execute ship_inpact_lesson twice and capture metrics for both runs.

## Requirements
- Run 1: cold start (no preferences)
- Run 2: after Run 1 close signal processed
- Capture: questions_asked, tokens_used, time_to_close per run

## Implementation Steps
1. Wipe sessions.db before Run 1
2. Execute Run 1 end-to-end; record metrics
3. Execute Run 2 with preference store warm

## Definition of Done
- [ ] Both runs reach status=completed
- [ ] Metrics captured to a markdown table
