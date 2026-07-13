"""
Promptfoo provider driving supagetti's real analyze/govern phases against a
cached Express.js fixture.

This does not re-implement analyze/govern for eval purposes — it calls the
actual core.scanner/core.analyzer/core.governor phase functions (the same
code path core/llm.py and the CLI use), pointed at a private fixture case
dir under .fixture-cache/ so eval runs never touch the real cases/
directory. That keeps the eval honest: a pass here means the production
pipeline itself produced schema-valid, grounded output, not that some
parallel eval-only logic did.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
SUPAGETTI_ROOT = EVAL_DIR.parent
CACHE_DIR = EVAL_DIR / ".fixture-cache"
FIXTURE_REPO = "https://github.com/expressjs/express.git"
# Must match case_manager.CASE_ID_RE ("CASE_" + exactly 4 digits) — 9001 is
# well outside the real cases/ counter range so it can never collide.
CASE_ID = "CASE_9001"
CASE_NAME = f"{CASE_ID}_express_eval"

sys.path.insert(0, str(SUPAGETTI_ROOT))


def _ensure_fixture_clone() -> Path:
    """Clone Express once and cache it — repeated eval runs reuse the same
    checkout instead of re-cloning on every invocation."""
    repo_dir = CACHE_DIR / "express"
    if not (repo_dir / "package.json").exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        subprocess.run(
            ["git", "clone", "--depth", "1", FIXTURE_REPO, str(repo_dir)],
            check=True,
            capture_output=True,
        )
    return repo_dir


def _build_case(cases_dir: Path, source_dir: Path):
    from core import case_manager
    from core.models import Intake

    case_dir = cases_dir / CASE_NAME
    case_dir.mkdir(parents=True, exist_ok=True)
    dest_source = case_dir / "source"
    if not dest_source.exists():
        shutil.copytree(source_dir, dest_source, ignore=shutil.ignore_patterns(".git"))

    intake = Intake(
        case_id=CASE_ID,
        project_name="express_eval",
        source_type="folder",
        user_claim="A fast, unopinionated, minimalist web framework for Node.js",
        user_pain="Evaluating supagetti analyze/govern phases with promptfoo",
        desired_outcome="Confirm LLM-backed phases produce schema-valid, grounded output",
        audience="eval-harness",
        privacy_level="internal",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    case_manager.write_json(case_dir / "intake.json", intake.model_dump())
    return case_dir


def call_api(prompt, options, context):
    from core import analyzer, case_manager, governor, scanner

    phase = context["vars"]["phase"]
    if phase not in ("analyze", "govern"):
        return {"output": "", "error": f"unknown phase '{phase}' (expected analyze|govern)"}

    try:
        repo_dir = _ensure_fixture_clone()
    except subprocess.CalledProcessError as exc:
        return {"output": "", "error": f"fixture clone failed: {exc.stderr}"}

    cases_dir = CACHE_DIR / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    # Law 1 (case_manager.py) says case resolution lives only in
    # case_manager — redirecting its module-level CASES_DIR is the sanction-
    # ed way to point the real phase functions at an eval-private location
    # without touching cases/ or duplicating resolve_case_id().
    case_manager.CASES_DIR = cases_dir
    case_manager.COUNTER_FILE = cases_dir / ".counter"

    case_dir = _build_case(cases_dir, repo_dir)

    scan_path = case_dir / "scan.json"
    if not scan_path.exists():
        status = scanner.run_scan(CASE_ID)
        if status.status != "ok":
            return {"output": "", "error": f"scan failed: {status.reason}"}

    result: dict = {"phase": phase, "scan": case_manager.read_json(scan_path)}

    analyze_status = analyzer.run_analyze(CASE_ID)
    if analyze_status.status != "ok":
        return {"output": "", "error": f"analyze failed: {analyze_status.reason}"}
    result["findings"] = case_manager.read_json(case_dir / "findings.json")

    if phase == "govern":
        govern_status = governor.run_govern(CASE_ID)
        if govern_status.status != "ok":
            return {"output": "", "error": f"govern failed: {govern_status.reason}"}
        result["governor_report"] = case_manager.read_json(case_dir / "governor_report.json")

    return {"output": json.dumps(result)}
