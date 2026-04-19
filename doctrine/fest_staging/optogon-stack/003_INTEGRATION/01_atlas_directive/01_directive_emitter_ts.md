# Task: Directive Emitter Ts

## Objective
Add services/delta-kernel/src/atlas/directive.ts — transforms task queue → Directive.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 3a
- Function: emitNextDirective(): Directive | null
- Reads from existing leverage-scored queue in delta-kernel
- Output validates against Directive.v1.json

## Implementation Steps
1. Add directive.ts module under src/atlas/
2. Map current task fields onto Directive shape
3. Use ajv (or existing schema validator) for runtime validation

## Definition of Done
- [ ] Unit test: emit returns valid Directive for known queue state
- [ ] Test: empty queue returns null cleanly
