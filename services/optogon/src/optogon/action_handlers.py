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

# --- Codex delegation handlers (path: delegate_to_codex) -------------------

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


@register("classify_codex_intent")
def classify_codex_intent(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Map user_intent to a Codex skill + sandbox + framing.

    Outputs (merged into context.system):
        target_skill: str | None
        sandbox: 'read-only' | 'workspace-write'
        framing: str
        should_delegate: bool
        delegate_reason: str (when should_delegate is False)
    """
    ctx = session_state["context"]
    intent_raw = (
        ctx["confirmed"].get("user_intent")
        or ctx["user"].get("user_intent")
        or ctx["system"].get("user_intent")
        or ""
    )
    intent_original = str(intent_raw).strip()
    intent = intent_original.lower()  # for matching only, NOT for downstream prompting
    if not intent:
        raise ActionError("classify_codex_intent: no user_intent in context")

    # Anthropic overlap: stay with Claude
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

    # Match against intent rules
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

    # No match: don't delegate; let Claude handle
    return {
        "target_skill": None,
        "sandbox": "read-only",
        "framing": "",
        "should_delegate": False,
        "delegate_reason": "no_match",
        "user_intent_normalized": intent,
        "user_intent_raw": intent_original,
    }


def _resolve_codex_executable() -> str:
    """Return the executable string for `codex`. Handles Windows .cmd shims."""
    import shutil
    # Windows: `codex` is a .cmd shim in npm global. shutil.which finds it if .cmd is in PATHEXT.
    p = shutil.which("codex.cmd") or shutil.which("codex")
    return p or "codex"


@register("run_codex_exec")
def run_codex_exec(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Invoke `codex exec` with the framing chosen by classify_codex_intent.

    Sandbox safety:
    - Honors system.sandbox ('read-only' | 'workspace-write')
    - Always passes --ephemeral and --skip-git-repo-check
    - cwd defaults to system.cwd or REPO_ROOT
    - 5 min timeout; non-zero exit returns codex_success=False with stderr

    Optional structured handoff:
    - If context.output_schema_path is set, passes --output-schema and -o
      and parses the result file into 'parsed_output'.
    """
    ctx = session_state["context"]
    framing = ctx["system"].get("framing") or ""
    sandbox = ctx["system"].get("sandbox") or "read-only"
    skill = ctx["system"].get("target_skill") or ""
    cwd_raw = ctx["confirmed"].get("cwd") or ctx["user"].get("cwd") or ctx["system"].get("cwd")
    # Use ORIGINAL casing for the actual prompt; lowercased version is for classifier debug only
    user_intent = (
        ctx["system"].get("user_intent_raw")
        or ctx["confirmed"].get("user_intent")
        or ctx["user"].get("user_intent")
        or ctx["system"].get("user_intent_normalized")
        or ""
    )
    schema_path_raw = (
        ctx["confirmed"].get("output_schema_path")
        or ctx["user"].get("output_schema_path")
        or ctx["system"].get("output_schema_path")
    )

    if not framing:
        raise ActionError("run_codex_exec: no framing in context (classify must run first)")

    cwd = str(_resolve_path(str(cwd_raw))) if cwd_raw else str(REPO_ROOT)

    # Build the prompt: framing first, then user's words for trigger-matching
    prompt_lines = [framing]
    if skill and skill != "__review__":
        prompt_lines.append(f"(Use the {skill} skill.)")
    prompt_lines.append(f"User request: {user_intent}")
    if schema_path_raw:
        prompt_lines.append("Reply ONLY with JSON matching the supplied output schema.")
    prompt = "\n".join(prompt_lines)

    codex_bin = _resolve_codex_executable()
    cmd: list[str] = [
        codex_bin, "exec",
        "-s", sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", cwd,
    ]
    if sandbox == "workspace-write":
        # add --full-auto's other half (-a on-request); never combine with -s read-only
        cmd += ["-a", "on-request"]

    # Optional structured-output mode
    output_file: Path | None = None
    schema_path: Path | None = None
    if schema_path_raw:
        schema_path = _resolve_path(str(schema_path_raw))
        if not schema_path.exists():
            raise ActionError(f"run_codex_exec: schema not found: {schema_path}")
        # write -o file alongside session data (cleanup is the caller's problem)
        import tempfile
        output_file = Path(tempfile.gettempdir()) / f"optogon_codex_{os.getpid()}_{id(action)}.json"
        cmd += ["--output-schema", str(schema_path), "-o", str(output_file)]

    cmd.append(prompt)

    log.info("run_codex_exec: skill=%s sandbox=%s cwd=%s schema=%s",
             skill, sandbox, cwd, schema_path)

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

    result: HandlerResult = {
        "codex_success": proc.returncode == 0,
        "codex_output": proc.stdout,
        "codex_stderr": proc.stderr,
        "exit_code": proc.returncode,
        "skill": skill,
        "sandbox": sandbox,
    }

    # If structured output requested, parse the -o file (written at exec exit)
    if output_file is not None:
        try:
            if output_file.exists():
                import json as _json
                parsed = _json.loads(output_file.read_text(encoding="utf-8"))
                result["parsed_output"] = parsed
                result["output_file"] = str(output_file)
                # Validate against schema
                if schema_path is not None:
                    import json as _json2
                    from jsonschema import Draft7Validator
                    schema_obj = _json2.loads(schema_path.read_text(encoding="utf-8"))
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
