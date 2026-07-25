#!/usr/bin/env python3
"""Rebuild the SCIP index over Atlas's TypeScript + Python services.

One shard per project - scip-typescript walks from a tsconfig.json and emits
`index.scip`; scip-python walks from a project dir and emits the same. We
rename each output to <service>.scip and land them in INDEX_DIR so the MCP
wrapper (sourcegraph_mcp.py) can query them by service.

Mirror of C:\\Users\\bruke\\zoekt-win\\reindex.py structurally - same 3-layer
failsafe (this script's --if-stale gate is Layer 1; L2 is the governance-daemon
cron; L3 is a Windows scheduled task). See project_zoekt_windows_native memory.

Usage:
    python reindex.py                         # all projects, both langs
    python reindex.py --if-stale              # skip if newest shard <24h old
    python reindex.py --lang ts               # only TypeScript projects
    python reindex.py --lang py               # only Python projects
    python reindex.py --project delta-kernel  # only projects matching arg

Env:
    SOURCEGRAPH_SCIP_INDEX_DIR - where .scip shards land
    SOURCEGRAPH_SCIP_STALE_HOURS - --if-stale freshness threshold (default 24)
    SCIP_BIN, SCIP_TS_BIN, SCIP_PYTHON_BIN - tool paths (auto-detected)
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\bruke\Pre Atlas")
INDEX_DIR = Path(os.environ.get(
    "SOURCEGRAPH_SCIP_INDEX_DIR",
    r"C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\index",
))
STALE_HOURS = float(os.environ.get("SOURCEGRAPH_SCIP_STALE_HOURS", "24"))

# Tool paths - default to the standard install locations, allow env override.
SCIP_BIN = os.environ.get("SCIP_BIN", r"C:\Users\bruke\go\bin\scip.exe")
SCIP_TS_BIN = os.environ.get("SCIP_TS_BIN") or shutil.which("scip-typescript") or "scip-typescript"
SCIP_PY_BIN = os.environ.get("SCIP_PYTHON_BIN") or shutil.which("scip-python") or "scip-python"

# TypeScript projects: (project_name, path_to_dir_containing_tsconfig.json).
# Only top-level project tsconfigs - subproject tsconfigs (like delta-kernel/web,
# aegis-fabric/sdk) get picked up implicitly by references or land in the parent
# shard. Skip _retired.
TS_PROJECTS = [
    ("aegis-fabric",  REPO_ROOT / "services" / "aegis-fabric"),
    ("canvas-engine", REPO_ROOT / "services" / "canvas-engine"),
    ("delta-kernel",  REPO_ROOT / "services" / "delta-kernel"),
    ("delta-scp",     REPO_ROOT / "services" / "delta-scp"),
    ("ws-gateway",    REPO_ROOT / "services" / "ws-gateway"),
]

# Python projects: (project_name, path_to_dir_containing_pyproject.toml).
PY_PROJECTS = [
    ("atlas-map-api",     REPO_ROOT / "services" / "atlas-map-api"),
    ("cognitive-sensor",  REPO_ROOT / "services" / "cognitive-sensor"),
    ("cortex",            REPO_ROOT / "services" / "cortex"),
    ("droplist",          REPO_ROOT / "services" / "droplist"),
    ("memory-hub",        REPO_ROOT / "services" / "memory-hub"),
    ("openclaw",          REPO_ROOT / "services" / "openclaw"),
    ("optogon",           REPO_ROOT / "services" / "optogon"),
    ("perception",        REPO_ROOT / "services" / "perception"),
    ("search-stack",      REPO_ROOT / "services" / "search-stack"),
    ("triangulation",     REPO_ROOT / "services" / "triangulation"),
]


def newest_shard_age_hours() -> float | None:
    shards = list(INDEX_DIR.glob("*.scip"))
    if not shards:
        return None
    newest = max(s.stat().st_mtime for s in shards)
    return (time.time() - newest) / 3600.0


def index_is_fresh() -> bool:
    age = newest_shard_age_hours()
    return age is not None and age < STALE_HOURS


def _shard_to_sqlite(name: str, shard: Path) -> None:
    """Also produce <name>.db via `scip expt-convert` so the MCP wrapper can
    query with plain SQL instead of decoding protobuf per call. The convert
    output is fixed to `index.db` in CWD (positional arg only, no --output that
    accepts an absolute path reliably), so we run it in INDEX_DIR and rename."""
    db_dest = INDEX_DIR / f"{name}.db"
    if db_dest.exists():
        db_dest.unlink()
    # Run inside INDEX_DIR so `index.db` lands here, then rename.
    p = subprocess.run(
        [SCIP_BIN, "expt-convert", shard.name],
        cwd=str(INDEX_DIR), capture_output=True, text=True,
    )
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-400:])
        print(f"  WARN expt-convert rc={p.returncode} for {name} (MCP will fall back)")
        return
    tmp = INDEX_DIR / "index.db"
    if tmp.exists():
        tmp.rename(db_dest)


def index_ts(name: str, project_dir: Path) -> bool:
    if not (project_dir / "tsconfig.json").is_file():
        print(f"  SKIP {name}: no tsconfig.json in {project_dir}")
        return False
    print(f"=== scip-typescript: {name} ===")
    # scip-typescript writes index.scip in CWD; --output overrides destination.
    dest = INDEX_DIR / f"{name}.scip"
    p = subprocess.run(
        [SCIP_TS_BIN, "index", "--output", str(dest)],
        cwd=str(project_dir), capture_output=True, text=True,
    )
    sys.stdout.write(p.stdout[-600:])
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-600:])
        print(f"  [FAILED rc={p.returncode}]")
        return False
    size_kb = dest.stat().st_size // 1024 if dest.exists() else 0
    print(f"  wrote {dest.name} ({size_kb} KB)")
    _shard_to_sqlite(name, dest)
    return True


def index_py(name: str, project_dir: Path) -> bool:
    if not (project_dir / "pyproject.toml").is_file():
        print(f"  SKIP {name}: no pyproject.toml in {project_dir}")
        return False
    print(f"=== scip-python: {name} ===")
    dest = INDEX_DIR / f"{name}.scip"
    # scip-python signature: `scip-python index --project-name X --output PATH .`
    p = subprocess.run(
        [SCIP_PY_BIN, "index", "--project-name", name, "--output", str(dest), "."],
        cwd=str(project_dir), capture_output=True, text=True,
    )
    sys.stdout.write(p.stdout[-600:])
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-600:])
        print(f"  [FAILED rc={p.returncode}]")
        return False
    size_kb = dest.stat().st_size // 1024 if dest.exists() else 0
    print(f"  wrote {dest.name} ({size_kb} KB)")
    _shard_to_sqlite(name, dest)
    return True


def main() -> int:
    if_stale = "--if-stale" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--if-stale"]

    lang_filter = None
    project_filter = None
    i = 0
    while i < len(args):
        if args[i] == "--lang" and i + 1 < len(args):
            lang_filter = args[i + 1]
            i += 2
        elif args[i] == "--project" and i + 1 < len(args):
            project_filter = args[i + 1]
            i += 2
        else:
            i += 1

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if if_stale and index_is_fresh():
        age = newest_shard_age_hours()
        print(f"index fresh ({age:.1f}h < {STALE_HOURS}h) - skipping reindex")
        return 0

    ts_projects = [p for p in TS_PROJECTS
                   if (project_filter is None or project_filter.lower() in p[0].lower())]
    py_projects = [p for p in PY_PROJECTS
                   if (project_filter is None or project_filter.lower() in p[0].lower())]

    if lang_filter == "ts":
        py_projects = []
    elif lang_filter == "py":
        ts_projects = []

    print(f"scip:   {SCIP_BIN}")
    print(f"ts:     {SCIP_TS_BIN}  ({len(ts_projects)} project(s))")
    print(f"python: {SCIP_PY_BIN}  ({len(py_projects)} project(s))")
    print(f"index:  {INDEX_DIR}")
    print()

    ok, fail = 0, 0
    for name, path in ts_projects:
        if index_ts(name, path):
            ok += 1
        else:
            fail += 1
    for name, path in py_projects:
        if index_py(name, path):
            ok += 1
        else:
            fail += 1

    shards = list(INDEX_DIR.glob("*.scip"))
    total_mb = sum(s.stat().st_size for s in shards) // (1024 * 1024)
    print(f"\nDone: {ok} shard(s) built, {fail} skipped/failed. "
          f"{len(shards)} total shard(s), {total_mb} MB in {INDEX_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
