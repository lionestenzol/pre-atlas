"""
Phase 6 — governor. Law 5: this is the ONLY phase with veto power over
report generation. Future validation checks are added to its checklist,
never as a separate gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from core import case_manager, llm
from core.models import FindingsResult, GovernorReport, Intake, PhaseStatus

SYSTEM_PROMPT = """You are the Governor: a strict editorial gate that reviews \
findings before they are allowed into a client-facing report. You do not \
rewrite findings — you audit them.

Run this exact checklist against the findings, and record a pass/fail entry \
for each item in `checklist`:
1. unsupported_claims — every finding's claims are backed by its own evidence list.
2. unlabeled_assumptions — inferences beyond the evidence are clearly flagged \
as assumptions, not stated as fact.
3. privacy_exposure — findings do not leak sensitive data beyond what the \
intake's privacy_level permits, and do not encourage exposing secrets.
4. scope_creep — findings stay within user_claim / desired_outcome, no \
unrelated tangents presented as core findings.
5. overconfident_language — confidence field matches the strength of the \
wording used (no "high" confidence on speculative claims).
6. detection_conflation — findings correctly distinguish "not detected in \
scan" from "confirmed absent"; never claim something "does not exist" when \
the scan only shows detected=false.

status rules:
- "blocked" if ANY checklist item fails on a finding that materially \
misleads the reader (e.g. a false certainty claim, real privacy leak).
- "needs_review" if minor issues exist that a human should look at but \
don't block distribution.
- "approved" if all checks pass cleanly.

blocking_reasons must be empty unless status is "blocked", and must name \
the specific finding id(s) and checklist item(s) at fault.

`summary` must be 3-6 sentences, under 800 characters. State the verdict and \
the specific issues found — nothing else. Do not draft multiple versions, \
narrate your own writing process, or include meta-commentary; output only \
the final summary text.
"""


def _build_prompt(intake: Intake, findings: FindingsResult, template_intent: str) -> str:
    return (
        "Audit these findings against the checklist before they become a report.\n\n"
        f"=== intake.json ===\n{json.dumps(intake.model_dump(), indent=2)}\n\n"
        f"=== findings.json ===\n{json.dumps(findings.model_dump(), indent=2)}\n\n"
        f"=== report_template.md (intent only, do not fill it in) ===\n{template_intent}\n"
    )


def run_govern(case_id: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="govern", reason=str(exc))

    # Law 3: govern verifies its own prerequisites.
    intake_path = case_dir / "intake.json"
    findings_path = case_dir / "findings.json"
    if not intake_path.exists():
        return PhaseStatus(status="failed", phase="govern", reason="intake.json missing. Run 'intake' first.")
    if not findings_path.exists():
        return PhaseStatus(status="failed", phase="govern", reason="findings.json missing. Run 'analyze' first.")

    try:
        intake = Intake.model_validate(case_manager.read_json(intake_path))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="govern", reason=f"intake.json invalid: {exc}")
    if not intake.is_complete():
        return PhaseStatus(status="failed", phase="govern", reason="intake.json is incomplete. Run 'intake' first.")
    try:
        findings = FindingsResult.model_validate(case_manager.read_json(findings_path))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="govern", reason=f"findings.json invalid: {exc}")

    base_dir = case_dir.parent.parent
    template_path = base_dir / "templates" / "report_template.md"
    template_intent = template_path.read_text() if template_path.exists() else "(template not found)"

    prompt = _build_prompt(intake, findings, template_intent)
    try:
        report = llm.structured_call(prompt, GovernorReport, system=SYSTEM_PROMPT)
    except llm.LLMCallError as exc:
        return PhaseStatus(status="failed", phase="govern", reason=str(exc))

    report.case_id = case_manager.case_short_id(case_dir)
    report.generated_at = datetime.now(timezone.utc).isoformat()

    if report.status == "blocked" and not report.blocking_reasons:
        report.blocking_reasons = ["Governor returned status=blocked without specific reasons."]

    case_manager.write_json(case_dir / "governor_report.json", report.model_dump())
    return PhaseStatus(status="ok", phase="govern", reason=None)
