# Task: Optogon Path

## Objective
Create OptogonPath.v1.json schema per spec Section 7.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 7 (Path Composition)
- Path = ordered+branching graph of OptogonNode references
- Required: id, label, description, entry_node_id, nodes[], success_criteria, schema_version
- Each node reference can be inline or by id pointing into a registry

## Implementation Steps
1. Author contracts/schemas/OptogonPath.v1.json
2. Use $ref into OptogonNode.v1.json for inline node definitions
3. Allow alternative: nodes[] of just id strings + separate node_registry

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Example with ship_inpact_lesson shape (5+ nodes) parses
