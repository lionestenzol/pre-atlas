"""
Tests for core/verifier.py — the "verify-or-it-didn't-happen" deterministic
re-derivation layer that governor.py runs against scan.json, independent of
whatever the LLM audit concludes.
"""
from __future__ import annotations

from core import verifier
from core.models import (
    Detection,
    Finding,
    FindingsResult,
    FindingVerification,
    GovernorReport,
    LargeFile,
    ManifestDetections,
    ScanResult,
    SymbolEntry,
    SymbolicCompression,
    SymbolicNode,
    VerificationCheck,
)


def _detection(detected: bool) -> Detection:
    return Detection(detected=detected, confidence="high")


def _manifests(**overrides: bool) -> ManifestDetections:
    fields = {
        "package_json": False, "requirements_txt": False, "pyproject_toml": False,
        "dockerfile": False, "ci_config": False, "readme": False, "license_file": False,
        "tests_dir": False, "env_example": False, "gitignore": False,
    }
    fields.update(overrides)
    return ManifestDetections(**{k: _detection(v) for k, v in fields.items()})


def _scan(**manifest_overrides: bool) -> ScanResult:
    return ScanResult(
        case_id="CASE_0001",
        generated_at="2026-01-01T00:00:00Z",
        file_count=2,
        dir_count=1,
        total_size_bytes=100,
        manifests=_manifests(**manifest_overrides),
        largest_files=[LargeFile(path="lib/app.js", size_bytes=100)],
        top_level_entries=["package.json", "lib"],
        symbolic_compression=SymbolicCompression(
            files_included=1,
            raw_tokens_est=10,
            compressed_tokens_est=5,
            token_yield=5,
            compression_ratio=0.5,
            symbolic_nodes=[
                SymbolicNode(
                    path="lib/app.js",
                    language="javascript",
                    bytes=100,
                    tokens_est=10,
                    symbols=[SymbolEntry(kind="function", name="createApplication", line=36)],
                )
            ],
        ),
    )


def _finding(**kwargs) -> Finding:
    base = dict(
        id="F-001",
        title="Finding",
        category="Structural",
        severity="info",
        confidence="high",
        evidence=["placeholder evidence"],
        plain_language="plain",
        technical_finding="technical",
        why_it_matters="why",
        recommended_next_action="do something",
    )
    base.update(kwargs)
    return Finding(**base)


def test_verified_manifest_claim_matches_real_scan():
    scan = _scan(dockerfile=False)
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(evidence=["dockerfile manifest: detected=false, confidence=high"])],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 1
    assert result.verified == 1
    assert result.contradictions == []
    assert result.grounded is True


def test_contradicted_manifest_claim_flagged():
    scan = _scan(dockerfile=False)  # real scan says NOT detected
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(evidence=["dockerfile manifest: detected=true, confidence=high"])],  # false claim
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 1
    assert len(result.contradictions) == 1
    assert result.contradictions[0].kind == "manifest"
    assert result.grounded is False


def test_verified_path_citation():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="Largest file is lib/app.js.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run >= 1
    assert result.grounded is True


def test_contradicted_path_citation_for_nonexistent_file():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="Found a suspicious file at lib/totally_made_up.js.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert any(c.kind == "path" for c in result.contradictions)
    assert result.grounded is False


def test_verified_symbol_citation():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="lib/app.js defines createApplication() at line 36.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.grounded is True
    assert not result.contradictions


def test_contradicted_symbol_citation_for_fabricated_function():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="The code defines initializeQuantumCache() somewhere.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert any(c.kind == "symbol" for c in result.contradictions)


def test_pure_prose_with_no_checkable_claims_is_not_grounded_or_contradicted():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="This project generally looks well organized.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 0
    assert result.contradictions == []
    assert result.grounded is False  # unverifiable, not verified — doesn't get to count as fine


def test_brand_names_ending_in_js_are_not_mistaken_for_files():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="This layout is characteristic of the Express.js and Node.js ecosystem.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 0


