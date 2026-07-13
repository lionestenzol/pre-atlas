"""
Phase 6 (govern) evidence verification. No LLM calls in this file, ever.

Ports code-recon's "verify-or-it-didn't-happen" discipline into govern: a
finding's claims only count as grounded if they can be independently
re-derived from real scan data — not because a model (the same one that
wrote them, or a second one auditing them) says so. This moves trust from
"LLM audits LLM" to "code checks against source" for the specific claim
shapes below.

Deliberately narrow scope, matching delta-scp's own heuristic-not-AST
posture: three checkable claim shapes only — manifest detection state,
file-path citations, and symbol-name citations. Free-form prose ("this
looks well-tested") is neither verified nor contradicted; it simply isn't a
checkable claim, and it never gets to borrow the confidence of the claims
that are.
"""
from __future__ import annotations

import re

from core.models import (
    Finding,
    FindingsResult,
    FindingVerification,
    GovernorCheck,
    GovernorReport,
    ManifestDetections,
    ScanResult,
    VerificationCheck,
)

_MANIFEST_FIELDS = (
    "package_json", "requirements_txt", "pyproject_toml", "dockerfile",
    "ci_config", "readme", "license_file", "tests_dir", "env_example", "gitignore",
)

# Matches the model's own snake_case-echo phrasing, e.g. "dockerfile
# manifest: detected=false, confidence=high" or "ci_config manifest
# detected=true with high confidence" — observed verbatim across every
# analyze run against this scanner. Deliberately anchored to the exact
# field names in ManifestDetections so a match can only mean one real
# field, never a fuzzy human paraphrase that could misfire.
_MANIFEST_RE = re.compile(
    r"\b(" + "|".join(_MANIFEST_FIELDS) + r")\b[^.]{0,40}?detected\s*[:=]\s*(true|false)",
    re.IGNORECASE,
)

# Path-shaped tokens: word/slash/dot runs ending in a short alphabetic
# extension. Requiring the suffix to be alphabetic (not digits) excludes
# percentages, ratios, and version numbers (e.g. "29.8x", "0.0335").
_PATH_RE = re.compile(r"\b[\w][\w./\\-]*\.[A-Za-z]{1,6}\b")

# Path-shaped tokens that are never real repo files — tech/brand names that
# happen to end in a real extension (e.g. "Node.js" reads exactly like a
# filename to a regex but is a runtime, not a path in this repo).
_PATH_DENYLIST = {
    "node.js", "express.js", "react.js", "vue.js", "angular.js", "next.js",
    "jquery.js", "d3.js", "three.js", "e.g", "i.e", "etc",
}

# An identifier immediately followed by empty parens with NO whitespace in
# between — i.e. "createApplication()", not "methods (GET, POST)". The
# latter is an ordinary English parenthetical, not a function-call
# citation, and space-before-paren is how the two are told apart in prose.
_SYMBOL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\(\)")


def _finding_text(finding: Finding) -> str:
    return "\n".join([finding.title, finding.technical_finding, finding.plain_language, *finding.evidence])


def _real_paths(scan: ScanResult) -> set[str]:
    paths = set(scan.top_level_entries)
    paths.update(f.path.replace("\\", "/") for f in scan.largest_files)
    paths.update(n.path.replace("\\", "/") for n in scan.symbolic_compression.symbolic_nodes)
    return paths


def _real_symbols(scan: ScanResult) -> set[str]:
    return {s.name for node in scan.symbolic_compression.symbolic_nodes for s in node.symbols}


def _check_manifests(text: str, manifests: ManifestDetections) -> list[VerificationCheck]:
    checks = []
    for m in _MANIFEST_RE.finditer(text):
        field, claimed = m.group(1).lower(), m.group(2).lower() == "true"
        real = getattr(manifests, field).detected
        checks.append(VerificationCheck(
            claim=m.group(0).strip(),
            kind="manifest",
            verdict="verified" if claimed == real else "contradicted",
            detail=f"scan.json manifests.{field}.detected={real}",
        ))
    return checks


def _strip_leading_dots(path: str) -> str:
    """".github/dependabot.yml" and "github/dependabot.yml" should compare
    equal — evidence prose is inconsistent about leading dots on dotfiles/
    dotdirs, and that's a prose-style difference, not a wrong claim."""
    return "/".join(seg.lstrip(".") for seg in path.split("/"))


# Cues that flip a path mention from "this file exists" to "this file is
# absent" — e.g. "do not include .env.local". Checked against the text
# immediately before the match, up to the previous sentence boundary, so a
# negation earlier in the paragraph can't leak into an unrelated claim.
_NEGATION_CUES = (
    "do not include", "does not include", "no evidence of", "not detected",
    "does not exist", "not found", "absent", "missing", "without a",
    "lacks a", "excludes",
)

