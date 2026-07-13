"""
Law 7: All JSON artifacts are pydantic models. A malformed artifact must be
structurally impossible to write, not just discouraged in a docstring.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Law 4: every phase function returns one of these instead of relying on
# side-effect files to signal success.
# ---------------------------------------------------------------------------
class PhaseStatus(BaseModel):
    status: Literal["ok", "failed"]
    phase: str
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 2 — intake.json
# ---------------------------------------------------------------------------
INTAKE_REQUIRED_FIELDS = [
    "project_name", "source_type", "user_claim", "user_pain",
    "desired_outcome", "audience", "privacy_level",
]


class Intake(BaseModel):
    """
    Phase 1 (new-case) writes this schema-valid but with required fields
    empty. Phase 2 (intake) fills them in via a re-prompting terminal loop
    and re-validates. Because case creation must produce a schema-valid
    *empty* placeholder, required-field non-emptiness is enforced by
    is_complete() rather than a pydantic min_length constraint — downstream
    phases call is_complete() as their Law 3 prerequisite check.
    """
    case_id: Optional[str] = None
    project_name: str = ""
    source_type: Literal["folder", "zip", "repo"] = "folder"
    user_claim: str = ""
    user_pain: str = ""
    desired_outcome: str = ""
    audience: str = ""
    privacy_level: Literal["public", "internal", "confidential"] = "internal"
    scope_limit: Optional[str] = None
    source_reference: Optional[str] = None
    created_at: Optional[str] = None

    def is_complete(self) -> bool:
        return all(getattr(self, field) for field in INTAKE_REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# Phase 4 — scan.json
#
# Law 8: "not detected" (detected=False, we looked and it isn't there) and
# "does not exist" are never conflated. Every detection field carries both
# a boolean and a confidence, never a bare exists flag.
# ---------------------------------------------------------------------------
class Detection(BaseModel):
    detected: bool
    confidence: Confidence


class ManifestDetections(BaseModel):
    package_json: Detection
    requirements_txt: Detection
    pyproject_toml: Detection
    dockerfile: Detection
    ci_config: Detection
    readme: Detection
    license_file: Detection
    tests_dir: Detection
    env_example: Detection
    gitignore: Detection


class LargeFile(BaseModel):
    path: str
    size_bytes: int


class SymbolEntry(BaseModel):
    kind: str
    name: str
    line: int = Field(ge=1)


class SymbolicNode(BaseModel):
    path: str
    language: str
    bytes: int = Field(ge=0)
    tokens_est: int = Field(ge=0)
    symbols: list[SymbolEntry] = Field(default_factory=list)


class SymbolicCompression(BaseModel):
    """
    Symbolic map of the codebase's source files, ported from delta-scp's
    compressTree() (services/delta-scp/src/compressor.ts). Only files
    matching delta-scp's INCLUDE_EXT allowlist are read here — images,
    binaries, and lockfiles never reach this list. scan.json's own
    file_count/extension_counts above still cover 100% of source/.
    """
    files_included: int = Field(ge=0)
    raw_tokens_est: int = Field(ge=0)
    compressed_tokens_est: int = Field(ge=0)
    token_yield: int
    compression_ratio: float = Field(ge=0)
    symbolic_nodes: list[SymbolicNode] = Field(default_factory=list)


class ScanResult(BaseModel):
    case_id: str
    generated_at: str
    started_at: Optional[str] = None
    file_count: int = Field(ge=0)
    dir_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    extension_counts: dict[str, int] = Field(default_factory=dict)
    languages_detected: list[str] = Field(default_factory=list)
    manifests: ManifestDetections
    largest_files: list[LargeFile] = Field(default_factory=list)
    top_level_entries: list[str] = Field(default_factory=list)
    symbolic_compression: SymbolicCompression
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 5 — findings.json
# ---------------------------------------------------------------------------
class Finding(BaseModel):
    id: str
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: Confidence
    evidence: list[str] = Field(min_length=1)
    plain_language: str = Field(min_length=1)
    technical_finding: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    recommended_next_action: str = Field(min_length=1)


class FindingsResult(BaseModel):
    case_id: str
    generated_at: str
    findings: list[Finding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 6 — governor_report.json
# ---------------------------------------------------------------------------
class GovernorCheck(BaseModel):
    name: str
    passed: bool
    notes: str = ""


class GovernorReport(BaseModel):
    case_id: str
    generated_at: str
    status: Literal["approved", "needs_review", "blocked"]
    checklist: list[GovernorCheck] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=1200)


# ---------------------------------------------------------------------------
# Phase 8 — ledger_entry.json
# ---------------------------------------------------------------------------
class TopFinding(BaseModel):
    id: str
    title: str
    severity: str
    confidence: Confidence


class LedgerEntry(BaseModel):
    case_id: str
    project_name: str
    created_at: Optional[str] = None
    generated_at: str
    phases_completed: list[str] = Field(default_factory=list)
    top_findings: list[TopFinding] = Field(default_factory=list)
    governor_status: Optional[str] = None
    report_generated: bool = False
    scan_duration_seconds: Optional[float] = None
