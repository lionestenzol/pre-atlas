"""
build_brief.py — Generate a structured execution brief with machine-executable actions.

Hybrid approach:
  1. Template patterns match common goals to concrete actions
  2. Claude API fallback for unmatched goals

Reads:
  - %TEMP%/atlas_state.json   (delta-kernel state)
  - %TEMP%/atlas_work.json    (work queue status)
  - output/atlas_snapshot.json (latest snapshot, optional)

Env vars:
  - BRIEF_GOAL          (required) — target outcome
  - BRIEF_CONTEXT       (optional) — additional context
  - BRIEF_OUTPUT_DIR    (optional) — output directory
  - ANTHROPIC_API_KEY   (optional) — enables Claude fallback

Writes:
  - output/brief_{date}_{slug}.json
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-")[:max_len]


def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# System state extraction
# ---------------------------------------------------------------------------

def extract_system_state(state: dict, work: dict) -> dict:
    capacity = work.get("capacity", {})
    return {
        "mode": state.get("mode", "UNKNOWN"),
        "build_allowed": work.get("build_allowed", False),
        "closure_ratio": work.get("closure_ratio", 0),
        "sleep_hours": state.get("sleepHours", 0),
        "open_loops": state.get("openLoops", 0),
        "queue_available": capacity.get("available", 0),
        "queue_active": capacity.get("active", 0),
    }


def derive_constraints(sys_state: dict) -> list[str]:
    constraints: list[str] = []
    if not sys_state["build_allowed"]:
        constraints.append("Build not allowed — system in closure mode, must close loops first")
    if sys_state["mode"] == "CLOSURE":
        constraints.append("Mode is CLOSURE — only loop-closing and system tasks permitted")
    elif sys_state["mode"] == "RECOVER":
        constraints.append("Mode is RECOVER — sleep deficit detected, limit to light work")
    if sys_state["open_loops"] > 3:
        constraints.append(f"{sys_state['open_loops']} open loops — high context load")
    if sys_state["queue_available"] == 0:
        constraints.append("Queue at capacity — wait for current job to complete")
    if not constraints:
        constraints.append("No active constraints — system clear for execution")
    return constraints


def derive_risks(goal: str, sys_state: dict) -> list[str]:
    risks: list[str] = []
    if sys_state["mode"] not in ("BUILD", "COMPOUND", "SCALE"):
        risks.append(f"Mode ({sys_state['mode']}) may block execution")
    if sys_state["open_loops"] > 5:
        risks.append("High open loop count — governance may deny new work")
    risks.append("Scope creep — define done criteria before starting")
    risks.append("Context loss — brief provides recovery point if session drops")
    return risks


def build_scope(goal: str, context: str) -> dict:
    return {
        "in": [goal, "Use existing infrastructure", "Produce concrete deliverable"],
        "out": ["Architecture changes", "New service creation", "Scope expansion"],
    }


def build_resources(sys_state: dict) -> list[str]:
    resources = [
        f"Atlas pipeline (mode: {sys_state['mode']})",
        f"Work queue ({sys_state['queue_available']} slots available)",
    ]
    if sys_state["build_allowed"]:
        resources.append("Build execution permitted")
    resources.append("Profiles: @WORK, @BUILD, @CLEAN, @SNAPSHOT, @BRIEF")
    return resources


# ---------------------------------------------------------------------------
# Template-based action generation
# ---------------------------------------------------------------------------

# Each template: (pattern_regex, action_generator_function)
# Generator receives (goal, context, match) and returns list of action dicts

def _actions_launch_service(goal: str, context: str, match: re.Match) -> list[dict]:
    """Template: launch/start/run <something> on port <N>"""
    service = match.group(1).strip()
    port = match.group(2)
    return [
        {
            "id": "a1",
            "step": 1,
            "type": "command",
            "executor": "shell",
            "action": f"Verify port {port} is available",
            "payload": f"netstat -ano | findstr :{port} && echo PORT_IN_USE && exit 1 || echo PORT_AVAILABLE",
            "owner": "system",
            "risk": "low",
        },
        {
            "id": "a2",
            "step": 2,
            "type": "command",
            "executor": "shell",
            "action": f"Install dependencies for {service}",
            "payload": "pip install -r requirements.txt",
            "owner": "system",
            "risk": "medium",
        },
        {
            "id": "a3",
            "step": 3,
            "type": "command",
            "executor": "shell",
            "action": f"Start {service} on port {port}",
            "payload": f"python -m uvicorn app:app --host 127.0.0.1 --port {port}",
            "owner": "system",
            "risk": "medium",
        },
        {
            "id": "a4",
            "step": 4,
            "type": "command",
            "executor": "shell",
            "action": f"Verify {service} health",
            "payload": f"curl -s http://localhost:{port}/health",
            "owner": "system",
            "risk": "low",
        },
    ]


def _actions_build_project(goal: str, context: str, match: re.Match) -> list[dict]:
    """Template: build/compile <project>"""
    project = match.group(1).strip()
    return [
        {
            "id": "a1",
            "step": 1,
            "type": "command",
            "executor": "shell",
            "action": f"Clean previous build artifacts for {project}",
            "payload": "npm run clean || true",
            "owner": "system",
            "risk": "low",
        },
        {
            "step": 2,
            "type": "command",
            "executor": "shell",
            "action": "Install dependencies",
            "payload": "npm install",
            "owner": "system",
            "risk": "low",
        },
        {
            "step": 3,
            "type": "command",
            "executor": "shell",
            "action": f"Build {project}",
            "payload": "npm run build",
            "owner": "system",
            "risk": "medium",
        },
        {
            "step": 4,
            "type": "command",
            "executor": "shell",
            "action": "Run tests",
            "payload": "npm test",
            "owner": "system",
            "risk": "medium",
        },
    ]


def _actions_deploy(goal: str, context: str, match: re.Match) -> list[dict]:
    """Template: deploy <target>"""
    target = match.group(1).strip()
    return [
        {
            "step": 1,
            "type": "command",
            "executor": "shell",
            "action": f"Build {target} for production",
            "payload": "npm run build",
            "owner": "system",
            "risk": "medium",
        },
        {
            "step": 2,
            "type": "command",
            "executor": "shell",
            "action": "Run pre-deploy checks",
            "payload": "npm test && npm run lint",
            "owner": "system",
            "risk": "medium",
        },
        {
            "step": 3,
            "type": "command",
            "executor": "shell",
            "action": f"Deploy {target}",
            "payload": "npm run deploy",
            "owner": "operator",
            "risk": "high",
        },
    ]


def _actions_close_loop(goal: str, context: str, match: re.Match) -> list[dict]:
    """Template: close loop / finish / complete <task>"""
    task = match.group(1).strip() if match.group(1) else goal
    return [
        {
            "step": 1,
            "type": "api_call",
            "executor": "http",
            "action": f"Mark task done: {task}",
            "payload": {
                "method": "POST",
                "url": "http://localhost:3001/api/law/close_loop",
                "body": {"task_title": task},
            },
            "owner": "system",
            "risk": "low",
        },
        {
            "step": 2,
            "type": "command",
            "executor": "shell",
            "action": "Refresh governance state",
            "payload": "curl -s -X POST http://localhost:3001/api/daemon/run -H \"Content-Type: application/json\" -d \"{\\\"job\\\":\\\"refresh\\\"}\"",
            "owner": "system",
            "risk": "low",
        },
    ]


def _actions_clean(goal: str, context: str, match: re.Match) -> list[dict]:
    """Template: clean / clear / reset"""
    return [
        {
            "step": 1,
            "type": "atlas_cmd",
            "executor": "work_queue",
            "action": "Run system cleanup",
            "payload": {"cmd": "@CLEAN"},
            "owner": "system",
            "risk": "low",
        },
        {
            "step": 2,
            "type": "atlas_cmd",
            "executor": "work_queue",
            "action": "Take system snapshot",
            "payload": {"cmd": "@SNAPSHOT"},
            "owner": "system",
            "risk": "low",
        },
    ]


# Pattern registry: (regex, handler). Order matters — first match wins.
TEMPLATES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"(?:launch|start|run|spin up)\s+(.+?)\s+(?:on\s+)?port\s+(\d+)", re.I), _actions_launch_service),
    (re.compile(r"(?:build|compile)\s+(.+)", re.I), _actions_build_project),
    (re.compile(r"(?:deploy)\s+(.+)", re.I), _actions_deploy),
    (re.compile(r"(?:close|finish|complete|wrap)\s+(?:loop\s+)?(.+)?", re.I), _actions_close_loop),
    (re.compile(r"(?:clean|clear|reset|hygiene)", re.I), _actions_clean),
]


def match_template(goal: str, context: str) -> Optional[list[dict]]:
    """Try to match goal against known templates. Returns actions or None."""
    for pattern, handler in TEMPLATES:
        m = pattern.search(goal)
        if m:
            return handler(goal, context, m)
    return None


# ---------------------------------------------------------------------------
# Claude API fallback
# ---------------------------------------------------------------------------

CLAUDE_PROMPT = """You are a deterministic execution planner for a governed system called Atlas.

