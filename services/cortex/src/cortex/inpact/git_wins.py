"""Git-as-Wins — auto-logs commits as MomentumWins in inPACT.

Removes the friction of manually typing `inpact win <text>` for work that is
already recorded in git history. Polls the local git log for new commits since
the last recorded win hash and appends them.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cortex.config import config
from cortex.inpact.client import InpactClient

log = logging.getLogger("cortex.inpact.git_wins")


async def _run_git(repo: Path, *args: str) -> str:
    """Run a git command and return stdout, or empty on failure."""
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(repo), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning("git %s failed: %s", " ".join(args), stderr.decode(errors="replace"))
        return ""
    return stdout.decode(errors="replace")


async def get_recent_commits(repo: Path, since_hash: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent commits as [{sha, subject, author, timestamp}]."""
    fmt = "%H\x1f%s\x1f%an\x1f%aI"
    if since_hash:
        # Everything after since_hash up to HEAD
        args = ["log", f"{since_hash}..HEAD", f"--pretty=format:{fmt}", f"-{limit}"]
    else:
        args = ["log", f"--pretty=format:{fmt}", f"-{limit}"]

    out = await _run_git(repo, *args)
    commits: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, subject, author, iso_ts = parts
        commits.append({"sha": sha, "subject": subject, "author": author, "timestamp": iso_ts})
    return commits


def _generate_id() -> str:
    return secrets.token_urlsafe(6)


async def log_commits_as_wins(inpact: InpactClient, repo: Path | None = None) -> dict[str, Any]:
    """Append any new commits since last_git_sha to MomentumWins."""
    repo = repo or Path(config.GIT_WINS_REPO_PATH)
    if not repo.exists() or not (repo / ".git").exists():
        return {"ok": False, "error": f"No git repo at {repo}"}

    state = await inpact.get_state()
    meta = state.get("_GitWinsMeta") or {}
    last_sha = meta.get("last_sha")

    commits = await get_recent_commits(repo, since_hash=last_sha)
    if not commits:
        return {"ok": True, "added": 0}

    wins = list(state.get("MomentumWins") or [])
    now_iso = datetime.now(timezone.utc).isoformat()
    # Walk oldest -> newest so they appear chronologically in MomentumWins
    for commit in reversed(commits):
        subject = commit["subject"]
        # Skip merge commits and noisy automation (heuristic)
        if subject.startswith(("Merge ", "chore(deps)", "bot:")):
            continue
        wins.append({
            "id": _generate_id(),
            "date": commit["timestamp"][:10],
            "timestamp": commit["timestamp"],
            "source": "git",
            "sha": commit["sha"][:12],
            "description": subject,
            "auto": True,
        })

    # Mark newest sha so we don't reimport
    newest_sha = commits[0]["sha"]
    await inpact.merge_state({
        "MomentumWins": wins,
        "_GitWinsMeta": {"last_sha": newest_sha, "last_checked": now_iso},
    })
    log.info("Git Wins: added %d commits (newest=%s)", len(commits), newest_sha[:8])
    return {"ok": True, "added": len(commits), "newest_sha": newest_sha}
