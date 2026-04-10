"""
validate_actions.py — Safety gate for Atlas action execution.

Reads a brief JSON file, validates every action against safety rules.
Outputs a validated brief or exits with error.

Env vars:
  - BRIEF_PATH (required) — path to brief JSON file

Safety rules:
  - Block dangerous commands (rm -rf, sudo, shutdown, format, etc.)
  - Restrict file writes to ./workspace/ and ./output/
  - Restrict ports to 3000-3999
  - Max timeout per action: 120s
  - Max 10 actions per brief
"""

import json
import os
import re
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Dangerous patterns (blocked unconditionally)
# ---------------------------------------------------------------------------

BLOCKED_COMMANDS: list[re.Pattern] = [
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\breboot\b", re.I),
    re.compile(r"\bformat\s+[a-z]:", re.I),
    re.compile(r"\bdel\s+/s\s+/q\s+[a-z]:\\", re.I),
    re.compile(r"\bmkfs\b", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r"\b:(){", re.I),  # fork bomb
    re.compile(r"\bcurl\b.*\|\s*(?:bash|sh|cmd)\b", re.I),  # pipe to shell
    re.compile(r"\bpowershell\b.*-enc", re.I),  # encoded powershell
    re.compile(r"\btaskkill\s+/f\s+/im\s+(?:explorer|svchost|csrss|winlogon)", re.I),
    re.compile(r"\breg\s+delete\b", re.I),
    re.compile(r"\bnet\s+user\b.*\/add", re.I),
]

# Allowed port range
PORT_MIN = 3000
PORT_MAX = 3999

# Max actions per brief
MAX_ACTIONS = 10

# Max timeout per action (ms)
MAX_TIMEOUT_MS = 120_000


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def check_dangerous_command(payload: str) -> Optional[str]:
    """Check if payload contains dangerous commands. Returns reason or None."""
    for pattern in BLOCKED_COMMANDS:
        if pattern.search(payload):
            return f"Blocked pattern: {pattern.pattern}"
    return None


def check_port_range(payload: str) -> Optional[str]:
    """Check if any port references are within allowed range."""
    port_matches = re.findall(r"(?:--port|:)(\d{4,5})\b", payload)
    for port_str in port_matches:
        port = int(port_str)
        if port < PORT_MIN or port > PORT_MAX:
            return f"Port {port} outside allowed range {PORT_MIN}-{PORT_MAX}"
    return None


def check_file_write(action: dict) -> Optional[str]:
    """Check file_write actions for path safety."""
    if action.get("type") != "file_write":
        return None

    payload = action.get("payload", {})
    if isinstance(payload, dict):
        path = payload.get("path", "")
    else:
        return "file_write payload must be an object with 'path'"

    # Normalize path
    path = path.replace("\\", "/").lower()

    # Block absolute paths outside workspace
    if re.match(r"^[a-z]:/", path) and "workspace" not in path and "output" not in path:
        return f"File write to {path} blocked — only ./workspace/ and ./output/ allowed"

    # Block path traversal
    if ".." in path:
        return f"Path traversal blocked: {path}"

    return None


def check_timeout(action: dict) -> Optional[str]:
    """Check timeout is within limits."""
    timeout = action.get("timeout", MAX_TIMEOUT_MS)
    if isinstance(timeout, (int, float)) and timeout > MAX_TIMEOUT_MS:
        return f"Timeout {timeout}ms exceeds max {MAX_TIMEOUT_MS}ms"
    return None


def validate_action(action: dict, index: int) -> list[str]:
    """Validate a single action. Returns list of violations."""
    violations: list[str] = []

    action_id = action.get("id", f"action_{index}")

    # Extract payload as string for command checking
    payload = action.get("payload", "")
    payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)

    # Check dangerous commands
    danger = check_dangerous_command(payload_str)
    if danger:
        violations.append(f"[{action_id}] BLOCKED: {danger}")

    # Check port range
    port_issue = check_port_range(payload_str)
    if port_issue:
        violations.append(f"[{action_id}] BLOCKED: {port_issue}")

    # Check file writes
    file_issue = check_file_write(action)
    if file_issue:
        violations.append(f"[{action_id}] BLOCKED: {file_issue}")

    # Check timeout
    timeout_issue = check_timeout(action)
    if timeout_issue:
        violations.append(f"[{action_id}] BLOCKED: {timeout_issue}")

    return violations


def validate_brief(brief: dict) -> tuple[bool, list[str]]:
    """Validate entire brief. Returns (passed, violations)."""
    violations: list[str] = []

    actions = brief.get("actions", [])

    if not actions:
        violations.append("No actions found in brief")
        return False, violations

    if len(actions) > MAX_ACTIONS:
        violations.append(f"Too many actions: {len(actions)} > max {MAX_ACTIONS}")
        return False, violations

    for i, action in enumerate(actions):
        action_violations = validate_action(action, i)
        violations.extend(action_violations)

    passed = len(violations) == 0
    return passed, violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    brief_path = os.environ.get("BRIEF_PATH", "").strip()
    if not brief_path:
        print("ERROR: BRIEF_PATH environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Load brief
    try:
        with open(brief_path, "r", encoding="utf-8") as f:
            brief = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Cannot read brief: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate
    passed, violations = validate_brief(brief)

    if not passed:
        error_result = {
            "error": "BLOCKED_ACTION",
            "brief_path": brief_path,
            "violations": violations,
        }
        print(json.dumps(error_result, indent=2))
        print(f"\nValidation FAILED: {len(violations)} violation(s)", file=sys.stderr)
        sys.exit(1)

    # Write validated brief
    output_dir = os.path.dirname(brief_path) or "output"
    basename = os.path.basename(brief_path)
    validated_path = os.path.join(output_dir, f"validated_{basename}")

    brief["validated"] = True
    brief["validated_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()

    with open(validated_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2)

    print(json.dumps({"status": "PASSED", "actions": len(brief["actions"]), "path": validated_path}, indent=2))
    print(f"\nValidation PASSED: {len(brief['actions'])} actions cleared", file=sys.stderr)
    print(f"Validated brief: {validated_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
