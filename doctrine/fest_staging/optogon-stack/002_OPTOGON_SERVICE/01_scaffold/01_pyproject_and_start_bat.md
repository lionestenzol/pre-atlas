# Task: Pyproject And Start Bat

## Objective
Create services/optogon/pyproject.toml and start.bat.

## Requirements
- Match pattern from services/cortex/ and services/cognitive-sensor/
- pyproject.toml: name=optogon, deps=fastapi, uvicorn, pydantic, jsonschema, sqlite (stdlib)
- start.bat launches uvicorn on :3010

## Implementation Steps
1. Copy services/cortex/pyproject.toml as template, change name + deps
2. Author start.bat with: uvicorn optogon.main:app --port 3010 --reload

## Definition of Done
- [ ] services/optogon/pyproject.toml exists and parses
- [ ] services/optogon/start.bat launches without ImportError (smoke test)
