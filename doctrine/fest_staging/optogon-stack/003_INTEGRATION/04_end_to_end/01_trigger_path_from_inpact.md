# Task: Trigger Path From Inpact

## Objective
Add 'Run path' control to today.html that triggers Optogon path execution.

## Requirements
- Lists paths from GET /paths on Optogon (:3010)
- Click → POST /session/start with selected path_id
- Returns session_id; track in localStorage

## Implementation Steps
1. Add path-runner block to today.html using ls-* classes
2. Author paths.js to fetch + start sessions
3. Render running session inline (status from GET /session/{id})

## Definition of Done
- [ ] Click on ship_inpact_lesson starts a session and shows status
