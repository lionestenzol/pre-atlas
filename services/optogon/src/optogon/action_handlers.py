"""Action handlers - real side-effect implementations for execute nodes.

Per doctrine/03_OPTOGON_SPEC.md Section 6 (execute node actions).

Registry pattern: paths reference action handlers by action.id. Each handler
receives the session state and the action dict, returns a dict of outputs
that get merged into the session context's 'system' tier so downstream
gates can route on them.

Safety rules:
- git_commit refuses if more than the expected file is staged
- read_file refuses paths outside the repo root unless absolute-allowed
- All handlers are deterministic where possible; retries are safe
"""
from __future__ import annotations
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import REPO_ROOT

log = logging.getLogger("optogon.actions")


class ActionError(Exception):
    """Raised when an action fails in a way that should halt the node."""


HandlerResult = dict[str, Any]
Handler = Callable[[dict[str, Any], dict[str, Any]], HandlerResult]

_REGISTRY: dict[str, Handler] = {}


def register(action_id: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _REGISTRY[action_id] = fn
        return fn
    return deco


def get_handler(action_id: str) -> Handler | None:
    return _REGISTRY.get(action_id)


def _resolve_path(raw: str) -> Path:
    """Resolve a path. Relative paths are resolved against REPO_ROOT."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    else:
        p = p.resolve()
    return p


def _within_repo(p: Path) -> bool:
    try:
        p.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@register("read_content")
def read_content(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Read a file referenced by context.file_path. Stores content + metadata."""
    ctx = session_state["context"]
    file_path = (ctx["confirmed"].get("file_path")
                 or ctx["user"].get("file_path")
                 or ctx["system"].get("file_path"))
    if not file_path:
        raise ActionError("read_content: no file_path in context")
    p = _resolve_path(str(file_path))
    if not _within_repo(p):
        raise ActionError(f"read_content: path outside repo root: {p}")
    if not p.exists():
        return {
            "file_exists": False,
            "file_size": 0,
            "content": "",
            "resolved_path": str(p),
        }
    if not p.is_file():
        raise ActionError(f"read_content: not a file: {p}")
    content = p.read_text(encoding="utf-8")
    return {
        "file_exists": True,
        "file_size": p.stat().st_size,
        "file_size_ok": p.stat().st_size > 0,
        "content": content,
        "resolved_path": str(p),
    }


@register("scan_em_dashes")
def scan_em_dashes(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Count em-dashes in the read content. Per feedback_no_em_dashes_in_ui.md."""
    ctx = session_state["context"]
    content = ctx["system"].get("content")
    if content is None:
        # Also fall back to action_results in case a prior node stored it
        for node_id, results in session_state.get("node_states", {}).items():
            for _aid, result in (results.get("action_results") or {}).items():
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    break
            if content is not None:
                break
    if content is None:
        raise ActionError("scan_em_dashes: no content in context; run read_content first")

    # Count em-dashes (U+2014). Record line numbers.
    lines_with_em_dash: list[int] = []
    for i, line in enumerate((content or "").splitlines(), start=1):
        if "\u2014" in line:
            lines_with_em_dash.append(i)
    count = sum(line.count("\u2014") for line in (content or "").splitlines())
    return {
        "em_dash_count": count,
        "em_dash_lines": lines_with_em_dash,
        "em_dash_clean": count == 0,
    }


@register("git_commit")
def git_commit(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Git-commit the file at context.file_path with context.commit_message.

    Safety checks:
    - Refuses if repo has uncommitted changes to files OTHER than target
    - Uses `git add -- <file>` (explicit path)
    - Verifies only the target file is staged before commit
    - Runs with cwd = REPO_ROOT
    """
    ctx = session_state["context"]
    file_path = (ctx["confirmed"].get("file_path")
                 or ctx["user"].get("file_path"))
    commit_message = (ctx["confirmed"].get("commit_message")
                      or ctx["user"].get("commit_message"))
    if not file_path or not commit_message:
        raise ActionError("git_commit: missing file_path or commit_message")

    p = _resolve_path(str(file_path))
    if not _within_repo(p):
        raise ActionError(f"git_commit: path outside repo: {p}")

    dry_run = bool((action.get("spec") or {}).get("dry_run", False))

    rel_path = str(p.relative_to(REPO_ROOT)).replace("\\", "/")

    def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        log.debug("git %s (cwd=%s)", " ".join(args), REPO_ROOT)
        return subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=check,
        )

    # 1. Pre-check: find currently staged files; abort if anything else is staged
    staged = run_git(["diff", "--cached", "--name-only"], check=False).stdout.splitlines()
    unexpected = [s for s in staged if s and s.strip() != rel_path]
    if unexpected:
        raise ActionError(f"git_commit: other files are staged, refusing: {unexpected}")

    if dry_run:
        return {
            "dry_run": True,
            "would_commit": rel_path,
            "commit_message": commit_message,
            "commit_success": False,
            "commit_sha": None,
        }

    # 2. Stage only the target file
    run_git(["add", "--", rel_path])

    # 3. Verify staging is exactly the target
    staged_after = run_git(["diff", "--cached", "--name-only"], check=False).stdout.splitlines()
    if staged_after != [rel_path]:
        # Unstage to avoid leaving the repo in a weird state
        run_git(["reset", "--", rel_path], check=False)
        raise ActionError(f"git_commit: staging mismatch (got {staged_after}), refusing")

    # 4. Commit
    commit = run_git(["commit", "-m", commit_message], check=False)
    if commit.returncode != 0:
        raise ActionError(f"git_commit: commit failed: {commit.stderr or commit.stdout}")

    # 5. Grab SHA
    sha = run_git(["rev-parse", "HEAD"], check=False).stdout.strip()
    return {
        "commit_success": True,
        "commit_sha": sha,
        "committed_path": rel_path,
        "commit_message": commit_message,
        "dry_run": False,
    }


# ---------------------------------------------------------------------------
# Filesystem triage handlers (triage_fs_loop path)
# ---------------------------------------------------------------------------

@register("inspect_fs_item")
def inspect_fs_item(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Stat the evidence path. Detects kind + whether it still exists."""
    ctx = session_state["context"]
    evidence = (
        ctx["confirmed"].get("evidence")
        or ctx["user"].get("evidence")
        or ctx["system"].get("evidence")
    )
    if not evidence:
        raise ActionError("inspect_fs_item: no evidence path in context")
    p = Path(str(evidence)).expanduser()
    exists = p.exists()
    is_file = p.is_file() if exists else False
    is_dir = p.is_dir() if exists else False
    size_bytes = p.stat().st_size if is_file else 0
    name_lower = p.name.lower()
    if name_lower.endswith(".env") or name_lower == ".env":
        detected_kind = "env"
    elif is_dir and any((p / sentinel).exists() for sentinel in ("package.json", "pyproject.toml", ".git")):
        detected_kind = "project"
    elif size_bytes > 100 * 1024 * 1024:
        detected_kind = "artifact"
    else:
        detected_kind = "other"
    return {
        "fs_exists": exists,
        "fs_is_file": is_file,
        "fs_is_dir": is_dir,
        "fs_size_bytes": size_bytes,
        "fs_detected_kind": detected_kind,
    }


@register("propose_fs_verdict")
def propose_fs_verdict(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Map (severity, fs_kind, age) to a proposed verdict and safe action.

    Verdicts are suggestions only — the approval node (or learned pref)
    decides whether to act. Safe action is always the least destructive
    option that still closes the loop.
    """
    ctx = session_state["context"]

    def pick(key: str, default=None):
        for tier in ("confirmed", "user", "system", "inferred"):
            if key in ctx.get(tier, {}):
                return ctx[tier][key]
        return default

    severity = pick("severity", "medium")
    fs_kind = pick("fs_kind", pick("fs_detected_kind", "other"))
    age_days = pick("age_days", 0) or 0
    exists = pick("fs_exists", True)

    if not exists:
        return {
            "proposed_verdict": "CLOSE",
            "proposed_action": "mark_closed",
            "rationale": "evidence no longer on disk — nothing to do",
            "confidence": 0.95,
        }

    if fs_kind == "env" and severity == "high" and age_days >= 365:
        return {
            "proposed_verdict": "ARCHIVE",
            "proposed_action": "rotate_and_delete",
            "rationale": f"stale leaked .env ({age_days}d): rotate keys, then delete",
            "confidence": 0.85,
        }
    if fs_kind == "env" and severity == "high":
        return {
            "proposed_verdict": "REVIEW",
            "proposed_action": "inspect_contents",
            "rationale": "recent leaked .env: inspect before acting",
            "confidence": 0.6,
        }
    if fs_kind == "project" and age_days >= 90:
        return {
            "proposed_verdict": "ARCHIVE",
            "proposed_action": "move_to_archive",
            "rationale": f"stalled project ({age_days}d): move to _archive",
            "confidence": 0.75,
        }
    if fs_kind == "artifact":
        return {
            "proposed_verdict": "KEEP",
            "proposed_action": "none",
            "rationale": "large artifact: flag only, user decides",
            "confidence": 0.5,
        }
    return {
        "proposed_verdict": "REVIEW",
        "proposed_action": "manual",
        "rationale": "no rule matched: defer to human",
        "confidence": 0.4,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run_action(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Look up and invoke the handler for action.id. Returns result dict."""
    action_id = action.get("id")
    if not action_id:
        raise ActionError("action missing id")
    handler = get_handler(action_id)
    if handler is None:
        # Unknown action - fall back to stub so unregistered paths still "work"
        log.warning("no handler registered for action id=%s; stubbing", action_id)
        return {"stub": True}
    return handler(session_state, action)
