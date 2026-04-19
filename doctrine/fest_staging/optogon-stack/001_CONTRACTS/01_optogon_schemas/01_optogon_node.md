# Task: Optogon Node

## Objective
Create OptogonNode.v1.json schema covering all node types from spec Section 6.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 6 (Node Architecture)
- Schema must support node types: qualify, execute, gate, approval, close, fork
- Required top-level fields: id, type, label, qualification_keys, actions, transitions, schema_version
- Use $schema draft-07 to match existing contracts/schemas/ConventionVersion
- schema_version field literal '1.0'

## Implementation Steps
1. Open contracts/schemas/ for naming/format reference (ModeContract.v1.json)
2. Author contracts/schemas/OptogonNode.v1.json
3. Cross-check every field name against spec Section 6
4. Validate schema itself parses with jsonschema.Draft7Validator.check_schema

## Definition of Done
- [ ] File contracts/schemas/OptogonNode.v1.json exists
- [ ] Draft-07 self-check passes
- [ ] Covers all 6 node types with type-specific conditional requirements
