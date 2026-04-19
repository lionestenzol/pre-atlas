# Task: Session Store

## Objective
Implement session_store.py — in-memory + SQLite persistence of OptogonSessionState.

## Requirements
- Source: doctrine/03_OPTOGON_SPEC.md Section 8
- API: create_session, get_session, update_session, close_session
- Backing: SQLite file at services/optogon/data/sessions.db (auto-created)
- Validate state against OptogonSessionState.v1.json on every write

## Implementation Steps
1. Author session_store.py
2. On startup, ensure sessions table exists
3. Use json column for full state blob; index session_id

## Definition of Done
- [ ] Round-trip create→update→get returns equal state
- [ ] Schema-invalid state raises before write
