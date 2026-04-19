# Task: Fastapi Endpoints

## Objective
Implement FastAPI endpoints per build plan Phase 2 spec.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 2 endpoints list
- POST /session/start, POST /session/{id}/turn, GET /session/{id}, GET /paths, GET /health
- All responses JSON; errors return structured ContractError detail

## Implementation Steps
1. Author main.py with FastAPI app + 5 routes
2. Wire to session_store and node_processor
3. Add CORS middleware allowing inpact origin (:3006)

## Definition of Done
- [ ] All 5 endpoints respond with expected shapes
- [ ] OpenAPI docs at /docs render
