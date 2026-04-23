"""Bridge: Optogon triage proposal -> Directive for Cortex.

Takes a proposed fs action (rotate_and_delete, move_to_archive, etc.)
and emits a Directive.v1 targeted at Cortex's Ghost Executor. In
DRY-RUN mode (default) the directive is only logged to
cortex_directives_log.json; no POST leaves the machine.

Flip CORTEX_BRIDGE_APPLY=1 to actually POST to Cortex.

Keeps the blast radius tiny on day 1: scope is an audit trail of
"what Atlas would ask Cortex to do", not Cortex actually doing it.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
REPO_ROOT = BASE.parent.parent  # services/cognitive-sensor -> Pre Atlas
LOG_PATH = BASE / "cortex_directives_log.json"
PROPOSALS_PATH = BASE / "proposals.json"
CORTEX_URL = os.environ.get("CORTEX_URL", "http://localhost:3009")
APPLY = os.environ.get("CORTEX_BRIDGE_APPLY", "0") == "1"
RUN_PROPOSAL = os.environ.get("CORTEX_BRIDGE_RUN_PROPOSAL", "0") == "1"


def _within_repo(path_str: str) -> bool:
    """True if path is inside the Pre Atlas repo root."""
    if not path_str:
        return False
    try:
        p = Path(path_str).expanduser().resolve()
        p.relative_to(REPO_ROOT.resolve())
        return True
    except (ValueError, OSError):
        return False


def _append_proposal(directive: dict[str, Any], evidence: str) -> str:
    """Convert a Directive into a proposal entry and append to proposals.json.

    Returns the proposal_id (also matches directive.id for traceability).
    """
    proposal_id = directive["id"]
    proposal = {
        "proposal_id": proposal_id,
        "dtype": directive["task"]["type"],
        "domain": "filesystem",
        "rationale": directive["task"]["description"],
        "suggested_action": directive["task"]["label"],
        "relevant_files": directive["context_bundle"]["relevant_files"],
        "status": "approved" if RUN_PROPOSAL else "pending",
        "created_at": directive["issued_at"],
        "source": "atlas.triage_fs_loop",
        "evidence": evidence,
    }
    existing: list[dict] = []
    if PROPOSALS_PATH.exists():
        try:
            existing = json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(proposal)
    atomic_write_json(PROPOSALS_PATH, existing)
    return proposal_id


def _spawn_runner(proposal_id: str) -> bool:
    """Detached subprocess: python proposal_runner.py <id>. Returns True on spawn."""
    import subprocess
    runner = BASE / "proposal_runner.py"
    if not runner.exists():
        logger.warning("proposal_runner.py not found; skipping spawn")
        return False
    try:
        subprocess.Popen(
            [os.sys.executable, str(runner), proposal_id],
            cwd=str(BASE),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        return True
    except OSError as exc:
        logger.warning("failed to spawn proposal_runner: %s", exc)
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_directive(loop_id: str, title: str, evidence: str, proposed_action: str, rationale: str, confidence: float) -> dict[str, Any]:
    """Build a Directive.v1 for the proposed action. Shape per contracts/schemas/Directive.v1.json."""
    priority_tier = "high" if confidence >= 0.85 else "medium"
    return {
        "schema_version": "1.0",
        "id": f"dir_{uuid.uuid4().hex[:12]}",
        "issued_at": _now_iso(),
        "priority_tier": priority_tier,
        "leverage_score": float(max(0.0, min(1.0, confidence))),
        "task": {
            "id": f"task_{loop_id}",
            "label": f"fs triage: {proposed_action}",
            "description": f"{rationale} (target: {evidence})",
            "type": "configure",
            "estimated_complexity": "simple",
            "success_criteria": [
                f"{proposed_action} completed safely",
                "no unintended side effects",
            ],
            "constraints": [
                "dry-run unless user approves",
                "never delete outside listed path",
            ],
        },
        "context_bundle": {
            "project_id": "pre-atlas",
            "relevant_files": [evidence] if evidence else [],
            "prior_attempts": [],
        },
        "execution": {
            "target_agent": "claude_code",
            "autonomy_level": "approval_required",
            "timeout_seconds": 600,
            "fallback": "escalate_to_human",
        },
        "interrupt_policy": {
            "interruptible": True,
            "interrupt_threshold": "high_and_above",
            "resume_on_interrupt": False,
        },
    }


def _log_append(directive: dict[str, Any], applied: bool, note: str = "") -> None:
    log = {"directives": []}
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    entries = log.setdefault("directives", [])
    entries.append({
        "directive_id": directive["id"],
        "issued_at": directive["issued_at"],
        "task_label": directive["task"]["label"],
        "description": directive["task"]["description"],
        "relevant_files": directive["context_bundle"]["relevant_files"],
        "confidence": directive["leverage_score"],
        "applied": applied,
        "note": note,
    })
    log["directives"] = entries[-200:]
    atomic_write_json(LOG_PATH, log)


def emit(loop_id: str, title: str, evidence: str, proposed_action: str, rationale: str, confidence: float) -> dict[str, Any]:
    """Build and route a Directive. Returns a summary dict.

    Routing rules:
    - Evidence outside the Pre Atlas repo: log only, never execute. The
      proposal_runner creates branches in THIS repo and would have no
      safe way to act on an external path.
    - Evidence inside the repo + APPLY=0: dry-run, log only.
    - Evidence inside the repo + APPLY=1: append to proposals.json.
    - APPLY=1 + RUN_PROPOSAL=1: also spawn proposal_runner.
    """
    directive = build_directive(loop_id, title, evidence, proposed_action, rationale, confidence)

    if not _within_repo(evidence):
        _log_append(directive, applied=False, note="out-of-repo: user action required")
        return {"ok": True, "applied": False, "directive_id": directive["id"], "mode": "out-of-repo"}

    if not APPLY:
        _log_append(directive, applied=False, note="dry-run (set CORTEX_BRIDGE_APPLY=1 to queue proposal)")
        return {"ok": True, "applied": False, "directive_id": directive["id"], "mode": "dry-run"}

    proposal_id = _append_proposal(directive, evidence)
    if RUN_PROPOSAL:
        spawned = _spawn_runner(proposal_id)
        note = "proposal queued and runner spawned" if spawned else "proposal queued; runner failed to spawn"
        _log_append(directive, applied=spawned, note=note)
        return {"ok": True, "applied": spawned, "directive_id": directive["id"], "mode": "run_proposal"}

    _log_append(directive, applied=False, note="proposal queued (set CORTEX_BRIDGE_RUN_PROPOSAL=1 to auto-run)")
    return {"ok": True, "applied": False, "directive_id": directive["id"], "mode": "queued"}


if __name__ == "__main__":
    # self-test: dry-run a sample directive
    result = emit(
        loop_id="fs-test-999",
        title="Test fs loop",
        evidence=r"C:\Users\bruke\tmp\.env",
        proposed_action="rotate_and_delete",
        rationale="self-test",
        confidence=0.9,
    )
    print(json.dumps(result, indent=2))
