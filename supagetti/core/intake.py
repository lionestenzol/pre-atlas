"""Phase 2 — interactive intake."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from core import case_manager
from core.models import Intake, PhaseStatus

# (field, prompt text, choices or None) — walked in order. All required.
REQUIRED_FIELDS: list[tuple[str, str, list[str] | None]] = [
    ("project_name", "Project name", None),
    ("source_type", "Source type", ["folder", "zip", "repo"]),
    ("user_claim", "What does the user claim this project does?", None),
    ("user_pain", "What pain/problem is the user trying to solve?", None),
    ("desired_outcome", "What is the desired outcome of this analysis?", None),
    ("audience", "Who is the audience for the report?", None),
    ("privacy_level", "Privacy level", ["public", "internal", "confidential"]),
]
OPTIONAL_FIELDS: list[tuple[str, str]] = [
    ("scope_limit", "Scope limit (optional, press Enter to skip)"),
]


def _prompt_required(field: str, label: str, choices: list[str] | None) -> str:
    suffix = f" [{'/'.join(choices)}]" if choices else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if not value:
            print(f"  '{field}' is required, please enter a value.")
            continue
        if choices and value not in choices:
            print(f"  Must be one of: {', '.join(choices)}")
            continue
        return value


def _prompt_optional(label: str) -> str | None:
    value = input(f"{label}: ").strip()
    return value or None


def run_intake(case_id: str, input_fn=input) -> PhaseStatus:
    global input
    input = input_fn  # allow tests/automation to inject input
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="intake", reason=str(exc))

    short_id = case_manager.case_short_id(case_dir)
    print(f"\n=== Intake for {short_id} ===")
    print("Required fields will re-prompt until answered. Optional fields "
          "can be skipped with Enter.\n")

    answers: dict = {}
    for field, label, choices in REQUIRED_FIELDS:
        answers[field] = _prompt_required(field, label, choices)
    for field, label in OPTIONAL_FIELDS:
        answers[field] = _prompt_optional(label)

    answers["case_id"] = short_id
    answers["created_at"] = datetime.now(timezone.utc).isoformat()

    existing_path = case_dir / "intake.json"
    if existing_path.exists():
        existing = case_manager.read_json(existing_path)
        if existing.get("source_reference"):
            answers["source_reference"] = existing["source_reference"]

    try:
        intake = Intake.model_validate(answers)
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="intake", reason=str(exc))
    if not intake.is_complete():
        return PhaseStatus(status="failed", phase="intake", reason="Required fields were left empty.")

    case_manager.write_json(existing_path, intake.model_dump())
    print(f"\nintake.json written to {existing_path}")
    return PhaseStatus(status="ok", phase="intake", reason=None)
