#!/usr/bin/env python3
"""Reconcile fest-declared progress against disk + git + memory evidence.

Runs `fest list` (via WSL) to enumerate festivals, then for each derives a
search keyword from the festival id and counts:
  - disk hits via Everything CLI (es.exe), excluding noise dirs
  - git commits in Pre Atlas mentioning the keyword since SINCE
  - whether MEMORY.md mentions the keyword

Outputs festival_evidence.json with a heuristic evidence_strength (0..1) and
suggested action per festival. Heuristic only — not authoritative; the goal is
to surface UNDERMARKED festivals where shipped work isn't reflected in fest %.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_INDEX = Path.home() / ".claude" / "projects" / "C--Users-bruke-Pre-Atlas" / "memory" / "MEMORY.md"
OUTPUT_PATH = Path(__file__).parent / "festival_evidence.json"
SINCE = "2026-03-01"
ES_EXCLUDES = ["!node_modules", "!worktrees", "!__pycache__", "!.git", "!dist"]

# Manual overrides: festivals whose on-disk project name diverged from the fest id.
# When fest gets revised so id ≈ project, drop these.
KEYWORD_OVERRIDES: dict[str, str] = {
    "mb3d-2026-MB0001": "mb3d-blender",
    "inpact-ship-2026-04-15-IS0001": "inpact",
    "canvas-90-day-CD0001": "canvas-engine",
    "claude-festival-skill-CF0001": "fest-skill",
    "agent-cookbook-AC0001": "cookbook",
    "td-claude-protocols-TC0001": "touchdesigner",
}


def festival_keywords(fest_id: str) -> tuple[str | None, str]:
    """Return (id_suffix, keyword).
    id_suffix is the gold signal (e.g. 'MB0001', unambiguous in commit messages).
    keyword is the 2-token form (e.g. 'canvas-engine'); falls back to full name.
    Single-token fallback DELIBERATELY OMITTED — 'atlas'/'claude'/'strudel' alone
    over-match noise, swamping the actual signal.
    """
    parts = fest_id.rsplit("-", 1)
    id_suffix = parts[1] if len(parts) == 2 and re.match(r"^[A-Z]+\d+$", parts[1]) else None
    name = parts[0] if id_suffix else fest_id
    tokens = [t for t in name.split("-") if not t.isdigit() and len(t) > 1]
    keyword = "-".join(tokens[:2]) if len(tokens) >= 2 else name
    return id_suffix, keyword


def list_festivals() -> list[dict]:
    """Run `fest list` in WSL, parse lifecycle + (id, pct)."""
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", "cd ~/festival-project && fest list"],
        capture_output=True, text=True, timeout=30,
    )
    festivals: list[dict] = []
    lifecycle = None
    for line in result.stdout.splitlines():
        line = line.strip()
        m = re.match(r"^(ACTIVE|READY|PLANNING|DONE)\s+Festivals", line)
        if m:
            lifecycle = m.group(1)
            continue
        m = re.match(r"^([\w\-]+)\s+\[(\d+)%\]", line)
        if m and lifecycle:
            festivals.append({"id": m.group(1), "lifecycle": lifecycle, "fest_pct": int(m.group(2))})
    return festivals


def disk_count(keyword: str) -> int:
    try:
        result = subprocess.run(
            ["es", keyword, "-p", "-n", "200", *ES_EXCLUDES],
            capture_output=True, text=True, timeout=10,
        )
        return sum(1 for l in result.stdout.splitlines() if l.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        return 0


def git_count(keyword: str) -> int:
    try:
        result = subprocess.run(
            ["git", "log", f"--since={SINCE}", f"--grep={keyword}", "-i", "--oneline"],
            capture_output=True, text=True, timeout=10, cwd=REPO_ROOT,
        )
        return sum(1 for l in result.stdout.splitlines() if l.strip())
    except subprocess.SubprocessError:
        return 0


def memory_hits(keyword: str, fest_id: str, id_suffix: str | None) -> bool:
    if not MEMORY_INDEX.exists():
        return False
    text = MEMORY_INDEX.read_text(encoding="utf-8", errors="ignore").lower()
    if keyword.lower() in text or fest_id.lower() in text:
        return True
    return bool(id_suffix and id_suffix.lower() in text)


def evidence_strength(disk: int, git_kw: int, git_id: int, memory: bool) -> float:
    # git_id matches are the gold signal — fest suffix in commit message is unambiguous.
    return min(1.0, disk * 0.01 + git_kw * 0.05 + git_id * 0.3 + (0.4 if memory else 0.0))


def suggest_action(fest_pct: int, git_id: int, disk: int, git_kw: int, mem: bool) -> str:
    if fest_pct >= 80:
        return "FEST AGREES (marked complete)"
    # gold signal: commit explicitly cites the festival id
    if git_id >= 3:
        return "FEST UNDERMARKED — multiple commits cite this fest; mark catch-up"
    if git_id >= 1:
        return "FEST UNDERMARKED — at least 1 commit cites this fest"
    # memory entry + non-trivial keyword evidence
    if mem and (disk >= 10 or git_kw >= 2):
        return "FEST UNDERMARKED — memory + keyword evidence, no fest-id in commits"
    if mem and (disk >= 3 or git_kw >= 1):
        return "PARTIAL DRIFT — memory mentions this; some keyword evidence"
    if disk >= 20 or git_kw >= 3:
        return "AMBIGUOUS — disk/git evidence but no memory; may be keyword collision"
    if disk == 0 and git_kw == 0 and not mem:
        return "LIKELY TRULY STALLED — zero evidence anywhere"
    return "WEAK SIGNAL — manual review"


def main() -> int:
    festivals = list_festivals()
    print(f"Found {len(festivals)} festivals\n")
    print(f"{'festival':<42} {'fest':>5}  {'disk':>4}  gitKW  gitID  mem  str   action")
    print("-" * 120)
    results: list[dict] = []
    for f in festivals:
        id_suffix, auto_kw = festival_keywords(f["id"])
        kw = KEYWORD_OVERRIDES.get(f["id"], auto_kw)
        kw_source = "override" if f["id"] in KEYWORD_OVERRIDES else "auto"
        d = disk_count(kw)
        g_kw = git_count(kw)
        g_id = git_count(id_suffix) if id_suffix else 0
        m = memory_hits(kw, f["id"], id_suffix)
        s = evidence_strength(d, g_kw, g_id, m)
        action = suggest_action(f["fest_pct"], g_id, d, g_kw, m)
        f.update({
            "id_suffix": id_suffix, "keyword_used": kw, "keyword_source": kw_source,
            "disk_count": d, "git_keyword_count": g_kw, "git_id_count": g_id,
            "memory_hit": m, "evidence_strength": round(s, 2),
            "suggested_action": action,
        })
        results.append(f)
        tag = "*" if kw_source == "override" else " "
        print(f" {tag}{f['id']:<38} kw={kw:<20} {f['fest_pct']:>3}%  disk={d:>3} gKW={g_kw:>2} gID={g_id:>2} mem={'Y' if m else 'N'}  {action}")
    print("\n  * = keyword override applied (auto-extracted keyword would have missed)")

    OUTPUT_PATH.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(), "festivals": results}, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
