# Task: Close Signal

## Objective
Create CloseSignal.v1.json schema per Rosetta Stone Contract 2.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 2
- Top-level: id, session_id, path_id, closed_at, status, deliverables, session_summary, decisions_made, unblocked, context_residue, interrupt_log
- status enum: completed, abandoned, failed, forked

## Implementation Steps
1. Author contracts/schemas/CloseSignal.v1.json
2. Make context_residue.learned_preferences an open object (additionalProperties true)
3. Make session_summary fields all required and numeric

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] All four status values accepted in enum check
