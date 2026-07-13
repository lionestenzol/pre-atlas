"""
Phase 4 — deterministic scanner. No LLM calls in this file, ever.
Writes only scan.json (Law 2).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from core import case_manager, symbols
from core.models import Detection, LargeFile, ManifestDetections, PhaseStatus, ScanResult

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

EXTENSION_LANGUAGE = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cs": "C#", ".rs": "Rust",
    ".swift": "Swift", ".kt": "Kotlin", ".sh": "Shell", ".sql": "SQL", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
    ".md": "Markdown",
}

CI_PATTERNS = [
    ".github/workflows", ".gitlab-ci.yml", ".circleci", "azure-pipelines.yml",
    "Jenkinsfile", ".travis.yml",
]
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs"}


def _detect(found: bool) -> Detection:
    return Detection(detected=found, confidence="high")


def _find_top_level_ci(source_dir: Path) -> bool:
    for pattern in CI_PATTERNS:
        if (source_dir / pattern).exists():
            return True
    return False


def _find_any(source_dir: Path, names_lower_prefixes: set[str]) -> bool:
    try:
        for entry in source_dir.iterdir():
            if entry.name.lower().split(".")[0] in names_lower_prefixes:
                return True
    except FileNotFoundError:
        return False
    return False


def run_scan(case_id: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="scan", reason=str(exc))

    # Law 3: verify our own prerequisites, don't trust call order.
    source_dir = case_dir / "source"
    if not source_dir.exists():
        return PhaseStatus(
            status="failed",
            phase="scan",
            reason=f"source/ does not exist for this case. Run 'load' first: {source_dir}",
        )

    started_at = datetime.now(timezone.utc).isoformat()

    file_count = 0
    dir_count = 0
    total_size = 0
    extension_counts: dict[str, int] = {}
    largest_files: list[LargeFile] = []
    symbol_rel_paths: list[str] = []
    warnings: list[str] = []
    has_tests_dir = False

    for path in source_dir.rglob("*"):
        rel_parts = path.relative_to(source_dir).parts
        if any(part in IGNORE_DIRS for part in rel_parts):
            continue
        if path.is_dir():
            dir_count += 1
            if path.name.lower() in TEST_DIR_NAMES:
                has_tests_dir = True
            continue
        if path.is_symlink():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            warnings.append(f"Could not stat file: {path}")
            continue

        file_count += 1
        total_size += size
        ext = path.suffix.lower() or "(no extension)"
        extension_counts[ext] = extension_counts.get(ext, 0) + 1
        rel_path = str(path.relative_to(source_dir))
        largest_files.append(LargeFile(path=rel_path, size_bytes=size))
        if symbols.include_file(path.name):
            symbol_rel_paths.append(rel_path)

    largest_files.sort(key=lambda f: f.size_bytes, reverse=True)
    largest_files = largest_files[:10]

    languages_detected = sorted(
        {EXTENSION_LANGUAGE[ext] for ext in extension_counts if ext in EXTENSION_LANGUAGE}
    )

    top_level_entries = sorted(
        p.name for p in source_dir.iterdir() if p.name not in IGNORE_DIRS
    ) if source_dir.exists() else []

    if file_count == 0:
        warnings.append("source/ contains no files.")

    manifests = ManifestDetections(
        package_json=_detect((source_dir / "package.json").is_file()),
        requirements_txt=_detect((source_dir / "requirements.txt").is_file()),
        pyproject_toml=_detect((source_dir / "pyproject.toml").is_file()),
        dockerfile=_detect(_find_any(source_dir, {"dockerfile"})),
        ci_config=_detect(_find_top_level_ci(source_dir)),
        readme=_detect(_find_any(source_dir, {"readme"})),
        license_file=_detect(_find_any(source_dir, {"license", "licence"})),
        tests_dir=_detect(has_tests_dir),
        env_example=_detect(_find_any(source_dir, {".env"}) or (source_dir / ".env.example").is_file()),
        gitignore=_detect((source_dir / ".gitignore").is_file()),
    )

    symbolic_compression = symbols.compress_tree(source_dir, symbol_rel_paths, warnings)

    try:
        scan = ScanResult(
            case_id=case_manager.case_short_id(case_dir),
            generated_at=datetime.now(timezone.utc).isoformat(),
            started_at=started_at,
            file_count=file_count,
            dir_count=dir_count,
            total_size_bytes=total_size,
            extension_counts=extension_counts,
            languages_detected=languages_detected,
            manifests=manifests,
            largest_files=largest_files,
            top_level_entries=top_level_entries,
            symbolic_compression=symbolic_compression,
            warnings=warnings,
        )
    except ValidationError as exc:
        return PhaseStatus(status="failed", phase="scan", reason=str(exc))

    case_manager.write_json(case_dir / "scan.json", scan.model_dump())
    return PhaseStatus(status="ok", phase="scan", reason=None)
