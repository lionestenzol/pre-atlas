"""
Contract validation for cognitive-sensor outputs.
Uses JSON Schema to enforce data contracts before writing payloads.
"""
import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    ValidationError = Exception

BASE = Path(__file__).parent.resolve()
CONTRACTS = BASE.parent.parent / "contracts" / "schemas"


def load_schema(name: str) -> dict:
    """Load a JSON schema from contracts/schemas/"""
    path = CONTRACTS / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return json.load(open(path, encoding="utf-8"))


def validate_payload(data: dict, schema_name: str) -> tuple[bool, str | None]:
    """
    Validate data against a schema.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not HAS_JSONSCHEMA:
        print(f"[WARN] jsonschema not installed. Skipping validation for {schema_name}")
        return True, None

    try:
        schema = load_schema(schema_name)
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, f"Validation failed for {schema_name}: {e.message}"
    except FileNotFoundError as e:
        return False, str(e)


def validate_daily_payload(payload: dict) -> tuple[bool, str | None]:
    """Validate DailyPayload before export to CycleBoard."""
    return validate_payload(payload, "DailyPayload.v1.json")


def validate_cognitive_metrics(metrics: dict) -> tuple[bool, str | None]:
    """Validate CognitiveMetricsComputed before export."""
    return validate_payload(metrics, "CognitiveMetricsComputed.json")


def validate_directive(directive: dict) -> tuple[bool, str | None]:
    """Validate DirectiveProposed before export."""
    return validate_payload(directive, "DirectiveProposed.json")


def validate_closures(closures: dict) -> tuple[bool, str | None]:
    """Validate Closures registry (Phase 5B)."""
    return validate_payload(closures, "Closures.v1.json")


def validate_work_ledger(ledger: dict) -> tuple[bool, str | None]:
    """Validate Work Ledger (Phase 6A)."""
    return validate_payload(ledger, "WorkLedger.v1.json")


def require_valid(data: dict, schema_name: str, context: str = "") -> None:
    """
    Validate and raise on failure. Use this to hard-block invalid writes.
    """
    valid, error = validate_payload(data, schema_name)
    if not valid:
        raise ValueError(f"[CONTRACT VIOLATION] {context}: {error}")


if __name__ == "__main__":
    # Self-test: validate current outputs
    print("Contract Validation Self-Test")
    print("=" * 40)

    # Test DailyPayload
    daily_path = BASE / "cycleboard" / "brain" / "daily_payload.json"
    if daily_path.exists():
        payload = json.load(open(daily_path, encoding="utf-8"))
        valid, err = validate_daily_payload(payload)
        print(f"DailyPayload: {'PASS' if valid else 'FAIL'}")
        if err:
            print(f"  {err}")
    else:
        print("DailyPayload: SKIP (file not found)")

    # Test cognitive_state (note: schema mismatch expected)
    cog_path = BASE / "cognitive_state.json"
    if cog_path.exists():
        state = json.load(open(cog_path, encoding="utf-8"))
        valid, err = validate_cognitive_metrics(state)
        print(f"CognitiveMetrics: {'PASS' if valid else 'FAIL'}")
        if err:
            print(f"  {err}")
    else:
        print("CognitiveMetrics: SKIP (file not found)")

    # Test closures registry (Phase 5B)
    closures_path = BASE / "closures.json"
    if closures_path.exists():
        closures = json.load(open(closures_path, encoding="utf-8"))
        valid, err = validate_closures(closures)
        print(f"Closures: {'PASS' if valid else 'FAIL'}")
        if err:
            print(f"  {err}")
    else:
        print("Closures: SKIP (file not found)")

    # Test work ledger (Phase 6A)
    work_ledger_path = BASE / "work_ledger.json"
    if work_ledger_path.exists():
        ledger = json.load(open(work_ledger_path, encoding="utf-8"))
        valid, err = validate_work_ledger(ledger)
        print(f"WorkLedger: {'PASS' if valid else 'FAIL'}")
        if err:
            print(f"  {err}")
    else:
        print("WorkLedger: SKIP (file not found)")

    print("=" * 40)
    print("Done.")