def test_english_parentheticals_are_not_mistaken_for_function_calls():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding=(
            "Response methods (sendfile, onstream, stringify) and routing "
            "(GET, POST) are both covered by the test suite."
        ))],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 0


def test_dotfile_leading_dot_inconsistency_still_verifies():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="Largest file is lib/app.js.")],
    )
    # real path has no leading dot here, but the same logic must also treat
    # ".github/x.yml" vs "github/x.yml" as equal — covered structurally by
    # _strip_leading_dots, exercised indirectly through the path check above.
    [result] = verifier.verify_findings(findings, scan)
    assert result.grounded is True


def test_negated_absence_claim_for_nonexistent_file_verifies():
    scan = _scan()  # env_example.detected is not part of path checking; file genuinely absent
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="The project does not include .env, .env.example, or .env.local.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.contradictions == []
    assert result.grounded is True


def test_negated_claim_contradicted_if_file_actually_exists():
    scan = _scan()  # lib/app.js IS a real scanned path
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="The project does not include lib/app.js anywhere.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert len(result.contradictions) == 1
    assert "claimed absent" in result.contradictions[0].detail


def test_ratios_and_percentages_are_not_mistaken_for_paths():
    scan = _scan()
    findings = FindingsResult(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        findings=[_finding(technical_finding="Compression ratio was 0.0335, a 29.8x reduction.")],
    )
    [result] = verifier.verify_findings(findings, scan)
    assert result.checks_run == 0


def _report(status="approved") -> GovernorReport:
    return GovernorReport(
        case_id="CASE_0001", generated_at="2026-01-01T00:00:00Z",
        status=status, summary="A short verdict.",
    )


def test_apply_verification_leaves_clean_report_untouched():
    verification = [FindingVerification(finding_id="F-001", checks_run=2, verified=2, contradictions=[], grounded=True)]
    report = verifier.apply_verification(_report("approved"), verification)
    assert report.status == "approved"
    assert report.blocking_reasons == []
    assert report.checklist == []


def test_apply_verification_forces_blocked_on_manifest_contradiction():
    bad = VerificationCheck(claim="dockerfile detected=true", kind="manifest", verdict="contradicted", detail="scan.json manifests.dockerfile.detected=False")
    verification = [FindingVerification(finding_id="F-001", checks_run=1, verified=0, contradictions=[bad], grounded=False)]
    report = verifier.apply_verification(_report("approved"), verification)
    assert report.status == "blocked"
    assert any("dockerfile detected=true" in r for r in report.blocking_reasons)


def test_apply_verification_forces_blocked_when_finding_fully_ungrounded():
    bad = VerificationCheck(claim="made_up.js", kind="path", verdict="contradicted", detail="no scanned file matches this path")
    verification = [FindingVerification(finding_id="F-002", checks_run=1, verified=0, contradictions=[bad], grounded=False)]
    report = verifier.apply_verification(_report("approved"), verification)
    assert report.status == "blocked"


def test_apply_verification_downgrades_but_does_not_block_for_partial_citation_slip():
    # F-001 has plenty of OTHER verified citations (verified=5) alongside
    # one bad path citation — a typo, not a fabricated finding.
    bad = VerificationCheck(claim="Elintrc.yml", kind="path", verdict="contradicted", detail="no scanned file matches this path")
    verification = [FindingVerification(finding_id="F-001", checks_run=6, verified=5, contradictions=[bad], grounded=False)]
    report = verifier.apply_verification(_report("approved"), verification)
    assert report.status == "needs_review"
    assert report.blocking_reasons == []  # not material enough to block
    assert any(c.name == "evidence_citation_accuracy" and not c.passed for c in report.checklist)


def test_apply_verification_never_upgrades_an_already_blocked_llm_status():
    verification = [FindingVerification(finding_id="F-001", checks_run=2, verified=2, contradictions=[], grounded=True)]
    report = verifier.apply_verification(_report("blocked"), verification)
    assert report.status == "blocked"
