"""Pre Atlas system-shape indexer.

Walks services/, apps/, and tools/ and emits audit/system-index.json.
Cross-references scripts/start_atlas.ps1 for port + autostart info.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(r"C:\Users\bruke\Pre Atlas")
OUT_PATH = REPO_ROOT / "audit" / "system-index.json"
START_SCRIPT = REPO_ROOT / "scripts" / "start_atlas.ps1"

ROOTS = ["services", "apps", "tools"]
EXCLUDE_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build",
    ".git", ".next", "target", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "coverage", ".turbo",
}
SOURCE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".html", ".css", ".scss", ".json", ".vue",
    ".rs", ".go", ".java", ".cs",
}

ENTRY_CANDIDATES = [
    "src/api/server.ts", "src/server.ts", "server.ts", "src/index.ts", "index.ts",
    "src/main.ts", "main.ts",
    "server.mjs", "server.js", "index.js", "src/index.js",
    "server.py", "main.py", "app.py", "run.py", "serve.py", "__main__.py",
    "src/server.py", "src/main.py", "src/app.py",
    "index.html", "onboarding.html", "atlas_template.html",
    "manifest.json",
]


def parse_start_script() -> dict[str, dict[str, Any]]:
    """Return {name: {port, cwd_rel}} for services in start_atlas.ps1."""
    out: dict[str, dict[str, Any]] = {}
    if not START_SCRIPT.exists():
        return out
    text = START_SCRIPT.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(
        r'@\{\s*Name\s*=\s*"([^"]+)";\s*Port\s*=\s*(\d+);\s*Cwd\s*=\s*"([^"]+)"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        name, port, cwd = match.group(1), int(match.group(2)), match.group(3)
        cwd_norm = cwd.replace("$RepoRoot\\", "").replace("$RepoRoot/", "")
        out[name.lower()] = {"port": port, "cwd_rel": cwd_norm}
    return out


def detect_language(node_files: list[str], py_files: list[str], html_files: list[str]) -> str:
    has_ts = any(f.endswith((".ts", ".tsx")) for f in node_files)
    has_js = any(f.endswith((".js", ".jsx", ".mjs", ".cjs")) for f in node_files)
    has_py = len(py_files) > 0
    has_html = len(html_files) > 0
    if has_ts and has_py:
        return "mixed"
    if has_ts:
        return "ts"
    if has_py:
        return "py"
    if has_js:
        return "js"
    if has_html and not (has_ts or has_js or has_py):
        return "html"
    return "unknown"


def detect_framework(deps: list[str], language: str, files_seen: set[str]) -> str:
    dl = {d.lower() for d in deps}
    if "express" in dl:
        return "express"
    if "next" in dl or any(d.startswith("next") for d in dl):
        return "next"
    if "fastapi" in dl:
        return "fastapi"
    if "flask" in dl:
        return "flask"
    if "uvicorn" in dl and language == "py":
        return "fastapi"
    if "react" in dl and "next" not in dl:
        return "react"
    if "vue" in dl:
        return "vue"
    # Vanilla HTML/JS app
    if "index.html" in files_seen and not deps:
        return "vanilla"
    if language == "html":
        return "vanilla"
    return "unknown"


def read_package_json(p: Path) -> list[str]:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    out: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        d = data.get(key)
        if isinstance(d, dict):
            out.update(d.keys())
    return sorted(out)


def read_requirements_txt(p: Path) -> list[str]:
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    deps: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        if m:
            deps.append(m.group(1))
    return deps


def read_pyproject(p: Path) -> list[str]:
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    deps: list[str] = []
    # Naive scan: look for dependencies = [...] block
    m = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if m:
        block = m.group(1)
        for line in block.splitlines():
            line = line.strip().strip(",").strip('"').strip("'")
            if not line:
                continue
            name = re.match(r"^([A-Za-z0-9_.\-]+)", line)
            if name:
                deps.append(name.group(1))
    return deps


def walk_subsystem(subsystem_dir: Path) -> dict[str, Any]:
    deps: set[str] = set()
    file_count = 0
    total_loc = 0
    files_seen: set[str] = set()
    node_files: list[str] = []
    py_files: list[str] = []
    html_files: list[str] = []
    entry_points: list[str] = []

    # Check for entry points at known relative paths
    for cand in ENTRY_CANDIDATES:
        if (subsystem_dir / cand).is_file():
            entry_points.append(cand.replace("\\", "/"))

    # Walk for deps + source counting
    for root, dirs, files in os.walk(subsystem_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        rel_root = Path(root).relative_to(subsystem_dir)
        for f in files:
            fp = Path(root) / f
            rel = (rel_root / f).as_posix()
            files_seen.add(f)

            # Manifest files (only at top level)
            if rel_root == Path("."):
                if f == "package.json":
                    deps.update(read_package_json(fp))
                elif f == "requirements.txt":
                    deps.update(read_requirements_txt(fp))
                elif f == "pyproject.toml":
                    deps.update(read_pyproject(fp))

            ext = fp.suffix.lower()
            if ext in SOURCE_EXT:
                file_count += 1
                if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                    node_files.append(f)
                elif ext == ".py":
                    py_files.append(f)
                elif ext == ".html":
                    html_files.append(f)
                # LOC count (cheap)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        total_loc += sum(1 for _ in fh)
                except Exception:
                    pass

    language = detect_language(node_files, py_files, html_files)
    framework = detect_framework(sorted(deps), language, files_seen)

    return {
        "deps": sorted(deps),
        "entry_points": entry_points,
        "file_count": file_count,
        "total_loc": total_loc,
        "language": language,
        "framework": framework,
    }


def main() -> None:
    start_map = parse_start_script()
    autostart_names = set(start_map.keys())

    # Also map by cwd_rel -> name for lookup
    cwd_to_name = {info["cwd_rel"].replace("\\", "/").lower(): name for name, info in start_map.items()}

    entries: list[dict[str, Any]] = []
    for root in ROOTS:
        root_path = REPO_ROOT / root
        if not root_path.exists():
            continue
        for entry in sorted(root_path.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name in EXCLUDE_DIRS:
                continue

            rel_path = f"{root}/{entry.name}"
            data = walk_subsystem(entry)

            # Port + autostart lookup
            name_lower = entry.name.lower()
            port: int | None = None
            in_autostart = False
            # Match either by name or by cwd
            rel_key = rel_path.lower()
            if name_lower in start_map:
                port = start_map[name_lower]["port"]
                in_autostart = True
            else:
                for ck, nm in cwd_to_name.items():
                    if ck.endswith(rel_key) or rel_key in ck:
                        port = start_map[nm]["port"]
                        in_autostart = True
                        break
            # Hand-mapped aliases (start_atlas uses short names)
            aliases = {
                "mosaic-orchestrator": "mosaic-orch",
                "uasc-executor": "uasc",
                "mosaic-dashboard": "mosaic-dashboard",
                "blueprint-generator": "blueprint-gen",
            }
            if not in_autostart and name_lower in aliases:
                alias = aliases[name_lower]
                if alias in start_map:
                    port = start_map[alias]["port"]
                    in_autostart = True

            entries.append({
                "path": rel_path,
                "name": entry.name,
                "language": data["language"],
                "framework": data["framework"],
                "deps": data["deps"],
                "entry_points": data["entry_points"],
                "file_count": data["file_count"],
                "total_loc": data["total_loc"],
                "port": port,
                "in_autostart": in_autostart,
            })

    output = {
        "generated_at": "2026-05-29",
        "repo_root": str(REPO_ROOT),
        "subsystem_count": len(entries),
        "autostart_count": sum(1 for e in entries if e["in_autostart"]),
        "entries": entries,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Subsystems: {len(entries)} | Autostart: {output['autostart_count']}")


if __name__ == "__main__":
    main()
