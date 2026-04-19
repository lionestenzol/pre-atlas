# Task: Build Output

## Objective
Create BuildOutput.v1.json schema per Rosetta Stone Contract 4 (response side).

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 4 (response shape)
- Top-level: task_prompt_id, completed_at, status, artifacts, summary, issues_encountered, follow_on_tasks, tokens_used
- status enum: success, partial, failed

## Implementation Steps
1. Author contracts/schemas/BuildOutput.v1.json
2. Make artifacts.path required only for type=file or type=diff (conditional)

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Failure-status example with empty artifacts still validates (silent failure forbidden but empty allowed)
