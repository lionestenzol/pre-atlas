# Task: Validator Py

## Objective
Create contracts/validate.py — loads every schema and example, asserts validity.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 1 step 3 deliverable
- Iterate contracts/schemas/*.json and contracts/examples/*.json
- Pair by basename (OptogonNode.v1.json ↔ OptogonNode.v1.example.json)
- Use jsonschema library (Draft7Validator)
- Exit code 0 on success, 1 on any failure

## Implementation Steps
1. Author contracts/validate.py
2. Add jsonschema to requirements (if not already present in contracts/)
3. Print summary: schema count, example count, validation status

## Definition of Done
- [ ] python contracts/validate.py exits 0 with clean output
- [ ] Deleting any example causes script to fail with clear error
