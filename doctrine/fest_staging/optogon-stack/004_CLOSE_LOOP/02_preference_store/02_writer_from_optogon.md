# Task: Writer From Optogon

## Objective
Optogon close handler writes context_residue.learned_preferences to Atlas preference store.

## Requirements
- On close, read learned_preferences from CloseSignal
- POST each entry to /api/atlas/preferences (new endpoint)
- If preference exists with same key, increment observed_count + average confidence

## Implementation Steps
1. Add /api/atlas/preferences POST endpoint to delta-kernel
2. Hook into Optogon close handler to call it

## Definition of Done
- [ ] After path close, new preferences appear in store
- [ ] Re-running same path increments observed_count
