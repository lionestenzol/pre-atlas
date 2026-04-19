# Task: Actions And Contract

## Objective
Implement execute node behavior — fire actions, validate outputs against contract.

## Requirements
- Each action runs and produces a structured result
- On result, validate against the schema referenced by the node (if any)
- Failure → emit error Signal, do not transition

## Implementation Steps
1. Implement handle_execute() in node_processor.py
2. Use contract_validator on outputs
3. Surface action errors as Signal with action_options for retry/abandon

## Definition of Done
- [ ] Test: successful action transitions; failed action emits error signal and holds
