# Task: Verify Signal Round Trip

## Objective
Verify end-to-end: trigger path → Optogon → CloseSignal → Atlas → Signal → today.html.

## Requirements
- All services running: delta-kernel :3001, optogon :3010, inpact :3006
- Path completes; CloseSignal posted to /api/atlas/close-signal
- Atlas emits completion Signal; today.html renders it

## Implementation Steps
1. Run all services
2. Trigger ship_inpact_lesson from today.html
3. Walk the path to close
4. Verify completion Signal appears in today.html within 30s

## Definition of Done
- [ ] Full round trip succeeds without manual intervention
- [ ] Screenshots saved as proof