# A period/!/? only counts as a sentence boundary when followed by
# whitespace — a bare "." can just as easily be the dot inside ".env" or
# ".eslintrc.yml", which must NOT truncate the negation-lookback window.
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?](?=\s)|\n")


def _is_negated_context(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - 80):match_start]
    boundaries = list(_SENTENCE_BOUNDARY_RE.finditer(window))
    if boundaries:
        window = window[boundaries[-1].end():]
    return any(cue in window.lower() for cue in _NEGATION_CUES)


def _check_paths(text: str, real_paths: set[str]) -> list[VerificationCheck]:
    normalized_real = {_strip_leading_dots(p.replace("\\", "/")) for p in real_paths}
    checks = []
    seen: set[str] = set()
    for m in _PATH_RE.finditer(text):
        token = m.group(0)
        if token in seen:
            continue
        seen.add(token)
        if token.lower() in _PATH_DENYLIST:
            continue
        stem = token.rsplit(".", 1)[0]
        if not any(c.isalpha() for c in stem):
            continue  # e.g. "29.8x" slipping past the suffix guard
        normalized = _strip_leading_dots(token.replace("\\", "/"))
        found = any(
            p == normalized or p.endswith("/" + normalized) or normalized.endswith("/" + p)
            for p in normalized_real
        )
        if _is_negated_context(text, m.start()):
            verdict = "verified" if not found else "contradicted"
            detail = (
                "correctly cited as absent from the scan"
                if not found
                else "claimed absent but a scanned file matches this path"
            )
        else:
            verdict = "verified" if found else "contradicted"
            detail = "matched a real scanned path" if found else "no scanned file matches this path"
        checks.append(VerificationCheck(claim=token, kind="path", verdict=verdict, detail=detail))
    return checks


def _check_symbols(text: str, real_symbols: set[str]) -> list[VerificationCheck]:
    checks = []
    seen: set[str] = set()
    for m in _SYMBOL_RE.finditer(text):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        found = name in real_symbols
        checks.append(VerificationCheck(
            claim=f"{name}()",
            kind="symbol",
            verdict="verified" if found else "contradicted",
            detail="matched an extracted symbol" if found else "no extracted symbol has this name",
        ))
    return checks


def verify_findings(findings: FindingsResult, scan: ScanResult) -> list[FindingVerification]:
    real_paths = _real_paths(scan)
    real_symbols = _real_symbols(scan)
    results = []
    for finding in findings.findings:
        text = _finding_text(finding)
        checks = (
            _check_manifests(text, scan.manifests)
            + _check_paths(text, real_paths)
            + _check_symbols(text, real_symbols)
        )
        contradictions = [c for c in checks if c.verdict == "contradicted"]
        results.append(FindingVerification(
            finding_id=finding.id,
            checks_run=len(checks),
            verified=len(checks) - len(contradictions),
            contradictions=contradictions,
            grounded=len(checks) > 0 and not contradictions,
        ))
    return results


def apply_verification(report: GovernorReport, verification: list[FindingVerification]) -> GovernorReport:
    """
    Deterministically tighten an LLM-produced GovernorReport using
    verify_findings() output. A manifest contradiction (a boolean fact check
    gone wrong — exactly the "detection_conflation" failure mode the prompt
    already names) or a finding with zero verified claims backing it up
    forces status="blocked", regardless of what the LLM concluded. A
    citation slip inside an otherwise well-grounded finding downgrades
    status to at most "needs_review" and is recorded in the checklist, not
    blocking_reasons — a single wrong filename in a paragraph of otherwise
    verified evidence isn't material enough to block distribution on its
    own, but it must never be silently waved through as "approved" either.
    """
    report.verification = verification
    force_blocked = False
    soft_notes: list[str] = []

    for v in verification:
        if not v.contradictions:
            continue
        manifest_hit = any(c.kind == "manifest" for c in v.contradictions)
        fully_ungrounded = v.verified == 0
        descriptions = [f'finding {v.finding_id} claims "{c.claim}" but {c.detail}' for c in v.contradictions]
        if manifest_hit or fully_ungrounded:
            force_blocked = True
            for d in descriptions:
                reason = f"CONTRADICTED (code-verified): {d}."
                if reason not in report.blocking_reasons:
                    report.blocking_reasons.append(reason)
        else:
            soft_notes.extend(descriptions)

    if force_blocked:
        report.status = "blocked"
    elif soft_notes and report.status == "approved":
        report.status = "needs_review"

    if soft_notes:
        report.checklist.append(GovernorCheck(
            name="evidence_citation_accuracy",
            passed=False,
            notes="Code-verified citation issue(s), not material enough to block: " + "; ".join(soft_notes),
        ))
    return report
