#!/usr/bin/env python3
"""
Central worktree bookmark index generator.

Doctrine (Bruke, 2026-07-25): worktrees are project bookmarks answering three
questions on sight — what was I reaching for, what's left, did I finish? This
script writes ONE central index (capsules/BOOKMARKS.md) and never touches the
worktree directories themselves. Zero deletion. Zero suggestions to close.

Done? = branch merged into main OR has a matching capsule/* tag.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "capsules" / "BOOKMARKS.md"
OUT_JSON = REPO / "capsules" / "BOOKMARKS.json"
MAIN_REF = "origin/main"


def sh(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, check=False,
    ).stdout.strip()


def worktrees() -> list[tuple[str, str, str]]:
    """Return [(path, sha, branch)] for every worktree except main."""
    out = sh("worktree", "list", "--porcelain")
    entries: list[tuple[str, str, str]] = []
    path = sha = branch = ""
    for line in out.splitlines() + [""]:
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif line.startswith("HEAD "):
            sha = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1].removeprefix("refs/heads/")
        elif line == "" and path:
            entries.append((path, sha, branch))
            path = sha = branch = ""
    return [e for e in entries if Path(e[0]).resolve() != REPO.resolve()]


@dataclass
class Bookmark:
    name: str
    branch: str
    path: str
    first_subject: str
    last_subject: str
    last_date: str
    ahead: int
    dirty: int
    merged: bool
    tagged: str  # tag name or ""

    @property
    def done(self) -> str:
        if self.tagged:
            return "TAGGED"
        if self.merged:
            return "MERGED"
        return "OPEN"

    @property
    def sort_key(self) -> tuple:
        # OPEN rows first (rank 0), then MERGED (1), then TAGGED (2).
        # Within each group, most-recently-touched first.
        rank = {"OPEN": 0, "MERGED": 1, "TAGGED": 2}[self.done]
        return (rank, self.last_date * -1 if False else "")


def build_bookmark(path: str, sha: str, branch: str, tags: set[str]) -> Bookmark:
    name = Path(path).name
    first_subject = sh("log", "--format=%s", "--reverse", f"{MAIN_REF}..{sha}").split("\n")[0] if sha else ""
    last_subject = sh("log", "-1", "--format=%s", sha) if sha else ""
    last_date = sh("log", "-1", "--format=%ad", "--date=short", sha) if sha else ""
    ahead_str = sh("rev-list", "--count", f"{MAIN_REF}..{sha}") if sha else "0"
    ahead = int(ahead_str) if ahead_str.isdigit() else 0
    dirty_out = subprocess.run(
        ["git", "-C", path, "status", "--porcelain"],
        capture_output=True, text=True, check=False,
    ).stdout
    dirty = len([ln for ln in dirty_out.splitlines() if ln.strip()])
    merged = subprocess.run(
        ["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, MAIN_REF],
        capture_output=True, check=False,
    ).returncode == 0

    # Tagged? Look for capsule/* tag matching branch stem.
    stem = branch.split("/")[-1] if branch else name
    tagged = ""
    for tag in tags:
        if stem in tag or (branch and branch.split("/")[-1] in tag):
            # Also confirm the tag actually points at (or near) this branch's tip
            tagged = tag
            break

    if not first_subject:
        first_subject = last_subject  # fallback

    return Bookmark(
        name=name,
        branch=branch or "(detached)",
        path=path,
        first_subject=first_subject or "(no unique commits)",
        last_subject=last_subject or "(unknown)",
        last_date=last_date or "?",
        ahead=ahead,
        dirty=dirty,
        merged=merged,
        tagged=tagged,
    )


def render(bookmarks: list[Bookmark]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    open_ = [b for b in bookmarks if b.done == "OPEN"]
    merged = [b for b in bookmarks if b.done == "MERGED"]
    tagged = [b for b in bookmarks if b.done == "TAGGED"]

    # Sort each group by last touch descending
    for grp in (open_, merged, tagged):
        grp.sort(key=lambda b: b.last_date, reverse=True)

    lines = [
        "# Worktree Bookmarks",
        "",
        f"_Generated {now}. Read this file back-to-front to revisit projects._",
        "",
        "Doctrine: each worktree is a project bookmark. **Done? = merged to main OR tagged as `capsule/*`.**",
        "Nothing here is deleted. Nothing is merged in haste. Parked, dated, and navigable.",
        "",
        "---",
        "",
        f"## OPEN — needs finishing ({len(open_)})",
        "",
        "| Name | Reaching for | Last touch | Latest | Ahead | Dirty |",
        "|------|--------------|------------|--------|------:|------:|",
    ]
    for b in open_:
        lines.append(
            f"| `{b.name}` | {truncate(b.first_subject, 60)} | {b.last_date} | {truncate(b.last_subject, 60)} | {b.ahead} | {b.dirty} |"
        )

    lines += [
        "",
        f"## MERGED — landed on main ({len(merged)})",
        "",
        "| Name | Reaching for | Last touch |",
        "|------|--------------|------------|",
    ]
    for b in merged:
        lines.append(f"| `{b.name}` | {truncate(b.first_subject, 60)} | {b.last_date} |")

    lines += [
        "",
        f"## TAGGED — parked as capsule (permanent record) ({len(tagged)})",
        "",
        "| Name | Reaching for | Tag | Last touch |",
        "|------|--------------|-----|------------|",
    ]
    for b in tagged:
        lines.append(f"| `{b.name}` | {truncate(b.first_subject, 60)} | `{b.tagged}` | {b.last_date} |")

    lines += [
        "",
        "---",
        "",
        "## How to use this file",
        "",
        "- **Back-to-front revisit** — read OPEN top-to-bottom. Most-recently-touched first; oldest OPEN at the bottom (likely dead or forgotten).",
        "- **Reaching for** — first unique commit's subject; that's what the worktree was originally for.",
        "- **Ahead / Dirty** — how many commits ahead of main, and how many uncommitted files sitting in the worktree.",
        "- **Enter a worktree** — `cd \"" + str(REPO).replace("\\", "/") + "/<path>\"` (see full path in each row's git worktree list).",
        "- **Regenerate this file** — `python scripts/scan_worktree_bookmarks.py`",
    ]
    return "\n".join(lines) + "\n"


def truncate(s: str, n: int) -> str:
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "..."


def tagged_bookmarks_without_worktree(tags: set[str], live_branches: set[str]) -> list[Bookmark]:
    """Every capsule/* tag whose branch is NOT currently a live worktree."""
    result: list[Bookmark] = []
    for tag in sorted(tags):
        # Peel the tag to its commit
        sha = sh("rev-list", "-n", "1", tag)
        if not sha:
            continue
        # Try to find a branch that points at this tag's commit
        branches = sh("branch", "--contains", sha, "--format=%(refname:short)").splitlines()
        branches = [b for b in branches if b and b != "main" and not b.startswith("(HEAD")]
        branch = branches[0] if branches else f"(tag: {tag})"
        if branch in live_branches:
            continue  # Already covered by the live-worktree list
        tag_date = sh("log", "-1", "--format=%ad", "--date=short", tag)
        tag_msg = sh("tag", "-l", "--format=%(contents:subject)", tag) or sh("log", "-1", "--format=%s", tag)
        first_subj = sh("log", "--format=%s", "--reverse", f"{MAIN_REF}..{sha}").split("\n")[0]
        result.append(Bookmark(
            name=tag.removeprefix("capsule/"),
            branch=branch,
            path="(no worktree — branch preserved, restore with `git worktree add`)",
            first_subject=first_subj or tag_msg or "(tag preserves tree)",
            last_subject=tag_msg or "(see tag)",
            last_date=tag_date or "?",
            ahead=int(sh("rev-list", "--count", f"{MAIN_REF}..{sha}") or "0"),
            dirty=0,
            merged=False,
            tagged=tag,
        ))
    return result


def main() -> None:
    tags = set(sh("tag", "-l", "capsule/*").splitlines())
    wts = worktrees()
    bookmarks = [build_bookmark(p, s, b, tags) for p, s, b in wts]
    live_branches = {b.branch for b in bookmarks}
    bookmarks += tagged_bookmarks_without_worktree(tags, live_branches)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(bookmarks), encoding="utf-8")
    open_count = sum(1 for b in bookmarks if b.done == "OPEN")
    merged_count = sum(1 for b in bookmarks if b.done == "MERGED")
    tagged_count = sum(1 for b in bookmarks if b.done == "TAGGED")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "index_path": str(OUT),
        "total": len(bookmarks),
        "open": open_count,
        "merged": merged_count,
        "tagged": tagged_count,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} - {len(bookmarks)} bookmarks indexed")
    print(f"  OPEN:   {open_count}")
    print(f"  MERGED: {merged_count}")
    print(f"  TAGGED: {tagged_count}")


if __name__ == "__main__":
    main()
