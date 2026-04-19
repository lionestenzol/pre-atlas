# Task: Emit Build Output

## Objective
Add emit_build_output(result) → BuildOutput in ghost_executor.

## Requirements
- Wraps Claude Code execution result
- Validates against BuildOutput.v1.json before emitting
- Emits Signal to InPACT (completion or error)

## Implementation Steps
1. Author emit.py with emit_build_output()
2. Hook into existing cortex executor return path

## Definition of Done
- [ ] Successful run → BuildOutput status=success + completion Signal
- [ ] Failed run → status=failed + error Signal with action_options
