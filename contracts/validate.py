#!/usr/bin/env python3
"""
validate.py — Optogon stack contracts validator.

Loads every schema under contracts/schemas/ that is part of the Optogon stack,
loads the matching example under contracts/examples/, and validates each
example against its schema. Exits 0 on success, 1 on any failure.

Scope: this script validates the 10 Optogon + Rosetta Stone schemas. Existing
pre-existing schemas (Aegis*, CognitiveMetricsComputed, DailyPayload, etc.)
are handled by services/cognitive-sensor/validate.py and are not touched here.

Usage:
  python contracts/validate.py
  python contracts/validate.py --verbose
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"
EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"

# The 10 Optogon stack schemas (3 Optogon + 7 Rosetta)
OPTOGON_STACK_SCHEMAS = [
    "OptogonNode.v1.json",
    "OptogonPath.v1.json",
    "OptogonSessionState.v1.json",
    "ContextPackage.v1.json",
    "CloseSignal.v1.json",
    "Directive.v1.json",
    "TaskPrompt.v1.json",
    "BuildOutput.v1.json",
    "Signal.v1.json",
    "UserPreferenceStore.v1.json",
]


def example_path_for(schema_filename: str) -> Path:
    # OptogonNode.v1.json -> OptogonNode.v1.example.json
    stem = schema_filename.rsplit(".json", 1)[0]
    return EXAMPLES_DIR / f"{stem}.example.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_one(schema_filename: str, verbose: bool = False) -> tuple[bool, list[str]]:
    errors: list[str] = []
    schema_path = SCHEMAS_DIR / schema_filename
    example_path = example_path_for(schema_filename)

    if not schema_path.exists():
        return False, [f"Schema missing: {schema_path}"]
    if not example_path.exists():
        return False, [f"Example missing: {example_path}"]

    try:
        schema = load_json(schema_path)
    except json.JSONDecodeError as e:
        return False, [f"Schema invalid JSON: {schema_path}: {e}"]

    try:
        example = load_json(example_path)
    except json.JSONDecodeError as e:
        return False, [f"Example invalid JSON: {example_path}: {e}"]

    # First: schema itself is valid draft-07
    try:
        Draft7Validator.check_schema(schema)
    except Exception as e:
        return False, [f"Schema fails draft-07 self-check: {schema_path}: {e}"]

    validator = Draft7Validator(schema)
    instance_errors = sorted(validator.iter_errors(example), key=lambda e: list(e.path))
    if instance_errors:
        for err in instance_errors:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"  at {loc}: {err.message}")
        return False, errors

    if verbose:
        print(f"  ok: {schema_filename} -> {example_path.name}")
    return True, []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    print(f"Validating {len(OPTOGON_STACK_SCHEMAS)} Optogon stack schemas in {SCHEMAS_DIR}")

    failed = 0
    passed = 0
    for schema_filename in OPTOGON_STACK_SCHEMAS:
        ok, errors = validate_one(schema_filename, verbose=args.verbose)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {schema_filename}")
            for e in errors:
                print(e)

    total = passed + failed
    print()
    if failed == 0:
        print(f"{total} schemas, {total} examples, all valid")
        return 0
    print(f"{passed}/{total} schemas validated; {failed} failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
