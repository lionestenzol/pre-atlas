# Task: Schema Validate On Emit

## Objective
Enforce Directive.v1.json validation before emit; refuse invalid output.

## Requirements
- If validation fails, log error to delta-kernel and return 500 with error detail
- Never emit a Directive that fails validation

## Implementation Steps
1. Wrap emitNextDirective output in validator call
2. On validation failure, log + raise

## Definition of Done
- [ ] Test: corrupted task in queue → 500, not a malformed Directive
