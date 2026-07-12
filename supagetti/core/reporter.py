"""
Phase 7 — report generator. Pure templating, no LLM call: analyzer already
produced plain-language text.

Law 5: the Governor is the ONLY phase that can block this one. This
function hard-checks governor_report.json's status at the top, before doing
anything else.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from core import case_manager
from core.models import FindingsResult, GovernorReport, Intake, PhaseStatus, ScanResult

REQUIRED_SECTIONS = [
    "1. Executive Summary", "2. Project Overview", "3. What Was Claimed",
    "4. What Was Found", "5. Evidence Summary", "6. Technical Findings",
    "7. Plain-Language Findings", "8. Why It Matters", "9. Privacy & Security Notes",
    "10. Confidence & Limitations", "11. Recommended Next Actions",
    "12. Governor Review Notes", "13. Case Metadata",
]


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return order.get(severity, 5)


def run_report(case_id: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="report", reason=str(exc))

    # Law 3: verify prerequisites ourselves.
    required = {
        "intake.json": case_dir / "intake.json",
        "scan.json": case_dir / "scan.json",
        "findings.json": case_dir / "findings.json",
        "governor_report.json": case_dir / "governor_report.json",
    }
    for name, path in required.items():
        if not path.exists():
            return PhaseStatus(status="failed", phase="report", reason=f"{name} missing.")

    try:
        intake = Intake.model_validate(case_manager.read_json(required["intake.json"]))
        scan = ScanResult.model_validate(case_manager.read_json(required["scan.json"]))
        findings = FindingsResult.model_validate(case_manager.read_json(required["findings.json"]))
        governor = GovernorReport.model_validate(case_manager.read_json(required["governor_report.json"]))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="report", reason=f"artifact invalid: {exc}")

    # Law 5: only the Governor can block report generation.
    if governor.status == "blocked":
        reasons = "; ".join(governor.blocking_reasons) or "no reasons given"
        return PhaseStatus(
            status="failed",
            phase="report",
            reason=f"Governor blocked report generation: {reasons}",
        )

    sorted_findings = sorted(findings.findings, key=lambda f: _severity_rank(f.severity))

    executive_summary = (
        f"{governor.summary}\n\n"
        f"{len(findings.findings)} finding(s) reviewed for **{intake.project_name}**. "
        f"Governor status: **{governor.status}**."
    )
    project_overview = (
        f"- **Audience:** {intake.audience}\n"
        f"- **Privacy level:** {intake.privacy_level}\n"
        f"- **Desired outcome:** {intake.desired_outcome}\n"
        f"- **Scope limit:** {intake.scope_limit or 'None specified'}\n"
        f"- **Source:** {intake.source_type} ({intake.source_reference or 'unrecorded'})\n"
        f"- **Languages detected:** {', '.join(scan.languages_detected) or 'none detected'}\n"
        f"- **Files scanned:** {scan.file_count} across {scan.dir_count} directories"
    )
    what_was_found = "\n".join(f"- **{f.title}** ({f.severity}/{f.confidence}): {f.plain_language}" for f in sorted_findings) or "No findings recorded."
    evidence_summary = "\n".join(
        f"- {f.title}:\n  - " + "\n  - ".join(f.evidence) for f in sorted_findings
    ) or "No evidence recorded."
    technical_findings = "\n\n".join(f"**{f.title}**\n{f.technical_finding}" for f in sorted_findings) or "None."
    plain_language_findings = "\n\n".join(f"**{f.title}**\n{f.plain_language}" for f in sorted_findings) or "None."
    why_it_matters = "\n\n".join(f"**{f.title}**\n{f.why_it_matters}" for f in sorted_findings) or "None."
    privacy_security_notes = "\n".join(
        c.name + ": " + ("PASS" if c.passed else "FAIL") + (f" — {c.notes}" if c.notes else "")
        for c in governor.checklist if c.name in ("privacy_exposure", "detection_conflation")
    ) or "No privacy-specific checklist items recorded."
    confidence_limitations = "\n".join(f"- {f.title}: confidence={f.confidence}" for f in sorted_findings) or "None."
    recommended_next_actions = "\n".join(f"- {f.recommended_next_action}" for f in sorted_findings) or "None."
    governor_notes = (
        f"Status: **{governor.status}**\n\n" +
        "\n".join(f"- {c.name}: {'PASS' if c.passed else 'FAIL'} — {c.notes}" for c in governor.checklist)
    )
    case_metadata = (
        f"- Case ID: {case_manager.case_short_id(case_dir)}\n"
        f"- Created: {intake.created_at}\n"
        f"- Report generated: {datetime.now(timezone.utc).isoformat()}\n"
        f"- Scan generated: {scan.generated_at}\n"
        f"- Findings generated: {findings.generated_at}\n"
        f"- Governor generated: {governor.generated_at}"
    )

    replacements = {
        "{{PROJECT_NAME}}": intake.project_name,
        "{{CASE_ID}}": case_manager.case_short_id(case_dir),
        "{{GENERATED_AT}}": datetime.now(timezone.utc).isoformat(),
        "{{EXECUTIVE_SUMMARY}}": executive_summary,
        "{{PROJECT_OVERVIEW}}": project_overview,
        "{{USER_CLAIM}}": intake.user_claim,
        "{{WHAT_WAS_FOUND}}": what_was_found,
        "{{EVIDENCE_SUMMARY}}": evidence_summary,
        "{{TECHNICAL_FINDINGS}}": technical_findings,
        "{{PLAIN_LANGUAGE_FINDINGS}}": plain_language_findings,
        "{{WHY_IT_MATTERS}}": why_it_matters,
        "{{PRIVACY_SECURITY_NOTES}}": privacy_security_notes,
        "{{CONFIDENCE_LIMITATIONS}}": confidence_limitations,
        "{{RECOMMENDED_NEXT_ACTIONS}}": recommended_next_actions,
        "{{GOVERNOR_NOTES}}": governor_notes,
        "{{CASE_METADATA}}": case_metadata,
    }

    base_dir = case_dir.parent.parent
    template_path = base_dir / "templates" / "report_template.md"
    if not template_path.exists():
        return PhaseStatus(status="failed", phase="report", reason=f"Template not found: {template_path}")
    rendered = template_path.read_text()
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    missing_sections = [s for s in REQUIRED_SECTIONS if s not in rendered]
    if missing_sections:
        return PhaseStatus(
            status="failed", phase="report",
            reason=f"Template is missing required sections: {missing_sections}",
        )
    if "{{" in rendered:
        return PhaseStatus(
            status="failed", phase="report",
            reason="Template still contains unfilled placeholders after rendering.",
        )

    (case_dir / "report.md").write_text(rendered)
    return PhaseStatus(status="ok", phase="report", reason=None)
