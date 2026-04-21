#!/usr/bin/env python3
"""Autonomous executor for approved auto_actor proposals.

Invoked by atlas_approve.py as a detached background subprocess:

    python proposal_runner.py <proposal_id>

Flow:
  1. Load proposal from proposals.json (must be status=approved)
  2. Create branch auto/<proposal_id> — main is never touched
  3. Shell out to `claude -p` (Claude Code headless). Uses the user's existing
     OAuth auth — no ANTHROPIC_API_KEY needed.
  4. Budget cap, timeout, sandbox flags enforced by claude CLI directly.
  5. Final JSON result parsed for cost/duration; status persisted.
  6. Branch is left for user review — runner NEVER merges to main.

Design choice: we use `claude -p` rather than the Anthropic SDK because the
user authenticates Claude Code via OAuth (no raw API key available). `claude -p`
reuses that auth. Claude Code's native tools (Edit, Write, Bash, Read, Grep,
etc.) are richer than what this module would hand-roll.

Delta-kernel is optional. Journal push fails gracefully when it's down —
the work still lands on the branch; only visibility is lost.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from atomic_write import atomic_write_json
from cycleboard_push import (
    _load_api_key,
    get_cycleboard_state,
    put_cycleboard_state,
    _today_date,
    _now_iso,
)

BASE = Path(__file__).parent.resolve()
REPO_ROOT = BASE.parent.parent
PROPOSALS_PATH = BASE / "proposals.json"

# Budget + timeout — all env-configurable
CLAUDE_MODEL = os.environ.get("PROPOSAL_RUNNER_MODEL", "sonnet")
MAX_BUDGET_USD = float(os.environ.get("PROPOSAL_MAX_COST_USD", "2.00"))
WALL_CLOCK_TIMEOUT_S = int(os.environ.get("PROPOSAL_TIMEOUT_S", "900"))

log = logging.getLogger("proposal_runner")


# ---------------------------------------------------------------------------
# Proposal IO
# ---------------------------------------------------------------------------
def load_proposals() -> list[dict[str, Any]]:
    if not PROPOSALS_PATH.exists():
        return []
    return json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))


def save_proposals(proposals: list[dict[str, Any]]) -> None:
    atomic_write_json(PROPOSALS_PATH, proposals)


def find_and_update_status(
    proposal_id: str, **updates: Any
) -> dict[str, Any] | None:
    proposals = load_proposals()
    for p in proposals:
        if p.get("proposal_id") == proposal_id:
            p.update(updates)
            save_proposals(proposals)
            return p
    return None


# ---------------------------------------------------------------------------
# Journal push to CycleBoard
# ---------------------------------------------------------------------------
def journal(content: str, api_key: Optional[str]) -> None:
    """Append one journal entry. Non-fatal on failure."""
    if api_key is None:
        log.info("JOURNAL (no api key): %s", content)
        return
    state = get_cycleboard_state(api_key)
    if state is None:
        log.warning("JOURNAL could not fetch state: %s", content)
        return
    merged = dict(state)
    entries = list(merged.get("Journal") or [])
    entries.append({
        "id": f"runner-{int(time.time() * 1000):x}",
        "date": _today_date(),
        "createdAt": _now_iso(),
        "content": content,
        "mood": None,
    })
    merged["Journal"] = entries
    put_cycleboard_state(merged, api_key)


# ---------------------------------------------------------------------------
# Git branch helpers
# ---------------------------------------------------------------------------
def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=check,
    )


def current_branch() -> str:
    r = _git("rev-parse", "--abbrev-ref", "HEAD", check=False)
    return (r.stdout or "").strip()


def create_branch(branch: str) -> None:
    _git("checkout", "-b", branch)


def branch_exists(branch: str) -> bool:
    r = _git("rev-parse", "--verify", branch, check=False)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------
def build_append_system_prompt(proposal: dict[str, Any], branch: str) -> str:
    return (
        "\n\n--- AUTONOMOUS PROPOSAL EXECUTOR ---\n"
        "You are running headless on a dedicated git branch. Your task:\n\n"
        f"PROPOSAL: {proposal.get('proposal_id')}\n"
        f"TYPE: {proposal.get('dtype')}\n"
        f"DOMAIN: {proposal.get('domain')}\n"
        f"RATIONALE: {proposal.get('rationale', '')}\n"
        f"SUGGESTED ACTION: {proposal.get('suggested_action', '')}\n\n"
        "CONSTRAINTS:\n"
        f"- You are on branch {branch}. Commit here; NEVER merge to main.\n"
        "- Stay inside this repo.\n"
        "- Work within your token and time budget. If the work is larger than "
        "the budget, produce a partial deliverable + a markdown summary of "
        "what's left, and stop.\n"
        "- At the end, run `git add -A` and `git commit` with a conventional "
        "message.\n"
        "- Never run destructive commands (rm -rf, git reset --hard, "
        "git push --force, etc).\n"
        "- If you need information you can't obtain, stop and explain.\n"
    )


def build_user_prompt(proposal: dict[str, Any]) -> str:
    return (
        f"Execute the {proposal.get('dtype')} directive on the "
        f"'{proposal.get('domain')}' domain. Commit the work with a clear "
        f"message on the current branch. End by summarizing what you shipped."
    )


# ---------------------------------------------------------------------------
# Claude CLI invocation
# ---------------------------------------------------------------------------
def _claude_cmd() -> Optional[str]:
    """Locate the claude CLI. Prefers PATH; falls back to ~/.local/bin."""
    found = shutil.which("claude") or shutil.which("claude.cmd")
    if found:
        return found
    home_local = Path.home() / ".local" / "bin" / "claude"
    if home_local.exists():
        return str(home_local)
    return None


def invoke_claude(
    proposal: dict[str, Any], branch: str, api_key_delta: Optional[str]
) -> dict[str, Any]:
    """Run `claude -p` with the proposal as the initial prompt.

    Returns a dict:
        {
            "status": completed|failed|timeout|budget_exceeded,
            "cost_usd": float,
            "duration_seconds": float,
            "final_text": str,
            "raw_result": dict (the claude JSON result if available),
            "stderr_tail": str,
        }
    """
    claude_bin = _claude_cmd()
    if not claude_bin:
        return {
            "status": "failed",
            "cost_usd": 0.0,
            "duration_seconds": 0.0,
            "final_text": "",
            "raw_result": {},
            "stderr_tail": "claude CLI not found on PATH",
        }

    system = build_append_system_prompt(proposal, branch)
    user = build_user_prompt(proposal)

    cmd = [
        claude_bin,
        "-p",
        "--model", CLAUDE_MODEL,
        "--output-format", "json",
        "--max-budget-usd", str(MAX_BUDGET_USD),
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--append-system-prompt", system,
        user,
    ]

    journal(f"spawn: claude -p (model={CLAUDE_MODEL}, budget=${MAX_BUDGET_USD})", api_key_delta)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=WALL_CLOCK_TIMEOUT_S,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start
        return {
            "status": "timeout",
            "cost_usd": 0.0,
            "duration_seconds": round(duration, 1),
            "final_text": "",
            "raw_result": {},
            "stderr_tail": (e.stderr[-500:] if isinstance(e.stderr, str) else "") or f"timeout after {WALL_CLOCK_TIMEOUT_S}s",
        }
    except Exception as e:
        return {
            "status": "failed",
            "cost_usd": 0.0,
            "duration_seconds": round(time.time() - start, 1),
            "final_text": "",
            "raw_result": {},
            "stderr_tail": f"{type(e).__name__}: {e}",
        }

    duration = round(time.time() - start, 1)

    # Parse the last JSON line in stdout (claude -p --output-format json emits
    # a single JSON object on its last line)
    raw: dict[str, Any] = {}
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    cost_usd = float(raw.get("total_cost_usd") or 0.0)
    is_error = bool(raw.get("is_error"))
    subtype = raw.get("subtype", "")
    errors = raw.get("errors") or []
    final_text = str(raw.get("result") or raw.get("response") or "")

    if not raw:
        status = "failed"
    elif subtype == "error_max_budget_usd":
        status = "budget_exceeded"
    elif is_error:
        status = "failed"
    else:
        status = "completed"

    return {
        "status": status,
        "cost_usd": cost_usd,
        "duration_seconds": duration,
        "final_text": final_text[:2000],
        "raw_result": {
            "subtype": subtype,
            "num_turns": raw.get("num_turns"),
            "stop_reason": raw.get("stop_reason"),
            "errors": errors,
            "session_id": raw.get("session_id"),
        },
        "stderr_tail": (proc.stderr or "")[-500:],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(proposal_id: str) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    api_key_delta = _load_api_key()
    journal(f"Runner starting for proposal {proposal_id}", api_key_delta)

    proposal = None
    for p in load_proposals():
        if p.get("proposal_id") == proposal_id:
            proposal = p
            break
    if proposal is None:
        journal(f"Runner ABORT: proposal {proposal_id} not found", api_key_delta)
        return 1
    if proposal.get("status") != "approved":
        journal(
            f"Runner ABORT: proposal {proposal_id} is {proposal.get('status')}, not approved",
            api_key_delta,
        )
        return 1

    # Branch isolation
    branch = f"auto/{proposal_id}"
    try:
        if branch_exists(branch):
            journal(f"Runner ABORT: branch {branch} already exists", api_key_delta)
            return 1
        create_branch(branch)
    except subprocess.CalledProcessError as e:
        journal(f"Runner ABORT: branch create failed: {e.stderr or e}", api_key_delta)
        return 1
    journal(f"Created branch {branch}; invoking claude -p", api_key_delta)
    find_and_update_status(
        proposal_id, status="running", branch=branch, started_at=_now_iso()
    )

    result = invoke_claude(proposal, branch, api_key_delta)

    end_status = result["status"]
    find_and_update_status(
        proposal_id,
        status=end_status,
        completed_at=_now_iso(),
        duration_seconds=result["duration_seconds"],
        cost_usd=round(result["cost_usd"], 4),
        final_text=result["final_text"],
        claude_result=result["raw_result"],
        stderr_tail=result["stderr_tail"],
    )

    summary = (
        f"Runner done: {proposal_id} [{end_status}] branch={branch} "
        f"cost=${result['cost_usd']:.3f} duration={result['duration_seconds']}s"
    )
    if result["final_text"]:
        summary += f"\nFinal: {result['final_text'][:200]}"
    journal(summary + " — review the branch", api_key_delta)

    return 0 if end_status == "completed" else 2


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: proposal_runner.py <proposal_id>", file=sys.stderr)
        return 2
    return run(argv[0])


if __name__ == "__main__":
    sys.exit(main())
