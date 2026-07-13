"""
Phase 8 — ledger. Law 9: read-only. Takes no interactive input, only reads
artifacts and timestamps already on disk.

The category tally, source split, and governance tax below are ported from
bearings' zero-LLM "where am I" digest
(~/.claude/scripts/bearings/bearings.py): a deterministic parse of what's
already on disk, never a re-derivation. Same discipline this file already
had (Law 9); this just gives it bearings' specific shape — a categorized
tally instead of a flat top-N list, an honest split instead of a raw file
count, and a shipped/blocked accounting instead of a bare status string.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from core import case_manager
from core.models import (
    CategoryTally,
    FindingsResult,
    GovernanceTax,
    GovernorReport,
    Intake,
    LedgerEntry,
    PhaseStatus,
    ScanResult,
    SourceSplit,
    TopFinding,
)

TOP_N_FINDINGS = 5

# Ported verbatim from bearings' DOC_EXTS/DATA_EXTS/PRODUCT_EXTS
# (bearings.py:52-55). Bearings classifies by full path (generated-bloat
# markers like node_modules/ take priority); scan.json's extension_counts
# only preserves extension, not path, so the "generated" bucket isn't
# reproducible here — an honest scope gap, not a silent drop. node_modules
# et al. are already excluded upstream by scanner.py's IGNORE_DIRS, which
# covers most of what that bucket would have caught anyway.
_DOC_EXTS = {".md", ".mdx", ".rst", ".txt"}
_DATA_EXTS = {".json", ".yaml", ".yml", ".csv", ".lock", ".html"}
_PRODUCT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".css", ".scss", ".sh", ".ps1", ".sql",
}


def _classify_ext(ext: str) -> str:
    if ext in _DOC_EXTS:
        return "docs"
    if ext in _PRODUCT_EXTS:
        return "product"
    if ext in _DATA_EXTS:
        return "data"
    return "other"


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
    findings_by_category: list[CategoryTally] = []
    source_split = None
    governance_tax = None
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

            split_counts = {"product": 0, "docs": 0, "data": 0, "other": 0}
            for ext, count in scan.extension_counts.items():
                split_counts[_classify_ext(ext)] += count
            source_split = SourceSplit(**split_counts)
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

            category_counts: dict[str, int] = {}
            for f in findings.findings:
                category_counts[f.category] = category_counts.get(f.category, 0) + 1
            findings_by_category = [
                CategoryTally(category=cat, count=n) for cat, n in sorted(category_counts.items())
            ]
        except ValidationError:
            pass

    governor_path = case_dir / "governor_report.json"
    if governor_path.exists():
        try:
            governor = GovernorReport.model_validate(case_manager.read_json(governor_path))
            phases_completed.append("govern")
            governor_status = governor.status

            checks_run = sum(v.checks_run for v in governor.verification)
            checks_verified = sum(v.verified for v in governor.verification)
            governance_tax = GovernanceTax(
                shipped=report_generated and governor.status != "blocked",
                checks_run=checks_run,
                checks_verified=checks_verified,
                blocked_reasons=governor.blocking_reasons if governor.status == "blocked" else [],
            )
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
        findings_by_category=findings_by_category,
        source_split=source_split,
        governance_tax=governance_tax,
        governor_status=governor_status,
        report_generated=report_generated,
        scan_duration_seconds=scan_duration_seconds,
    )

    case_manager.write_json(case_dir / "ledger_entry.json", ledger.model_dump())
    return PhaseStatus(status="ok", phase="ledger", reason=None)
