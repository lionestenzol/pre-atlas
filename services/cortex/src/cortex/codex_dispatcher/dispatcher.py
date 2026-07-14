"""Codex dispatcher — classify a user intent and run `codex exec`.

Originally lived at services/optogon/src/optogon/action_handlers.py
(classify_codex_intent + run_codex_exec). Moved here so Optogon can request
Codex execution over HTTP per doctrine/02_ROSETTA_STONE.md instead of calling
the Codex CLI directly.

The classification regex table is intentionally preserved verbatim from the
original Optogon code — it encodes Bruke's phrasing patterns and is the
load-bearing knowledge of which informal triggers map to which Codex skill.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("cortex.codex_dispatcher")


class DispatchError(Exception):
    """Raised when dispatch input is invalid (e.g. empty user_intent)."""


# Repo root: services/cortex/src/cortex/codex_dispatcher/dispatcher.py
# parents[5] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]


# Intent vocabulary: regex patterns -> (skill, sandbox_mode, prompt_framing_hint)
# Keep aligned with ~/.claude/skills/codex-delegate/SKILL.md Step 0 table.
# Lowercase, matches against user_intent.lower(). Order matters: first match wins.
_CODEX_INTENT_RULES: list[tuple[str, str, str, str]] = [
    # (regex, skill, sandbox, framing_hint)
    (r"\b(yeet|open (a )?pr|make (a )?pr|push (it|the change)|merge (this|it)|ship the diff)\b",
     "yeet", "workspace-write", "Stage all changes, commit, push, and open a draft PR. Use the description provided."),
    (r"\bci\b.{0,15}\b(broke|broken|failing|red|bad|busted|down|hosed)\b|\b(tests? (are )?(red|failing|broken)|actions failing|checks (are )?(red|bad|failing)|pr won.?t merge|what.?s failing|workflow failing)\b",
     "gh-fix-ci", "read-only", "Use gh to inspect failing checks and logs, summarize failure context, and draft a fix plan. Do NOT implement without approval."),
    (r"\b(address the comments?|fix the review|handle (the )?feedback|review comments)\b",
     "gh-address-comments", "workspace-write", "Address review/issue comments on the open GitHub PR for the current branch using gh."),
    (r"\b(deploy|ship it|throw (it|this) up|put (it|this) (online|live)|go live|host this|publish (it|this))\b.*\b(vercel|netlify|render|cloudflare)?\b",
     "vercel-deploy", "workspace-write", "Deploy this app to the named platform and report the production URL. If platform unspecified, prefer Vercel."),
    (r"\b(transcrib|what.?s in this audio|who said what|recording|diariz)\w*",
     "transcribe", "read-only", "Transcribe the audio file referenced. Output a markdown file with named speakers if diarization is requested."),
    (r"\b(narrate|tts|text.to.speech|voice ?over|read this aloud|make it speak)\w*",
     "speech", "workspace-write", "Generate narrated audio from the supplied text using the OpenAI Audio API."),
    (r"\b(sora|generate (a )?(video|short|clip)|make (a )?(video|clip)|i want a video)\b",
     "sora", "workspace-write", "Generate or edit a Sora video per the user's description."),
    (r"\bfigma\b|\b(implement (the )?(design|mock)|translate (the )?design|build this from figma)\b",
     "figma-implement-design", "workspace-write", "Pull the Figma design context and translate node(s) into production code with 1:1 visual fidelity."),
    (r"\b(threat model|any vulns|where (are )?we exposed|attacker|abuse path|is this safe)\b",
     "security-threat-model", "read-only", "Run a repo-grounded threat model: enumerate trust boundaries, assets, attacker capabilities, abuse paths, mitigations. Write a concise Markdown threat model."),
    (r"\b(bus factor|who owns (this|the)|sensitive code ownership|single point of failure)\b",
     "security-ownership-map", "read-only", "Build a security ownership topology from git history. Compute bus factor and sensitive-code ownership."),
    (r"\b(security review|secure(.by.default)?|look for security|is this secure)\b",
     "security-best-practices", "read-only", "Perform a language-specific security best-practices review (py/ts/go) and suggest improvements."),
    (r"\b(wrap (this|the) api|build (a |me a )?cli|cli from (this )?spec|make a tool for)\b",
     "cli-creator", "workspace-write", "Build a composable CLI from the supplied API/OpenAPI spec or examples."),
    (r"\b(qa this|test the ui|click through|drive (this )?with playwright|electron qa)\b",
     "playwright-interactive", "workspace-write", "Drive the app in a persistent Playwright browser/Electron session for iterative UI debugging."),
    (r"\b(second opinion|fresh eyes|sanity check|what does codex think|have codex review)\b",
     "__review__", "read-only", "Provide a fresh-frame second opinion. Do not modify files."),
    (r"\b(sentry|production errors?|crash reports?)\b",
     "sentry", "read-only", "Pull recent Sentry events / health data for the named project (read-only)."),
    (r"\blinear\b",
     "linear", "workspace-write", "Read or update the named Linear issue/project per the user's instruction."),
    (r"\bnotion\b",
     "notion-knowledge-capture", "workspace-write", "Capture or update the named Notion page per the user's instruction."),
    (r"\b(winui|wpf|windows app sdk|asp\.?net core|aspnet)\b",
     "aspnet-core", "workspace-write", "Bootstrap or extend the named Windows app framework project per the user's instruction."),
]

# Domains where anthropic-skills:* should win - never delegate these to Codex
_ANTHROPIC_OVERLAP = re.compile(
    r"\b(docx|word doc|word document|pdf( report| file)?|pptx|powerpoint|deck|presentation|"
    r"xlsx|\.csv|spreadsheet|"
    r"touchdesigner|\.tox|\.toe|"
    r"mcp server|fastmcp)\b",
    re.IGNORECASE,
)


def _resolve_path(raw: str) -> Path:
    """Resolve a path. Relative paths are resolved against repo root."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()
    else:
        p = p.resolve()
    return p


