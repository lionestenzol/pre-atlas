# Task: End To End Test

## Objective
Author tests/test_path_ship_inpact_lesson.py — full path execution test.

## Requirements
- Mock LLM responses; mock filesystem reads/writes
- Test must complete the path with status=completed and emit valid CloseSignal
- Asserts: questions_asked < 3, completion_rate = 1.0

## Implementation Steps
1. Author the test file
2. Use TestClient from fastapi.testclient
3. Drive the full path: POST /session/start → loop POST /session/{id}/turn until close

## Definition of Done
- [ ] pytest services/optogon/tests/test_path_ship_inpact_lesson.py passes
- [ ] CloseSignal payload validates against schema
