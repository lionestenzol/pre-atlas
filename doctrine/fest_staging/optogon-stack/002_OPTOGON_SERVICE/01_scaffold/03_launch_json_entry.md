# Task: Launch Json Entry

## Objective
Add optogon entry to .claude/launch.json so preview tooling can start it.

## Requirements
- Match pattern of existing entries in .claude/launch.json
- Name: 'optogon'
- runtimeExecutable: services/optogon/start.bat OR uvicorn (cross-platform)
- port: 3010

## Implementation Steps
1. Read .claude/launch.json
2. Append new configuration object
3. Verify JSON parses

## Definition of Done
- [ ] preview_start name='optogon' boots a server on :3010
- [ ] GET http://localhost:3010/health returns 200
