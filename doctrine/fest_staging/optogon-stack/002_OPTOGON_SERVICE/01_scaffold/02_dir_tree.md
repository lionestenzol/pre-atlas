# Task: Dir Tree

## Objective
Create the full src/optogon/ directory layout from build plan Phase 2.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 2 scaffold tree
- Create empty __init__.py + stub files for: main.py, config.py, node_processor.py, contract_validator.py, response_composer.py, session_store.py, context.py, inference.py, signals.py
- Create paths/ with _template.json and ship_inpact_lesson.json placeholder
- Create tests/ with empty test files

## Implementation Steps
1. Create directory tree under services/optogon/src/optogon/
2. Each .py stub has module docstring + 'pass' or empty class skeleton
3. _template.json contains a minimal valid OptogonPath

## Definition of Done
- [ ] All directories and files exist
- [ ] python -c 'import optogon' succeeds (after pip install -e .)
