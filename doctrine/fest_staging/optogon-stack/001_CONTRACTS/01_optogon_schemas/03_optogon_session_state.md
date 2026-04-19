# Task: Optogon Session State

## Objective
Create OptogonSessionState.v1.json schema per spec Section 8.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 8 (Session State Model)
- Captures: session_id, path_id, current_node_id, context tiers, history, started_at
- Context hierarchy fields (confirmed, user, inferred, system) per spec
- schema_version literal '1.0'

## Implementation Steps
1. Author contracts/schemas/OptogonSessionState.v1.json
2. Model context tiers as 4 named objects in a parent context object
3. Include node_history array tracking entered_at/closed_at per node

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Round-trips through json.dump/load without loss
