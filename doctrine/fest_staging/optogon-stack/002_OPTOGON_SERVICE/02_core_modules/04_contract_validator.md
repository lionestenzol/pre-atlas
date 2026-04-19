# Task: Contract Validator

## Objective
Implement contract_validator.py — load & validate against contracts/schemas/.

## Requirements
- API: validate(payload, contract_name) → True or raises ContractError
- Loads schemas lazily; caches Draft7Validator instances
- Used at every emit boundary (close signal, signal to inpact, directive consume)

## Implementation Steps
1. Author contract_validator.py
2. Resolve schema path relative to repo root via env var or sys.path walk
3. Add small test using OptogonNode example

## Definition of Done
- [ ] validate(valid_payload, 'CloseSignal') returns True
- [ ] validate(invalid_payload, 'CloseSignal') raises ContractError with field detail
