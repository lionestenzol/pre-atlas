# Task: Pacing Constraints

## Objective
Implement response_composer pacing layer — token budget + question-count constraint.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 11 metrics + spec pacing section
- Hard cap: 1 question per turn
- Soft cap: < 200 tokens per node closed
- If composer wants to ask more, log violation and truncate

## Implementation Steps
1. Author response_composer.py with compose(node, session, draft) → final_text
2. Implement question-count enforcement before LLM call

## Definition of Done
- [ ] Composer never returns response with > 1 question mark in non-clarification turn
- [ ] Logged metric: tokens_used per node
