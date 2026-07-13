"""
Custom promptfoo assertions for the analyze/govern eval suite. Each
function receives the JSON string returned by provider.py's call_api() and
re-validates it against the real Pydantic schemas (core/models.py) and the
real deterministic verifier (core/verifier.py) — the same code the CLI
itself trusts, not an eval-only reimplementation of the rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from core import verifier
from core.models import FindingsResult, GovernorReport, ScanResult

SUMMARY_TARGET_CHARS = 800  # governor.SYSTEM_PROMPT's brevity instruction;
# the schema only hard-caps at 1200 (core/models.py), so this checks the
# tighter intended target, not just the hard ceiling.


def _load(output: str) -> dict:
    return json.loads(output)


def schema_valid(output, context):
    data = _load(output)
    phase = data.get("phase")
    try:
        if phase == "analyze":
            FindingsResult.model_validate(data["findings"])
        elif phase == "govern":
            GovernorReport.model_validate(data["governor_report"])
        else:
            return {"pass": False, "score": 0.0, "reason": f"unknown phase '{phase}'"}
    except ValidationError as exc:
        return {"pass": False, "score": 0.0, "reason": f"schema invalid: {exc}"}
    return {"pass": True, "score": 1.0, "reason": "output validates against the pydantic schema"}


def findings_grounded(output, context):
    """analyze phase: findings must not trip verifier.py's contradiction
    checks against the real scan.json — a contradicted claim means the
    model cited a manifest/path/symbol that doesn't exist in the scan."""
    data = _load(output)
    if data.get("phase") != "analyze":
        return True  # not applicable to this test case

    findings = FindingsResult.model_validate(data["findings"])
    scan = ScanResult.model_validate(data["scan"])
    verifications = verifier.verify_findings(findings, scan)
    contradicted = [
        (v.finding_id, c.claim, c.detail)
        for v in verifications
        for c in v.contradictions
    ]
    if contradicted:
        detail = "; ".join(f"{fid}: '{claim}' ({why})" for fid, claim, why in contradicted)
        return {"pass": False, "score": 0.0, "reason": f"{len(contradicted)} contradicted claim(s): {detail}"}
    return {
        "pass": True,
        "score": 1.0,
        "reason": f"{len(verifications)} finding(s), 0 contradictions",
    }


def summary_under_cap(output, context):
    """govern phase: summary should respect the SYSTEM_PROMPT's 800-char
    brevity target, not just the schema's 1200-char hard ceiling."""
    data = _load(output)
    if data.get("phase") != "govern":
        return True

    report = GovernorReport.model_validate(data["governor_report"])
    length = len(report.summary)
    if length > SUMMARY_TARGET_CHARS:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"summary is {length} chars, over the {SUMMARY_TARGET_CHARS}-char target",
        }
    return {"pass": True, "score": 1.0, "reason": f"summary is {length} chars"}


def no_forced_blocks_from_fabrication(output, context):
    """govern phase: verifier.apply_verification() (already applied inside
    run_govern) only forces status='blocked' on a manifest contradiction or
    a fully-ungrounded finding — see core/verifier.py:apply_verification.
    This asserts the govern pass didn't trip that on the real Express
    fixture, i.e. it didn't fabricate or misstate evidence in its audit."""
    data = _load(output)
    if data.get("phase") != "govern":
        return True

    report = GovernorReport.model_validate(data["governor_report"])
    fabricated = [r for r in report.blocking_reasons if r.startswith("CONTRADICTED (code-verified)")]
    if fabricated:
        return {"pass": False, "score": 0.0, "reason": "; ".join(fabricated)}
    return {"pass": True, "score": 1.0, "reason": "no code-verified contradictions forced a block"}
