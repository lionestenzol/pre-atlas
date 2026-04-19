# Task: Schema And Sqlite Table

## Objective
Add user_preferences SQLite table backing UserPreferenceStore.v1.json.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md Cross-Session User Memory
- Table columns: id, user_id, key, value (json), confidence, source, observed_count, last_observed
- Single user system for now (user_id literal 'bruke')

## Implementation Steps
1. Add migration to delta-kernel storage layer
2. Add Preference repo module with read/write API

## Definition of Done
- [ ] Table exists; round-trip insert+query succeeds
- [ ] Schema validation against UserPreferenceStore.v1.json passes
