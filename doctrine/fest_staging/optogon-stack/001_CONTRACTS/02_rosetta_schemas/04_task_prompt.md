# Task: Task Prompt

## Objective
Create TaskPrompt.v1.json schema per Rosetta Stone Contract 4 (request side).

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 4 (Ghost Executor → Claude Code)
- Top-level: id, directive_id, issued_at, instruction, environment, prior_attempts, output_spec, constraints
- Must include both success_criteria and failure_criteria as required arrays

## Implementation Steps
1. Author contracts/schemas/TaskPrompt.v1.json
2. Make do_not_modify a constraint string array (treated as hard rule downstream)

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Examples missing failure_criteria fail validation
