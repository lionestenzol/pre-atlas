# Task: Context Package

## Objective
Create ContextPackage.v1.json schema per Rosetta Stone Contract 1.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 1
- Top-level: id, source, captured_at, structure_map, dependency_graph, action_inventory, inferred_state, token_count, compression_ratio
- Must support partial_context_package variant with coverage_score

## Implementation Steps
1. Copy field tree directly from Rosetta Contract 1 'What Site Pull Produces'
2. Express enums for source, route.method, component.type, action.type, action.risk_tier
3. Add schema_version field

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Includes both full and partial variants via oneOf
