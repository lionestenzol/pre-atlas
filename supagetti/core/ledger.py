"""
Phase 8 — ledger. Law 9: read-only. Takes no interactive input, only reads
artifacts and timestamps already on disk.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from core import case_manager
from core.models import (
    FindingsResult,
    GovernorReport,
    Intake,
    LedgerEntry,
    PhaseStatus,
    ScanResult,
    TopFinding,
)

TOP_N_FINDINGS = 5


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return order.get(severity, 5)


def run_ledger(case_id: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="ledger", reason=str(exc))

    # Law 3: ledger's only hard prerequisite is intake.json (needs
    # case_id/project_name to exist at all). Everything else is optional
    # and tracked via phases_completed — ledger reads whatever is on disk,
    # it never asks (Law 9).
    intake_path = case_dir / "intake.json"
    if not intake_path.exists():
        return PhaseStatus(status="failed", phase="ledger", reason="intake.json missing.")

    try:
        intake = Intake.model_validate(case_manager.read_json(intake_path))
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="ledger", reason=f"intake.json invalid: {exc}")

    phases_completed = ["intake"]
    scan_duration_seconds = None
    top_findings: list[TopFinding] = []
    governor_status = None
    report_generated = (case_dir / "report.md").exists()

    if (case_dir / "source").exists() and any((case_dir / "source").iterdir()):
        phases_completed.append("load")

    scan_path = case_dir / "scan.json"
    if scan_path.exists():
        try:
            scan = ScanResult.model_validate(case_manager.read_json(scan_path))
            phases_completed.append("scan")
            if scan.started_at:
                start = datetime.fromisoformat(scan.started_at)
                end = datetime.fromisoformat(scan.generated_at)
                scan_duration_seconds = (end - start).total_seconds()
        except ValidationError:
            pass

    findings_path = case_dir / "findings.json"
    if findings_path.exists():
        try:
            findings = FindingsResult.model_validate(case_manager.read_json(findings_path))
            phases_completed.append("analyze")
            ranked = sorted(findings.findings, key=lambda f: _severity_rank(f.severity))
            top_findings = [
                TopFinding(id=f.id, title=f.title, severity=f.severity, confidence=f.confidence)
                for f in ranked[:TOP_N_FINDINGS]
            ]
        except ValidationError:
            pass

    governor_path = case_dir / "governor_report.json"
    if governor_path.exists():
        try:
            governor = GovernorReport.model_validate(case_manager.read_json(governor_path))
            phases_completed.append("govern")
            governor_status = governor.status
        except ValidationError:
            pass

    if report_generated:
        phases_completed.append("report")

    ledger = LedgerEntry(
        case_id=case_manager.case_short_id(case_dir),
        project_name=intake.project_name,
        created_at=intake.created_at,
        generated_at=datetime.now(timezone.utc).isoformat(),
        phases_completed=phases_completed,
        top_findings=top_findings,
        governor_status=governor_status,
        report_generated=report_generated,
        scan_duration_seconds=scan_duration_seconds,
    )

    case_manager.write_json(case_dir / "ledger_entry.json", ledger.model_dump())
    return PhaseStatus(status="ok", phase="ledger", reason=None)
