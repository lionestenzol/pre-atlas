"""
Law 1: case ID resolution lives here and nowhere else. Every command that
takes a CASE_ID argument imports resolve_case_id() from this module.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.models import Intake

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_DIR = BASE_DIR / "cases"
COUNTER_FILE = CASES_DIR / ".counter"

CASE_ID_RE = re.compile(r"^CASE_(\d{4})(?:_.*)?$")


class CaseNotFoundError(Exception):
    pass


class CaseAmbiguousError(Exception):
    pass


def _ensure_cases_dir() -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)


def _short_id(case_id: str) -> str:
    """Normalize any accepted CASE_ID form down to 'CASE_0001'."""
    match = CASE_ID_RE.match(case_id.strip())
    if not match:
        raise CaseNotFoundError(
            f"'{case_id}' is not a valid CASE_ID. Expected 'CASE_0001' or "
            f"'CASE_0001_project_name'."
        )
    return f"CASE_{match.group(1)}"


def resolve_case_id(case_id: str) -> Path:
    """
    Resolve 'CASE_0001' or 'CASE_0001_project_name' to the case's folder on
    disk. This is the ONLY place case ID resolution happens (Law 1).
    """
    _ensure_cases_dir()
    short = _short_id(case_id)

    matches = sorted(
        p for p in CASES_DIR.iterdir()
        if p.is_dir() and (p.name == short or p.name.startswith(short + "_"))
    )
    if not matches:
        raise CaseNotFoundError(
            f"No case found matching '{case_id}' under {CASES_DIR}."
        )
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        raise CaseAmbiguousError(
            f"CASE_ID '{case_id}' is ambiguous, matches: {names}"
        )
    return matches[0]


def _next_case_number() -> int:
    """Case numbers are never reused, even if a case folder is deleted."""
    _ensure_cases_dir()
    last = 0
    if COUNTER_FILE.exists():
        last = int(COUNTER_FILE.read_text().strip() or "0")

    # Guard against the counter file falling behind reality (e.g. manual
    # folder creation) by also checking what's on disk.
    for p in CASES_DIR.iterdir():
        if p.is_dir():
            m = CASE_ID_RE.match(p.name)
            if m:
                last = max(last, int(m.group(1)))

    next_number = last + 1
    COUNTER_FILE.write_text(str(next_number))
    return next_number


def create_case(name: str) -> Path:
    """Create /cases/CASE_000N_name/ with a schema-valid empty intake.json."""
    _ensure_cases_dir()
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_") or "project"
    number = _next_case_number()
    case_dir_name = f"CASE_{number:04d}_{slug}"
    case_dir = CASES_DIR / case_dir_name
    case_dir.mkdir(parents=True, exist_ok=False)
    (case_dir / "source").mkdir(parents=True, exist_ok=True)

    intake = Intake(
        case_id=f"CASE_{number:04d}",
        project_name=name,
        source_type="folder",
        user_claim="",
        user_pain="",
        desired_outcome="",
        audience="",
        privacy_level="internal",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    # Write the raw dict rather than intake.model_dump_json() directly so the
    # "empty" placeholder strings are visibly unfilled pending Phase 2 intake.
    write_json(case_dir / "intake.json", intake.model_dump())
    return case_dir


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def case_short_id(case_dir: Path) -> str:
    m = CASE_ID_RE.match(case_dir.name)
    return f"CASE_{m.group(1)}" if m else case_dir.name