Convert this goal into structured, machine-executable actions.

Rules:
- No vague language
- Each action must include: step (int), type (command|api_call|file_write|atlas_cmd), executor (shell|http|fs|work_queue), action (description), payload (exact command/data), owner (system|operator), risk (low|medium|high)
- Output a JSON array of actions ONLY — no explanations, no markdown
- Maximum 5 actions
- Prefer shell commands on Windows (cmd.exe)

System state:
{state}

Goal: {goal}

Context: {context}
"""


def call_claude(goal: str, context: str, sys_state: dict) -> Optional[list[dict]]:
    """Call Claude API to generate executable actions. Returns actions or None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("[BRIEF] No ANTHROPIC_API_KEY — skipping Claude fallback", file=sys.stderr)
        return None

    prompt = CLAUDE_PROMPT.format(
        goal=goal,
        context=context or "none",
        state=json.dumps(sys_state, indent=2),
    )

    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("content", [{}])[0].get("text", "")

            # Extract JSON from response (may have markdown wrapping)
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            actions = json.loads(text)
            if isinstance(actions, list):
                return actions
            if isinstance(actions, dict) and "actions" in actions:
                return actions["actions"]
            return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[BRIEF] Claude fallback failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Generic fallback (no AI, no template match)
# ---------------------------------------------------------------------------

