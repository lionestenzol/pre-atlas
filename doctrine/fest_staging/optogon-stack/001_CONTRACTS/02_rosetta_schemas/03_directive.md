# Task: Directive

## Objective
Create Directive.v1.json schema per Rosetta Stone Contract 3.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 3
- Top-level: id, issued_at, priority_tier, leverage_score, task, context_bundle, execution, interrupt_policy
- task.success_criteria minItems 1 (Atlas must never emit empty success_criteria)

## Implementation Steps
1. Author contracts/schemas/Directive.v1.json
2. Enforce task.success_criteria minItems via JSON schema
3. Constrain leverage_score to [0,1]

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Example with empty success_criteria fails validation
