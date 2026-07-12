"""Phase 5 — analyzer. LLM calls go only through core/llm.py (Law 6)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from core import case_manager, llm
from core.models import FindingsResult, Intake, PhaseStatus, ScanResult

SYSTEM_PROMPT = """You are a careful, evidence-driven software analyst. You \
review a project's intake notes and a deterministic static scan, then \
produce findings about the codebase.

Rules:
- Every finding MUST cite concrete evidence from the scan data (file names, \
extension counts, detected manifests) — never invent evidence.
- Distinguish "not detected" from "confirmed absent": if the scan shows \
detected=false, phrase the finding as "no evidence of X was found in the \
scanned files", not "X does not exist".
- Do not overstate confidence. Use "low" confidence when evidence is thin.
- Do not make claims beyond what the intake and scan support.
- recommended_next_action must be concrete and actionable, not generic advice.
"""


def _build_prompt(intake: Intake, scan: ScanResult) -> str:
    return (
        "Analyze this project and produce a findings.json-conformant object.\n\n"
        f"=== intake.json ===\n{json.dumps(intake.model_dump(), indent=2)}\n\n"
        f"=== scan.json ===\n{json.dumps(scan.model_dump(), indent=2)}\n\n"
        "Produce between 3 and 10 findings covering: how well the codebase "
        "supports the user's claim, gaps relative to the desired outcome, "
        "privacy/security exposure implied by the privacy_level and scan "
        "data, and structural/technical observations from the scan. Every "
        "finding needs non-empty evidence drawn from the data above."
    )


def run_analyze(case_id: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="analyze", reason=str(exc))

    # Law 3: analyze does not assume scan/intake ran; it verifies itself.
    intake_path = case_dir / "intake.json"
    scan_path = case_dir / "scan.json"
    if not intake_path.exists():
        return PhaseStatus(status="failed", phase="analyze", reason="intake.json missing. Run 'intake' first.")
    if not scan_path.exists():
        return PhaseStatus(status="failed", phase="analyze", reason="scan.json missing. Run 'scan' first.")

    try:
        intake = Intake.model_validate(case_manager.read_json(intake_path))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="analyze", reason=f"intake.json invalid: {exc}")
    if not intake.is_complete():
        return PhaseStatus(status="failed", phase="analyze", reason="intake.json is incomplete. Run 'intake' first.")
    try:
        scan = ScanResult.model_validate(case_manager.read_json(scan_path))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="analyze", reason=f"scan.json invalid: {exc}")

    prompt = _build_prompt(intake, scan)
    try:
        findings = llm.structured_call(prompt, FindingsResult, system=SYSTEM_PROMPT)
    except llm.LLMCallError as exc:
        return PhaseStatus(status="failed", phase="analyze", reason=str(exc))

    findings.case_id = case_manager.case_short_id(case_dir)
    findings.generated_at = datetime.now(timezone.utc).isoformat()

    if not findings.findings:
        return PhaseStatus(status="failed", phase="analyze", reason="LLM returned zero findings.")

    case_manager.write_json(case_dir / "findings.json", findings.model_dump())
    return PhaseStatus(status="ok", phase="analyze", reason=None)
