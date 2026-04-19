# Task: Qualification And Inference

## Objective
Implement qualification node behavior — collect qualification_keys, run inference rules first.

## Requirements
- On enter: run inference.apply_rules(); for any key already inferred with confidence > 0.85, skip the question
- For remaining keys, ask one-at-a-time per pacing constraints
- On user answer, write to confirmed tier

## Implementation Steps
1. Implement handle_qualify() in node_processor.py
2. Hook to context.set_tier and inference.apply_rules
3. Track which keys are still pending in session_state.history

## Definition of Done
- [ ] Test: qualify node with all keys pre-inferred completes in 0 questions
- [ ] Test: qualify node asks remaining keys one at a time
