"""Contract validator - loads schemas from contracts/schemas/, validates payloads.

Used at every emit boundary (close signal, signal to inpact, path load).
"""
from __future__ import annotations
import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft7Validator

from .config import SCHEMAS_DIR


class ContractError(ValueError):
    """Raised when a payload fails its contract schema."""

    def __init__(self, contract_name: str, errors: list[str]) -> None:
        self.contract_name = contract_name
        self.errors = errors
        super().__init__(f"Contract {contract_name} failed: " + "; ".join(errors))


@lru_cache(maxsize=32)
def _load_validator(contract_name: str) -> Draft7Validator:
    schema_path = SCHEMAS_DIR / f"{contract_name}.v1.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def validate(payload: Any, contract_name: str) -> bool:
    """Validate payload. Returns True or raises ContractError."""
    validator = _load_validator(contract_name)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return True
    messages = [f"at {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
    raise ContractError(contract_name, messages)


def is_valid(payload: Any, contract_name: str) -> bool:
    """Soft check - returns bool without raising."""
    try:
        return validate(payload, contract_name)
    except ContractError:
        return False
