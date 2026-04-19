# Task: Queue Update On Close

## Objective
On CloseSignal receive: mark task complete, update queue, write decisions to cognitive map.

## Requirements
- Mark task with id matching CloseSignal.path_id (or matching task_id) as completed
- Add CloseSignal.decisions_made to long-term cognitive map (cognitive-sensor)
- Re-score queue per existing leverage logic
- Process unblocked array as advisory hints

## Implementation Steps
1. Implement handleCloseSignal() in delta-kernel
2. Persist decisions via cognitive-sensor write API

## Definition of Done
- [ ] Task moves from queue → completed table
- [ ] Decisions present in cognitive map after close
