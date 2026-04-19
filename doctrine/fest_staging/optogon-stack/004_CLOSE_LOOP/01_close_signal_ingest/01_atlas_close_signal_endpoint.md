# Task: Atlas Close Signal Endpoint

## Objective
Add POST /api/atlas/close-signal to delta-kernel.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 4
- Validates body against CloseSignal.v1.json
- Returns 202 on accept; 400 on schema fail

## Implementation Steps
1. Add route in delta-kernel server.ts
2. Wire to close_signal handler module

## Definition of Done
- [ ] Valid CloseSignal POST → 202
- [ ] Invalid → 400 with structured error
