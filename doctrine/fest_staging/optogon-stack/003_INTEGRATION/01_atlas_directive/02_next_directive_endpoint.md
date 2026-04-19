# Task: Next Directive Endpoint

## Objective
Add GET /api/atlas/next-directive endpoint to delta-kernel server.ts.

## Requirements
- Returns Directive JSON or 204 if queue empty
- Calls directive.emitNextDirective()
- CORS allows cortex origin

## Implementation Steps
1. Edit services/delta-kernel/src/api/server.ts
2. Wire route to directive.ts
3. Add to OpenAPI surface if delta-kernel has one

## Definition of Done
- [ ] curl localhost:3001/api/atlas/next-directive returns valid Directive or 204
