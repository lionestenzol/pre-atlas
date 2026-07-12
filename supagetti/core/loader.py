"""Phase 3 — source loading. Three loaders behind one interface."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

from core import case_manager
from core.models import PhaseStatus


def _record_source_reference(case_dir: Path, source_type: str, reference: str) -> None:
    intake_path = case_dir / "intake.json"
    data = case_manager.read_json(intake_path) if intake_path.exists() else {}
    data["source_type"] = source_type
    data["source_reference"] = reference
    case_manager.write_json(intake_path, data)


def _clear_source_dir(source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    for child in source_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def load_folder(case_id: str, folder_path: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="load", reason=str(exc))

    src = Path(folder_path).expanduser().resolve()
    if not src.is_dir():
        return PhaseStatus(
            status="failed", phase="load", reason=f"Folder not found: {src}"
        )

    source_dir = case_dir / "source"
    _clear_source_dir(source_dir)
    shutil.copytree(src, source_dir, dirs_exist_ok=True)

    _record_source_reference(case_dir, "folder", str(src))
    return PhaseStatus(status="ok", phase="load", reason=None)


def load_zip(case_id: str, zip_path: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="load", reason=str(exc))

    src = Path(zip_path).expanduser().resolve()
    if not src.is_file():
        return PhaseStatus(
            status="failed", phase="load", reason=f"Zip file not found: {src}"
        )
    if not zipfile.is_zipfile(src):
        return PhaseStatus(
            status="failed", phase="load", reason=f"Not a valid zip file: {src}"
        )

    source_dir = case_dir / "source"
    _clear_source_dir(source_dir)
    with zipfile.ZipFile(src) as zf:
        zf.extractall(source_dir)

    _record_source_reference(case_dir, "zip", str(src))
    return PhaseStatus(status="ok", phase="load", reason=None)


def load_repo(case_id: str, repo_url: str) -> PhaseStatus:
    try:
        case_dir = case_manager.resolve_case_id(case_id)
    except case_manager.CaseNotFoundError as exc:
        return PhaseStatus(status="failed", phase="load", reason=str(exc))

    source_dir = case_dir / "source"
    _clear_source_dir(source_dir)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(source_dir)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return PhaseStatus(
            status="failed",
            phase="load",
            reason=f"git clone failed: {result.stderr.strip()}",
        )

    _record_source_reference(case_dir, "repo", repo_url)
    return PhaseStatus(status="ok", phase="load", reason=None)
