#!/usr/bin/env python3
"""Portfolio-wide ship-evidence audit across 4 surfaces.

Inventory + signal-strength audit for the full work corpus, not just fest:
  1. Standalone repos in C:/Users/bruke/* (git/weapon/build markers)
  2. GitHub repos under lionestenzol (via gh)
  3. Custom skills in ~/.claude/skills/
  4. Pre Atlas internals: services/, apps/, tools/

Per-item signal:
  - "strong" : recent activity + size + memory mention OR explicit weapon ship
  - "partial": some evidence (git history, README, source files) but missing key factors
  - "stale"  : has content but no activity for >1 year
  - "none"   : empty/stub, no evidence

Output: portfolio_evidence.json with full per-item evidence + summary counts.
Heuristic only — surfaces what needs manual review, doesn't auto-classify into
"shipped/not-shipped." HOTL pattern.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
USER_DIR = Path("C:/Users/bruke")
PRE_ATLAS = USER_DIR / "Pre Atlas"
SKILLS_DIR = HOME / ".claude" / "skills"
MEMORY_INDEX = HOME / ".claude" / "projects" / "C--Users-bruke-Pre-Atlas" / "memory" / "MEMORY.md"
OUTPUT_PATH = Path(__file__).parent / "portfolio_evidence.json"

NOW = datetime.now(timezone.utc)
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", ".venv", "venv", ".next", "target", "build"}


def _load_memory_text() -> str:
    if MEMORY_INDEX.exists():
        return MEMORY_INDEX.read_text(encoding="utf-8", errors="ignore").lower()
    return ""


MEMORY_TEXT = _load_memory_text()


def memory_mentions(name: str) -> bool:
    return name.lower() in MEMORY_TEXT


def days_since(path: Path) -> int | None:
    try:
        ts = path.stat().st_mtime
        return (NOW - datetime.fromtimestamp(ts, tz=timezone.utc)).days
    except OSError:
        return None


def shallow_file_count(path: Path, max_depth: int = 3, cap: int = 500) -> int:
    """Count files up to max_depth, excluding noise dirs. Early-exit at cap."""
    if not path.exists() or not path.is_dir():
        return 0
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        depth = len(Path(root).relative_to(path).parts)
        if depth > max_depth:
            dirs[:] = []
            continue
        count += len(files)
        if count > cap:
            return count
    return count


def signal_band(
    file_count: int, days_old: int | None, has_weapon: bool, mem: bool, has_git: bool
) -> str:
    if file_count == 0:
        return "none"
    if has_weapon and file_count >= 3:
        return "strong"
    if days_old is not None and days_old > 365 and file_count < 10:
        return "stale"
    if mem and file_count >= 5:
        return "strong"
    if file_count >= 20 and has_git:
        return "strong" if (days_old is None or days_old < 180) else "stale"
    if file_count >= 5:
        return "partial"
    return "none"


def inventory_standalone_repos() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not USER_DIR.exists():
        return items
    for child in sorted(USER_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        markers = {
            "git": (child / ".git").exists(),
            "weapon": (child / ".weapon").exists(),
            "npm": (child / "package.json").exists(),
            "py": (child / "pyproject.toml").exists(),
            "rs": (child / "Cargo.toml").exists(),
            "readme": any((child / n).exists() for n in ("README.md", "README.rst", "README")),
        }
        if not any(markers.values()):
            continue
        fc = shallow_file_count(child)
        days = days_since(child)
        mem = memory_mentions(child.name)
        band = signal_band(fc, days, markers["weapon"], mem, markers["git"])
        items.append({
            "surface": "standalone_repo",
            "name": child.name,
            "path": str(child),
            "markers": [k for k, v in markers.items() if v],
            "file_count": fc,
            "days_since_modified": days,
            "memory_mention": mem,
            "signal_band": band,
        })
    return items


def inventory_github_repos() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "lionestenzol", "--limit", "100",
             "--json", "name,updatedAt,isPrivate,description,pushedAt"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0 or not result.stdout:
            return items
        repos = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return items
    for r in repos:
        updated = r.get("updatedAt", "")
        days: int | None = None
        if updated:
            try:
                days = (NOW - datetime.fromisoformat(updated.replace("Z", "+00:00"))).days
            except ValueError:
                pass
        mem = memory_mentions(r["name"])
        if days is not None and days < 90 and mem:
            band = "strong"
        elif days is not None and days < 180:
            band = "partial" if mem else "partial"
        elif days is not None and days > 365:
            band = "stale"
        else:
            band = "partial" if mem else "none"
        items.append({
            "surface": "github_repo",
            "name": r["name"],
            "private": r.get("isPrivate", False),
            "description": (r.get("description") or "")[:80],
            "days_since_updated": days,
            "memory_mention": mem,
            "signal_band": band,
        })
    return items


def inventory_custom_skills() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not SKILLS_DIR.exists():
        return items
    for child in sorted(SKILLS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        fc = shallow_file_count(child, max_depth=2)
        days = days_since(child)
        mem = memory_mentions(child.name)
        if skill_md.exists() and fc >= 3 and (mem or (days is not None and days < 180)):
            band = "strong"
        elif skill_md.exists() and fc >= 2:
            band = "partial"
        elif fc >= 1:
            band = "stale"
        else:
            band = "none"
        items.append({
            "surface": "custom_skill",
            "name": child.name,
            "path": str(child),
            "has_skill_md": skill_md.exists(),
            "file_count": fc,
            "days_since_modified": days,
            "memory_mention": mem,
            "signal_band": band,
        })
    return items


def inventory_pre_atlas() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kind in ("services", "apps", "tools"):
        parent = PRE_ATLAS / kind
        if not parent.exists():
            continue
        for child in sorted(parent.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            fc = shallow_file_count(child)
            days = days_since(child)
            mem = memory_mentions(child.name)
            has_pkg = (child / "package.json").exists() or (child / "pyproject.toml").exists()
            band = signal_band(fc, days, has_weapon=False, mem=mem, has_git=True)
            items.append({
                "surface": f"pre_atlas_{kind}",
                "name": child.name,
                "path": str(child.relative_to(PRE_ATLAS)),
                "file_count": fc,
                "days_since_modified": days,
                "memory_mention": mem,
                "has_package_manifest": has_pkg,
                "signal_band": band,
            })
    return items


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_band = Counter(i["signal_band"] for i in items)
    by_surface = Counter(i["surface"] for i in items)
    by_surface_band = Counter((i["surface"], i["signal_band"]) for i in items)
    surface_band_table: dict[str, dict[str, int]] = {}
    for (surface, band), n in by_surface_band.items():
        surface_band_table.setdefault(surface, {})[band] = n
    return {
        "total_items": len(items),
        "by_signal_band": dict(by_band),
        "by_surface": dict(by_surface),
        "by_surface_and_band": surface_band_table,
    }


def main() -> int:
    print("PORTFOLIO AUDIT - corpus-wide ship-evidence scan\n")
    all_items: list[dict[str, Any]] = []
    for label, fn in [
        ("standalone repos", inventory_standalone_repos),
        ("github repos", inventory_github_repos),
        ("custom skills", inventory_custom_skills),
        ("Pre Atlas internals", inventory_pre_atlas),
    ]:
        items = fn()
        print(f"  {label:<22} {len(items):>4} items")
        all_items.extend(items)

    summary = summarize(all_items)
    print(f"\n  TOTAL: {summary['total_items']} items")
    print(f"  By band: {summary['by_signal_band']}")

    print("\n  Surface x Band:")
    for surface, bands in summary["by_surface_and_band"].items():
        bands_fmt = ", ".join(f"{b}={n}" for b, n in sorted(bands.items()))
        print(f"    {surface:<22} {bands_fmt}")

    by_band: dict[str, list[dict[str, Any]]] = {}
    for item in all_items:
        by_band.setdefault(item["signal_band"], []).append(item)
    for band in ("strong", "partial", "stale", "none"):
        items = by_band.get(band, [])
        if not items:
            continue
        print(f"\n  --- {band.upper()} ({len(items)}) ---")
        for it in items[:20]:
            mem_tag = " [mem]" if it.get("memory_mention") else ""
            print(f"    {it['surface']:<22} {it['name']}{mem_tag}")
        if len(items) > 20:
            print(f"    ... +{len(items) - 20} more")

    OUTPUT_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "items": all_items,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
