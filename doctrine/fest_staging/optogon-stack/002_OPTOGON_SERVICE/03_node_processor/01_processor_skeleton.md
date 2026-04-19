# Task: Processor Skeleton

## Objective
Create node_processor.py skeleton — process_turn(session, message) entry point.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 14
- Single entry: process_turn(session_state, user_message) → (new_state, response_text, signals)
- Branches by current node.type

## Implementation Steps
1. Author node_processor.py with process_turn() and per-type stub functions
2. Wire to session_store and context modules

## Definition of Done
- [ ] process_turn dispatches to correct handler for each node type
- [ ] Unit test exercises every dispatch branch
