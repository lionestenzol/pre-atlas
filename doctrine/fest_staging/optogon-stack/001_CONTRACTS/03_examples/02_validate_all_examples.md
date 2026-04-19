# Task: Validate All Examples

## Objective
Run jsonschema validator over every example against its schema; all must pass.

## Requirements
- Use the validator from sequence 04 as the runner
- Exit non-zero if any example fails

## Implementation Steps
1. Run python contracts/validate.py
2. Read its output; fix any failing examples or schemas
3. Re-run until clean

## Definition of Done
- [ ] validate.py exits 0
- [ ] Output line: '10 schemas, 10 examples, all valid'
