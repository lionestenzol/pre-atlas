# Task: Health And Paths

## Objective
Implement /health (uptime + version) and /paths (lists paths/*.json).

## Requirements
- /health: returns {status: ok, version, uptime_seconds, schemas_loaded: int}
- /paths: scans services/optogon/paths/, returns [{id, label, description}]

## Implementation Steps
1. Implement health endpoint in main.py
2. Implement paths endpoint that reads paths/*.json and extracts metadata

## Definition of Done
- [ ] GET /health returns 200 with all fields populated
- [ ] GET /paths returns at least ship_inpact_lesson
