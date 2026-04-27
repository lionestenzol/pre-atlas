#!/usr/bin/env python3
"""Codex-delegate wrapper. ZERO manual steps for the user.

What this does:
  1. Ensures Optogon service is running on :3010 (auto-starts if not)
  2. Drives the `delegate_to_codex` Optogon path one-shot via POST /session/run
  3. Returns the Codex output (prose or parsed JSON when schema is supplied)

Usage from Claude Code (Bash tool) or any script:

  python tools/codex-partner/delegate.py "<user intent in their words>"
  python tools/codex-partner/delegate.py "yeet this with description X" --cwd "C:/path"
  python tools/codex-partner/delegate.py "second opinion on the migration" \
      --schema tools/codex-partner/schemas/decision.schema.json

Exit codes:
  0  delegated successfully (or correctly routed back to Claude)
  1  classifier said anthropic_overlap or no_match (informational, not an error)
  2  Codex execution failed (subprocess error, schema mismatch, timeout)
  3  Optogon could not be reached / started

Output: writes a JSON object to stdout for programmatic parsing:
  {
    "delegated": bool,
    "reason": "matched_intent" | "anthropic_overlap" | "no_match",
    "skill": "yeet" | "vercel-deploy" | ... | null,
    "sandbox": "read-only" | "workspace-write",
    "codex_success": bool,
    "exit_code": int | null,
    "codex_output": str (full Codex stdout),
    "parsed_output": dict | null (when --schema supplied),
    "schema_valid": bool | null,
    "session_id": str,
    "turns_walked": int
  }
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import request as urlreq, error as urlerr


OPTOGON_URL = os.environ.get("OPTOGON_URL", "http://127.0.0.1:3010")
HEALTH_URL = f"{OPTOGON_URL}/health"
RUN_URL = f"{OPTOGON_URL}/session/run"


def _is_running(timeout: float = 1.5) -> bool:
    try:
        with urlreq.urlopen(HEALTH_URL, timeout=timeout) as resp:
            return resp.status == 200
    except (urlerr.URLError, ConnectionError, TimeoutError):
        return False


def _find_optogon_dir() -> Path:
    """Locate services/optogon/ relative to repo root or this script."""
    here = Path(__file__).resolve()
    # tools/codex-partner/delegate.py -> repo at parents[2]
    candidates = [
        here.parents[2] / "services" / "optogon",
        Path.cwd() / "services" / "optogon",
    ]
    for c in candidates:
        if c.exists() and (c / "src" / "optogon" / "main.py").exists():
            return c
    raise SystemExit(f"could not locate services/optogon (tried: {candidates})")


def _start_optogon(quiet: bool = True) -> None:
    """Start Optogon as a background process. Returns when /health is OK."""
    optogon_dir = _find_optogon_dir()
    log_path = Path.home() / ".codex-partner-optogon.log"
    cmd = [
        sys.executable, "-m", "uvicorn",
        "optogon.main:app",
        "--host", "127.0.0.1",
        "--port", "3010",
        "--no-access-log",
    ]
    if not quiet:
        print(f"[delegate] starting Optogon (cwd={optogon_dir}, log={log_path})", file=sys.stderr)
    # Detach via DETACHED_PROCESS on Windows so it survives this script
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(log_path, "ab") as logf:
        subprocess.Popen(
            cmd,
            cwd=str(optogon_dir),
            stdout=logf,
            stderr=logf,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    # Wait up to 30s for /health
    deadline = time.time() + 30
    while time.time() < deadline:
        if _is_running(timeout=1.0):
            return
        time.sleep(0.5)
    raise SystemExit(f"3:Optogon failed to come up within 30s (log: {log_path})")


def _post_run(payload: dict[str, Any], timeout: float = 360.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urlreq.Request(
        RUN_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="Codex-delegate one-shot wrapper")
    p.add_argument("intent", help="Natural-language task description (Bruke's words are fine)")
    p.add_argument("--cwd", default=os.getcwd(), help="Working directory for Codex (default: cwd)")
    p.add_argument("--schema", default=None,
                   help="Path to a JSON Schema for typed handoff (--output-schema)")
    p.add_argument("--quiet", action="store_true", help="Suppress startup messages")
    p.add_argument("--no-autostart", action="store_true",
                   help="Fail if Optogon isn't already running (default: auto-start)")
    args = p.parse_args()

    # Autostart Optogon if down
    if not _is_running():
        if args.no_autostart:
            print(json.dumps({"error": "Optogon not running and --no-autostart set"}),
                  file=sys.stderr)
            return 3
        try:
            _start_optogon(quiet=args.quiet)
        except SystemExit as e:
            msg = str(e)
            print(json.dumps({"error": msg}), file=sys.stderr)
            return 3

    # Resolve schema path to absolute (Optogon resolves relative to REPO_ROOT)
    schema_abs = None
    if args.schema:
        schema_abs = str(Path(args.schema).resolve())

    initial_context: dict[str, Any] = {
        "user_intent": args.intent,
        "cwd": str(Path(args.cwd).resolve()),
    }
    if schema_abs:
        initial_context["output_schema_path"] = schema_abs

    payload = {"path_id": "delegate_to_codex", "initial_context": initial_context}

    try:
        result = _post_run(payload, timeout=420.0)
    except urlerr.URLError as e:
        print(json.dumps({"error": f"Optogon request failed: {e}"}), file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"unexpected: {e}"}), file=sys.stderr)
        return 3

    state = result.get("state", {})
    outputs = result.get("outputs", {})
    sysctx = state.get("context", {}).get("system", {})

    # Pull canonical fields (outputs[] survived close-trim; sysctx may have been wiped)
    delegated = bool(sysctx.get("should_delegate", outputs.get("codex_success") is not None))
    reason = sysctx.get("delegate_reason", "unknown")
    skill = sysctx.get("target_skill") or outputs.get("skill")
    sandbox = sysctx.get("sandbox") or outputs.get("sandbox") or "read-only"
    codex_success = outputs.get("codex_success")
    exit_code = outputs.get("exit_code")
    codex_output = outputs.get("codex_output") or ""
    parsed_output = outputs.get("parsed_output")
    schema_valid = outputs.get("schema_valid")

    summary = {
        "delegated": delegated,
        "reason": reason,
        "skill": skill,
        "sandbox": sandbox,
        "codex_success": codex_success,
        "exit_code": exit_code,
        "codex_output": codex_output,
        "parsed_output": parsed_output,
        "schema_valid": schema_valid,
        "session_id": result.get("session_id"),
        "turns_walked": result.get("turns_walked"),
        "closed": result.get("closed"),
    }
    print(json.dumps(summary, indent=2, default=str))

    # Exit codes:
    if not delegated:
        return 1   # routed back to Claude (informational)
    if codex_success is False:
        return 2   # codex ran but failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
