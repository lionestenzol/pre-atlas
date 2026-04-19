# Task: Transitions

## Objective
Implement transition resolution — gate, approval, fork, close node types.

## Requirements
- gate: evaluates condition, transitions to true_branch or false_branch
- approval: emits approval_required Signal, blocks until external resolution
- fork: spawns sub-session (deferred per build plan; raise NotImplementedError with TODO)
- close: assemble CloseSignal, validate, emit to Atlas

## Implementation Steps
1. Implement handle_gate, handle_approval, handle_fork (stub), handle_close
2. On close, build CloseSignal payload from session_state via dedicated builder

## Definition of Done
- [ ] Test: gate with true condition transitions correctly
- [ ] Test: close emits valid CloseSignal that passes contract_validator
