# Task: User Preference Store

## Objective
Create UserPreferenceStore.v1.json schema per Rosetta Stone cross-session memory section.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md 'Cross-Session User Memory'
- Top-level: user_id, last_updated, preferences[], behavioral_patterns[]
- preferences[].source enum: explicit, inferred
- preferences[].confidence in [0,1]

## Implementation Steps
1. Author contracts/schemas/UserPreferenceStore.v1.json
2. Constrain confidence numeric range

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Example with confidence > 1 fails validation
