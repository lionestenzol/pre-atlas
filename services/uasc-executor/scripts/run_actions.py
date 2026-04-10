"""
run_actions.py — Execute validated brief actions through OpenAI Codex CLI.

Reads a validated brief JSON, executes each action sequentially via `codex exec`.
Stops on first failure (unless retries specified). Writes results to output/.

Env vars:
  - BRIEF_PATH  (required) — path to validated brief JSON
  - CODEX_WORKDIR (optional) — working directory for codex (default: cwd)

Writes:
  - output/results_{brief_filename}.json
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional


CODEX_CMD = shutil.which("codex") or "codex"
CODEX_FLAGS = ["exec", "--dangerously-bypass-approvals-and-sandbox"]
DEFAULT_TIMEOUT_S = 120
DELTA_URL = os.environ.get("ATLAS_DELTA_URL", "http://localhost:3001")


def load_brief(path: str) -> dict:
    """Load and validate brief file."""
    with open(path, "r", encoding="utf-8") as f:
        brief = json.load(f)

    if not brief.get("validated"):
        print("ERROR: Brief is not validated. Run validate_actions.py first.", file=sys.stderr)
        sys.exit(1)

    if not brief.get("actions"):
        print("ERROR: No actions in brief.", file=sys.stderr)
        sys.exit(1)

    return brief


def build_codex_prompt(action: dict) -> str:
    """Convert action dict into a Codex-executable prompt."""
    action_type = action.get("type", "command")
    executor = action.get("executor", "shell")
    payload = action.get("payload", "")
    description = action.get("action", "")

    if action_type == "command" and executor == "shell":
        if isinstance(payload, str):
            return f"Run this exact command and return only the output. Do not modify or improve it:\n{payload}"
        return f"Execute: {description}"

    elif action_type == "file_write" and executor == "fs":
        if isinstance(payload, dict):
            path = payload.get("path", "output.txt")
            content = payload.get("content", "")
            return f"Write the following content to the file '{path}'. Create parent directories if needed. Content:\n{content}"
        return f"Write file: {description}"

    elif action_type == "api_call" and executor == "http":
        if isinstance(payload, dict):
            method = payload.get("method", "GET")
            url = payload.get("url", "")
            body = payload.get("body")
            body_str = f" with body: {json.dumps(body)}" if body else ""
            return f"Make an HTTP {method} request to {url}{body_str}. Return the response."
        return f"API call: {description}"

    elif action_type == "atlas_cmd" and executor == "work_queue":
        if isinstance(payload, dict):
            cmd = payload.get("cmd", "")
            return f"Run this curl command exactly:\ncurl -s -X POST http://localhost:3001/api/work/request -H \"Content-Type: application/json\" -d '{{\"type\":\"system\",\"title\":\"sub-{cmd}\",\"timeout_ms\":60000,\"metadata\":{{\"cmd\":\"{cmd}\",\"inputs\":{{}},\"source\":\"executor\",\"intent\":\"sub-task\"}}}}'"
        return f"Atlas command: {description}"

    # Fallback: use description + payload as-is
    return f"{description}\n{payload}" if payload else description


def run_action_via_codex(action: dict, workdir: str) -> dict:
    """Execute a single action through Codex CLI. Returns result dict."""
    action_id = action.get("id", "unknown")
    timeout_ms = action.get("timeout", DEFAULT_TIMEOUT_S * 1000)
    timeout_s = min(timeout_ms // 1000, DEFAULT_TIMEOUT_S)
    retries = action.get("retries", 1)

    prompt = build_codex_prompt(action)

    last_error = None
    for attempt in range(retries):
        start = time.time()
        try:
            cmd = [CODEX_CMD] + CODEX_FLAGS + ["-C", workdir, prompt]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=workdir,
                shell=False,
                stdin=subprocess.DEVNULL,
            )

            duration_ms = int((time.time() - start) * 1000)

            if result.returncode == 0:
                output = result.stdout.strip()
                if result.stderr.strip():
                    output += f"\n[stderr] {result.stderr.strip()}"
                return {
                    "id": action_id,
                    "status": "success",
                    "output": output[:5000],  # cap output size
                    "error": None,
                    "duration_ms": duration_ms,
                    "attempt": attempt + 1,
                }
            else:
                last_error = result.stderr.strip() or f"Exit code: {result.returncode}"
                print(f"[RUN] Action {action_id} attempt {attempt + 1} failed: {last_error}", file=sys.stderr)

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            last_error = f"Timeout after {timeout_s}s"
            print(f"[RUN] Action {action_id} attempt {attempt + 1} timed out", file=sys.stderr)

        except FileNotFoundError:
            return {
                "id": action_id,
                "status": "failed",
                "output": "",
                "error": "codex CLI not found. Install: npm i -g @openai/codex",
                "duration_ms": 0,
                "attempt": attempt + 1,
            }

        # Brief delay between retries
        if attempt < retries - 1:
            time.sleep(2)

    duration_ms = int((time.time() - start) * 1000)
    return {
        "id": action_id,
        "status": "failed",
        "output": "",
        "error": last_error or "Unknown error",
        "duration_ms": duration_ms,
        "attempt": retries,
    }


def run_action_direct(action: dict, workdir: str) -> dict:
    """Execute shell commands directly (no Codex). Faster for simple commands."""
    action_id = action.get("id", "unknown")
    action_type = action.get("type", "command")
    payload = action.get("payload", "")
    timeout_ms = action.get("timeout", DEFAULT_TIMEOUT_S * 1000)
    timeout_s = min(timeout_ms // 1000, DEFAULT_TIMEOUT_S)

    if action_type != "command" or not isinstance(payload, str):
        return run_action_via_codex(action, workdir)

    start = time.time()
    try:
        result = subprocess.run(
            payload,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=workdir,
            shell=True,
        )

        duration_ms = int((time.time() - start) * 1000)
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n[stderr] {result.stderr.strip()}"

        return {
            "id": action_id,
            "status": "success" if result.returncode == 0 else "failed",
            "output": output[:5000],
            "error": None if result.returncode == 0 else f"Exit code: {result.returncode}",
            "duration_ms": duration_ms,
            "attempt": 1,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "id": action_id,
            "status": "failed",
            "output": "",
            "error": f"Timeout after {timeout_s}s",
            "duration_ms": duration_ms,
            "attempt": 1,
        }


def report_to_delta(job_id: Optional[str], results: list[dict], brief: dict) -> None:
    """POST results back to delta-kernel work/complete endpoint."""
    if not job_id:
        print("[RUN] No job_id — skipping delta report", file=sys.stderr)
        return

    all_success = all(r["status"] == "success" for r in results)
    total_duration = sum(r.get("duration_ms", 0) for r in results)

    payload = {
        "job_id": job_id,
        "outcome": "completed" if all_success else "failed",
        "result": {
            "actions_total": len(results),
            "actions_succeeded": sum(1 for r in results if r["status"] == "success"),
            "actions_failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        },
        "metrics": {"duration_ms": total_duration},
    }

    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{DELTA_URL}/api/work/complete",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[RUN] Delta report: {resp.status}", file=sys.stderr)
    except Exception as e:
        print(f"[RUN] Delta report failed: {e}", file=sys.stderr)


def main() -> None:
    brief_path = os.environ.get("BRIEF_PATH", "").strip()
    if not brief_path:
        print("ERROR: BRIEF_PATH environment variable is required", file=sys.stderr)
        sys.exit(1)

    workdir = os.environ.get("CODEX_WORKDIR", os.getcwd())
    use_codex = os.environ.get("USE_CODEX", "true").lower() == "true"

    brief = load_brief(brief_path)
    actions = brief.get("actions", [])
    job_id = brief.get("job_id")
    now = datetime.now(timezone.utc)

    print(f"[RUN] Executing {len(actions)} actions from {brief_path}", file=sys.stderr)
    print(f"[RUN] Executor: {'codex' if use_codex else 'direct'}", file=sys.stderr)
    print(f"[RUN] Workdir: {workdir}", file=sys.stderr)

    results: list[dict] = []

    for i, action in enumerate(actions):
        action_id = action.get("id", f"a{i+1}")
        action_desc = action.get("action", action.get("payload", "unknown"))
        print(f"[RUN] [{i+1}/{len(actions)}] {action_id}: {action_desc}", file=sys.stderr)

        if use_codex:
            result = run_action_via_codex(action, workdir)
        else:
            result = run_action_direct(action, workdir)

        results.append(result)

        if result["status"] == "success":
            print(f"[RUN] [{i+1}/{len(actions)}] {action_id}: SUCCESS ({result['duration_ms']}ms)", file=sys.stderr)
        else:
            print(f"[RUN] [{i+1}/{len(actions)}] {action_id}: FAILED — {result['error']}", file=sys.stderr)
            # Stop on failure (strict executor behavior)
            print(f"[RUN] Stopping execution at action {action_id}", file=sys.stderr)
            break

    # Build output
    all_success = all(r["status"] == "success" for r in results)
    output = {
        "timestamp": now.isoformat(),
        "brief_path": brief_path,
        "objective": brief.get("objective", ""),
        "executor": "codex" if use_codex else "direct",
        "status": "completed" if all_success else "failed",
        "actions_total": len(actions),
        "actions_executed": len(results),
        "actions_succeeded": sum(1 for r in results if r["status"] == "success"),
        "actions_failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }

    # Write results
    output_dir = os.path.dirname(brief_path) or "output"
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.basename(brief_path).replace("validated_", "")
    results_path = os.path.join(output_dir, f"results_{basename}")

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(json.dumps(output, indent=2))
    print(f"\nResults written to: {results_path}", file=sys.stderr)

    # Report to delta
    report_to_delta(job_id, results, brief)

    # Exit with appropriate code
    if not all_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
