#!/usr/bin/env python3
"""CLI to approve/deny auto_actor proposals and fire the runner.

Proposals are written by cycleboard_push.py when auto_actor flags a directive
as `needs_approval`. They land in proposals.json. This CLI lets the user:

    python atlas_approve.py list               # show pending proposals
    python atlas_approve.py approve <id>       # approve + fire subprocess runner
    python atlas_approve.py approve <id> --no-fire  # approve only; run later
    python atlas_approve.py deny <id> [why]    # deny + journal it

Two ways to run an approved proposal:
  1. Subprocess runner (default when `approve` fires): spawns proposal_runner.py
     which calls `claude -p` headless. Fully detached. Reloads the Claude Code
     system prompt (~30k cached tokens) every invocation.
  2. In-session slash command: run `/run-proposal <id>` inside an active Claude
     Code session. Cheaper (no system-prompt reload). See
     .claude/commands/run-proposal.md.

Both paths write to the same `auto/<id>` branch scheme and update proposals.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_write import atomic_write_json

BASE = Path(__file__).parent.resolve()
PROPOSALS_PATH = BASE / "proposals.json"
RUNNER_SCRIPT = BASE / "proposal_runner.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_proposals() -> list[dict[str, Any]]:
    if not PROPOSALS_PATH.exists():
        return []
    try:
        data = json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"failed to read {PROPOSALS_PATH}: {e}", file=sys.stderr)
        return []


def save_proposals(proposals: list[dict[str, Any]]) -> None:
    atomic_write_json(PROPOSALS_PATH, proposals)


def find_proposal(
    proposals: list[dict[str, Any]], proposal_id: str
) -> dict[str, Any] | None:
    for p in proposals:
        if p.get("proposal_id") == proposal_id:
            return p
    return None


def cmd_list() -> int:
    proposals = load_proposals()
    pending = [p for p in proposals if p.get("status") == "pending"]
    if not pending:
        print("No pending proposals.")
        return 0
    print(f"Pending proposals ({len(pending)}):")
    print()
    for p in pending:
        pid = p.get("proposal_id", "?")
        dtype = p.get("dtype", "?")
        domain = p.get("domain", "?")
        rationale = (p.get("rationale") or "").strip()[:100]
        confidence = p.get("confidence", "?")
        risk = p.get("risk_level", "?")
        print(f"  {pid}  {dtype}/{domain}  (confidence={confidence}, risk={risk})")
        if rationale:
            print(f"    {rationale}")
    return 0


def _spawn_runner(proposal_id: str) -> None:
    """Spawn proposal_runner.py as a detached background subprocess.

    Uses creationflags on Windows to detach fully so the runner continues
    after the approve command returns.
    """
    kwargs: dict[str, Any] = {
        "cwd": str(BASE),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        # Explicit env inheritance: on Windows, DETACHED_PROCESS combined with
        # stream redirection to DEVNULL has been observed to drop ANTHROPIC_API_KEY
        # from the child. Passing os.environ.copy() makes inheritance deterministic.
        "env": os.environ.copy(),
    }
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, str(RUNNER_SCRIPT), proposal_id],
        **kwargs,
    )


def cmd_approve(proposal_id: str, fire: bool = True) -> int:
    proposals = load_proposals()
    p = find_proposal(proposals, proposal_id)
    if not p:
        print(f"proposal {proposal_id} not found", file=sys.stderr)
        return 1
    status = p.get("status")
    if status != "pending":
        print(f"proposal {proposal_id} is {status}, not pending", file=sys.stderr)
        return 1
    p["status"] = "approved"
    p["approved_at"] = _now_iso()
    save_proposals(proposals)
    if fire:
        _spawn_runner(proposal_id)
        print(f"Approved {proposal_id}. Subprocess runner started in background.")
        print(f"Watch progress: atlas journal   (or check CycleBoard)")
    else:
        print(f"Approved {proposal_id}. No runner fired.")
        print(f"Run later via one of:")
        print(f"  python proposal_runner.py {proposal_id}    # subprocess (headless)")
        print(f"  /run-proposal {proposal_id}                # slash command (in-session)")
    return 0


def cmd_deny(proposal_id: str, reason: str | None = None) -> int:
    proposals = load_proposals()
    p = find_proposal(proposals, proposal_id)
    if not p:
        print(f"proposal {proposal_id} not found", file=sys.stderr)
        return 1
    status = p.get("status")
    if status != "pending":
        print(f"proposal {proposal_id} is {status}, not pending", file=sys.stderr)
        return 1
    p["status"] = "denied"
    p["denied_at"] = _now_iso()
    if reason:
        p["deny_reason"] = reason
    save_proposals(proposals)
    print(f"Denied {proposal_id}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="show pending proposals")

    ap = sub.add_parser("approve", help="approve + fire runner")
    ap.add_argument("id", help="proposal_id")
    ap.add_argument("--no-fire", action="store_true", help="flip status but don't spawn runner (for testing)")

    dp = sub.add_parser("deny", help="mark as denied")
    dp.add_argument("id", help="proposal_id")
    dp.add_argument("reason", nargs="?", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "list" or args.cmd is None:
        return cmd_list()
    if args.cmd == "approve":
        return cmd_approve(args.id, fire=not args.no_fire)
    if args.cmd == "deny":
        return cmd_deny(args.id, args.reason)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
