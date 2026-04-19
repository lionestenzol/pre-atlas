# Task: Inference Rules

## Objective
Implement inference.py — Burden-Removal inference rules from spec.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Burden-Removal section
- Each rule: input qualification keys + system context → inferred value with confidence
- Confidence > 0.85 means it propagates to learned_preferences in close signal

## Implementation Steps
1. Author inference.py with apply_rules(session_state) → list of (key, value, confidence)
2. Implement at least 3 starter rules per spec examples
3. Mark rules as data-driven (loadable from JSON later)

## Definition of Done
- [ ] Unit test: known input produces known inferred output with expected confidence
- [ ] Output structure matches what session_store expects
