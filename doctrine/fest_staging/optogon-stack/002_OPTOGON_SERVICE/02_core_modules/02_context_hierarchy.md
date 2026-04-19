# Task: Context Hierarchy

## Objective
Implement context.py — confirmed > user > inferred > system tier resolver.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md context hierarchy section
- API: resolve(key, session_state) → (value, tier) or (None, None)
- Tier order: confirmed > user > inferred > system

## Implementation Steps
1. Author context.py with resolve() and set_tier(key, value, tier)
2. Add merge() that promotes inferred → confirmed when user explicitly confirms

## Definition of Done
- [ ] Unit test: confirmed value beats user value beats inferred value
- [ ] Unit test: resolve returns (None, None) for unknown key
