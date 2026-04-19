# Task: Approval Required Surface

## Objective
Surface approval_required signals above-the-fold with action buttons.

## Requirements
- Source: doctrine/02_ROSETTA_STONE.md Section 5 InPACT Display Rules
- approval_required signals always render at top regardless of priority
- Each action_option becomes a clickable button
- Click POSTs decision back to /api/signals/{id}/resolve

## Implementation Steps
1. Extend signals.js with approval rendering
2. Add /api/signals/{id}/resolve endpoint to delta-kernel
3. Wire button click → POST → re-fetch

## Definition of Done
- [ ] Approval signal renders with buttons at top
- [ ] Clicking button removes signal and resolves it