def _resolve_codex_executable() -> str:
    """Return the executable string for `codex`. Handles Windows .cmd shims."""
    # Windows: `codex` is a .cmd shim in npm global. shutil.which finds it if .cmd is in PATHEXT.
    p = shutil.which("codex.cmd") or shutil.which("codex")
    return p or "codex"


def classify_intent(user_intent: str) -> dict[str, Any]:
    """Map user_intent to a Codex skill + sandbox + framing.

    Pure regex matching; no side effects. Original casing preserved on
    user_intent_raw so downstream prompt assembly does not mangle paths,
    URLs, identifiers.
    """
    intent_original = str(user_intent).strip()
    intent = intent_original.lower()
    if not intent:
        raise DispatchError("classify_intent: user_intent is empty")

    if _ANTHROPIC_OVERLAP.search(intent):
        return {
            "target_skill": None,
            "sandbox": "read-only",
            "framing": "",
            "should_delegate": False,
            "delegate_reason": "anthropic_overlap",
            "user_intent_normalized": intent,
            "user_intent_raw": intent_original,
        }

    for pattern, skill, sandbox, framing in _CODEX_INTENT_RULES:
        if re.search(pattern, intent):
            return {
                "target_skill": skill,
                "sandbox": sandbox,
                "framing": framing,
                "should_delegate": True,
                "delegate_reason": "matched_intent",
                "user_intent_normalized": intent,
                "user_intent_raw": intent_original,
            }

    return {
        "target_skill": None,
        "sandbox": "read-only",
        "framing": "",
        "should_delegate": False,
        "delegate_reason": "no_match",
        "user_intent_normalized": intent,
        "user_intent_raw": intent_original,
    }


