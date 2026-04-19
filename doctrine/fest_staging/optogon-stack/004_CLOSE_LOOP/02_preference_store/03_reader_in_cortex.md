# Task: Reader In Cortex

## Objective
Cortex reads preferences when composing TaskPrompt — populate context_bundle.user_preferences.

## Requirements
- GET /api/atlas/preferences reads back the store
- Cortex consume_directive populates user_preferences in TaskPrompt from these

## Implementation Steps
1. Add /api/atlas/preferences GET endpoint
2. Edit cortex/ghost_executor/consume.py to fetch + inject

## Definition of Done
- [ ] TaskPrompt example has populated user_preferences after path runs