def generic_actions(goal: str, context: str) -> list[dict]:
    """Last-resort generic actions when no template matches and Claude is unavailable."""
    return [
        {
            "step": 1,
            "type": "command",
            "executor": "shell",
            "action": f"Define done criteria for: {goal}",
            "payload": f"echo \"DONE WHEN: {goal} is verified working\"",
            "owner": "operator",
            "risk": "low",
        },
        {
            "step": 2,
            "type": "command",
            "executor": "shell",
            "action": "Check system readiness",
            "payload": "curl -s http://localhost:3001/api/health && curl -s http://localhost:3008/health",
            "owner": "system",
            "risk": "low",
        },
        {
            "step": 3,
            "type": "command",
            "executor": "shell",
            "action": f"Execute: {goal}",
            "payload": f"echo \"MANUAL: {goal}\"",
            "owner": "operator",
            "risk": "medium",
        },
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    goal = os.environ.get("BRIEF_GOAL", "").strip()
    context = os.environ.get("BRIEF_CONTEXT", "").strip()
    output_dir = os.environ.get("BRIEF_OUTPUT_DIR", os.path.join(os.getcwd(), "output"))

    if not goal:
        print("ERROR: BRIEF_GOAL environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Load state
    temp = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
    state = load_json(os.path.join(temp, "atlas_state.json"))
    work = load_json(os.path.join(temp, "atlas_work.json"))
    snapshot = load_json(os.path.join(output_dir, "atlas_snapshot.json"))

    sys_state = extract_system_state(state, work)
    now = datetime.now(timezone.utc)

    # Generate actions: template → Claude → generic
    action_source = "template"
    actions = match_template(goal, context)

    if actions is None:
        action_source = "claude"
        actions = call_claude(goal, context, sys_state)

    if actions is None:
        action_source = "generic"
        actions = generic_actions(goal, context)

    # Build brief
    brief = {
        "timestamp": now.isoformat(),
        "objective": goal,
        "context": context or None,
        "action_source": action_source,
        "system_state": sys_state,
        "scope": build_scope(goal, context),
        "actions": actions,
        "risks": derive_risks(goal, sys_state),
        "resources": build_resources(sys_state),
        "constraints": derive_constraints(sys_state),
        "last_snapshot": snapshot.get("timestamp") if snapshot else None,
    }

    # Write output
    os.makedirs(output_dir, exist_ok=True)
    slug = slugify(goal)
    filename = f"brief_{now.strftime('%Y%m%d_%H%M%S')}_{slug}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2)

    print(json.dumps(brief, indent=2))
    print(f"\nBrief written to: {filepath}", file=sys.stderr)
    print(f"Action source: {action_source}", file=sys.stderr)


if __name__ == "__main__":
    main()