def run_codex_exec(
    framing: str,
    sandbox: str,
    skill: str,
    user_intent_raw: str,
    cwd: Optional[str] = None,
    output_schema_path: Optional[str] = None,
) -> dict[str, Any]:
    """Invoke `codex exec` with the supplied framing.

    Sandbox safety:
    - Honors sandbox ('read-only' | 'workspace-write')
    - Always passes --ephemeral and --skip-git-repo-check
    - 5 min timeout; non-zero exit returns codex_success=False with stderr

    Optional structured handoff via output_schema_path: passes
    --output-schema and -o, parses the result file into 'parsed_output'.
    """
    if not framing:
        raise DispatchError("run_codex_exec: framing is empty (classify_intent must run first)")

    cwd_resolved = str(_resolve_path(cwd)) if cwd else str(_REPO_ROOT)

    prompt_lines = [framing]
    if skill and skill != "__review__":
        prompt_lines.append(f"(Use the {skill} skill.)")
    prompt_lines.append(f"User request: {user_intent_raw}")
    if output_schema_path:
        prompt_lines.append("Reply ONLY with JSON matching the supplied output schema.")
    prompt = "\n".join(prompt_lines)

    codex_bin = _resolve_codex_executable()
    cmd: list[str] = [
        codex_bin, "exec",
        "-s", sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", cwd_resolved,
    ]
    if sandbox == "workspace-write":
        # Codex 0.118: --full-auto replaces the old -a on-request pair.
        cmd += ["--full-auto"]

    output_file: Optional[Path] = None
    schema_path: Optional[Path] = None
    if output_schema_path:
        schema_path = _resolve_path(str(output_schema_path))
        if not schema_path.exists():
            raise DispatchError(f"run_codex_exec: schema not found: {schema_path}")
        output_file = Path(tempfile.gettempdir()) / f"cortex_codex_{os.getpid()}_{id(prompt)}.json"
        cmd += ["--output-schema", str(schema_path), "-o", str(output_file)]

    cmd.append(prompt)

    log.info(
        "run_codex_exec: skill=%s sandbox=%s cwd=%s schema=%s",
        skill, sandbox, cwd_resolved, schema_path,
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            shell=False,
        )
    except FileNotFoundError as e:
        return {
            "codex_success": False,
            "codex_output": "",
            "codex_stderr": f"codex executable not found: {e}",
            "exit_code": None,
            "skill": skill,
            "sandbox": sandbox,
        }
    except subprocess.TimeoutExpired:
        return {
            "codex_success": False,
            "codex_output": "",
            "codex_stderr": "timeout after 300s",
            "exit_code": None,
            "skill": skill,
            "sandbox": sandbox,
        }

    result: dict[str, Any] = {
        "codex_success": proc.returncode == 0,
        "codex_output": proc.stdout,
        "codex_stderr": proc.stderr,
        "exit_code": proc.returncode,
        "skill": skill,
        "sandbox": sandbox,
    }

    if output_file is not None:
        try:
            if output_file.exists():
                import json as _json
                parsed = _json.loads(output_file.read_text(encoding="utf-8"))
                result["parsed_output"] = parsed
                result["output_file"] = str(output_file)
                if schema_path is not None:
                    schema_obj = _json.loads(schema_path.read_text(encoding="utf-8"))
                    from jsonschema import Draft7Validator
                    errs = list(Draft7Validator(schema_obj).iter_errors(parsed))
                    result["schema_valid"] = len(errs) == 0
                    if errs:
                        result["schema_errors"] = [str(e.message)[:200] for e in errs[:5]]
            else:
                result["parsed_output"] = None
                result["schema_valid"] = False
                result["schema_errors"] = ["output file not written by codex"]
        except Exception as e:  # noqa: BLE001
            result["parsed_output"] = None
            result["schema_valid"] = False
            result["schema_errors"] = [f"parse error: {e}"]

    return result


def dispatch_codex(
    user_intent: str,
    cwd: Optional[str] = None,
    output_schema_path: Optional[str] = None,
) -> dict[str, Any]:
    """End-to-end: classify the intent, then exec if delegate-eligible.

    Returns a single dict combining classification + execution outputs.
    When should_delegate=False (anthropic_overlap or no_match), execution
    is skipped and codex_* fields are absent.
    """
    classification = classify_intent(user_intent)

    if not classification["should_delegate"]:
        return classification

    exec_result = run_codex_exec(
        framing=classification["framing"],
        sandbox=classification["sandbox"],
        skill=classification["target_skill"] or "",
        user_intent_raw=classification["user_intent_raw"],
        cwd=cwd,
        output_schema_path=output_schema_path,
    )
    return {**classification, **exec_result}
