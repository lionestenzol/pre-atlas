"""Shared jsonschema validator for Ghost Executor contracts.

Loads schemas from repo root contracts/schemas/. Caches Draft7Validators.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


# Resolve repo root: services/cortex/src/cortex/ghost_executor/_validator.py
# parents[0]=ghost_executor, [1]=cortex, [2]=src, [3]=cortex/, [4]=services/, [5]=repo
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCHEMAS_DIR = _REPO_ROOT / "contracts" / "schemas"


class ContractError(ValueError):
    """Raised when a payload fails its schema."""

    def __init__(self, contract_name: str, errors: list[str]) -> None:
        self.contract_name = contract_name
        self.errors = errors
        super().__init__(f"{contract_name} failed: " + "; ".join(errors))


@lru_cache(maxsize=16)
def _load_validator(contract_name: str) -> Draft7Validator:
    schema_path = _SCHEMAS_DIR / f"{contract_name}.v1.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def validate(payload: Any, contract_name: str) -> None:
    """Raise ContractError if payload does not validate."""
    validator = _load_validator(contract_name)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        messages = [f"at {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise ContractError(contract_name, messages)
