"""Filesystem scan via Everything CLI (es.exe).

Surfaces disk-level open loops that the conversation pipeline can't see:
stalled project directories, leaked .env files, and oversized cleanup
targets. Writes cycleboard/brain/machine_scan.json as the authoritative
record and merges entries into loops_latest.json so CycleBoard surfaces
them alongside conversational loops.

Run as Phase 1.5 of run_daily.py — after loops.py, before wire_cycleboard.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from atlas_config import ROUTING
from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN = BASE / "cycleboard" / "brain"
ES_BIN = Path(r"C:\Program Files\Everything\es.exe")
MIN_LOOP_SCORE = ROUTING["min_loop_score"]

SCAN_ROOT = r"C:\Users\bruke"
NOISE_EXCLUDES = (
    "!node_modules",
    "!.git\\",
    "!_archive",
    "!_deferred",
    "!AppData",
    "!.venv",
    "!dist\\",
    "!.next\\",
    "!\\extensions\\",
    "!anaconda3\\pkgs",
    "!anaconda3\\Lib",
    "!site-packages",
    "!\\pkgs\\",
)


@dataclass(frozen=True)
class FsLoop:
    loop_id: str
    title: str
    score: int
    source: str
    severity: str
    evidence: str
    age_days: int | None = None


def _run_es(query: list[str], limit: int = 50) -> list[str]:
    """Invoke es.exe and return newline-split paths."""
    if not ES_BIN.exists():
        logger.warning("es.exe not found at %s — skipping scan", ES_BIN)
        return []
    cmd = [str(ES_BIN), "-p", "-n", str(limit), *query]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        logger.warning("es query timed out: %s", query)
        return []
    if proc.returncode != 0:
        logger.warning("es returned %s: %s", proc.returncode, proc.stderr.strip())
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _path_age_days(path: Path) -> int | None:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (datetime.now(timezone.utc) - mtime).days
    except OSError:
        return None


def scan_leaked_env() -> list[FsLoop]:
    """Find .env files outside node_modules and common ignores."""
    query = [
        f"path:{SCAN_ROOT}",
        "ext:env",
        "!.env.example",
        "!.env.template",
        *NOISE_EXCLUDES,
    ]
    hits = _run_es(query, limit=30)
    return [
        FsLoop(
            loop_id=f"fs-env-{abs(hash(p))}",
            title=f"Leaked .env: {Path(p).parent.name}/{Path(p).name}",
            score=30000,
            source="fs",
            severity="high",
            evidence=p,
            age_days=_path_age_days(Path(p)),
        )
        for p in hits
    ]


def scan_stalled_projects() -> list[FsLoop]:
    """Project roots (package.json / pyproject.toml) untouched >30d."""
    manifests = ["package.json", "pyproject.toml"]
    found: dict[str, FsLoop] = {}
    for manifest in manifests:
        query = [
            f"path:{SCAN_ROOT}",
            manifest,
            "dm:<=lastmonth",
            *NOISE_EXCLUDES,
        ]
        for p in _run_es(query, limit=40):
            project_dir = Path(p).parent
            key = str(project_dir).lower()
            if key in found:
                continue
            age = _path_age_days(Path(p))
            if age is None or age < 30:
                continue
            found[key] = FsLoop(
                loop_id=f"fs-stalled-{abs(hash(key))}",
                title=f"Stalled project: {project_dir.name} ({age}d)",
                score=20000,
                source="fs",
                severity="medium",
                evidence=str(project_dir),
                age_days=age,
            )
    return list(found.values())


def scan_large_artifacts() -> list[FsLoop]:
    """Files >100MB that look like cleanup candidates."""
    query = [
        f"path:{SCAN_ROOT}",
        "size:>100mb",
        *NOISE_EXCLUDES,
        "!.iso",
        "!.vhdx",
    ]
    hits = _run_es(query, limit=20)
    return [
        FsLoop(
            loop_id=f"fs-large-{abs(hash(p))}",
            title=f"Large artifact: {Path(p).name}",
            score=19000,
            source="fs",
            severity="low",
            evidence=p,
            age_days=_path_age_days(Path(p)),
        )
        for p in hits
    ]


def _merge_into_loops(fs_loops: Iterable[FsLoop]) -> int:
    """Append fs loops into loops_latest.json (dedup by loop_id)."""
    loops_path = BASE / "loops_latest.json"
    existing: list[dict] = []
    if loops_path.exists():
        try:
            existing = json.loads(loops_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    seen = {
        entry.get("convo_id") or entry.get("loop_id")
        for entry in existing
        if isinstance(entry, dict)
    }
    added = 0
    for loop in fs_loops:
        if loop.loop_id in seen:
            continue
        existing.append(
            {
                "convo_id": loop.loop_id,
                "loop_id": loop.loop_id,
                "title": loop.title,
                "score": loop.score,
                "source": loop.source,
                "severity": loop.severity,
                "evidence": loop.evidence,
                "age_days": loop.age_days,
            }
        )
        added += 1
    atomic_write_json(loops_path, existing)
    return added


def main() -> int:
    if not ES_BIN.exists():
        print(f"  [SKIP] Everything CLI not installed at {ES_BIN}")
        return 0

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scans = {
        "leaked_env": scan_leaked_env(),
        "stalled_projects": scan_stalled_projects(),
        "large_artifacts": scan_large_artifacts(),
    }
    all_loops = [loop for bucket in scans.values() for loop in bucket]
    filtered = [loop for loop in all_loops if loop.score >= MIN_LOOP_SCORE]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_root": SCAN_ROOT,
        "counts": {name: len(items) for name, items in scans.items()},
        "items": [asdict(loop) for loop in filtered],
    }
    BRAIN.mkdir(parents=True, exist_ok=True)
    atomic_write_json(BRAIN / "machine_scan.json", payload)

    added = _merge_into_loops(filtered)

    print("\n=== MACHINE SCAN (es) ===")
    for name, items in scans.items():
        print(f"  {name:<20} {len(items):>3} found")
    print(f"  merged into loops_latest.json: +{added}")
    print(f"  wrote cycleboard/brain/machine_scan.json ({len(filtered)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
