# Task: Signals Endpoint

## Objective
Add GET /api/signals to delta-kernel — aggregates Signals from all layers.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 3c
- Returns array of Signal objects
- Sorts by priority + emitted_at desc
- Supports ?since=timestamp filter

## Implementation Steps
1. Add signals collection table to delta-kernel SQLite
2. Add ingest endpoint POST /api/signals/ingest
3. Add list endpoint GET /api/signals

## Definition of Done
- [ ] curl /api/signals returns valid array
- [ ] POST /api/signals/ingest with valid Signal stores and is returned by GET
