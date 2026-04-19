# Task: Consume Directive

## Objective
Add services/cortex/src/cortex/ghost_executor/ — consume_directive(directive) → TaskPrompt.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 3b
- Validate input against Directive.v1.json
- Map Directive → TaskPrompt per Rosetta Contract 4
- Output validates against TaskPrompt.v1.json

## Implementation Steps
1. Create cortex/ghost_executor/ package
2. Author consume.py with consume_directive()
3. Wire to existing cortex planner if it makes sense; otherwise standalone

## Definition of Done
- [ ] Unit test: known Directive maps to known TaskPrompt
- [ ] Output validates against schema
