# Task: Signal

## Objective
Create Signal.v1.json schema per Rosetta Stone Contract 5.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md CONTRACT 5 (Universal Signal Schema)
- Top-level: id, emitted_at, source_layer, signal_type, priority, payload
- source_layer enum: site_pull, optogon, atlas, ghost_executor, claude_code
- signal_type enum: status, completion, blocked, approval_required, error, insight
- When action_required true, action_options must be non-empty

## Implementation Steps
1. Author contracts/schemas/Signal.v1.json
2. Use if/then/else to enforce action_options when action_required is true

## Definition of Done
- [ ] Schema validates against draft-07
- [ ] Approval-required example without action_options fails validation
