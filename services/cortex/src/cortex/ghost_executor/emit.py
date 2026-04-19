"""emit_build_output(result) -> BuildOutput.

Per doctrine/02_ROSETTA_STONE.md Contract 4 (response side). Wraps the
raw execution result from Claude Code into a BuildOutput.v1 envelope
ready for Atlas / InPACT.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from ._validator import validate, ContractError


class BuildOutputInvalidError(ValueError):
    def __init__(self, details: list[str]) -> None:
        self.details = details
        super().__init__("BuildOutput failed validation: " + "; ".join(details))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit_build_output(
    task_prompt_id: str,
    status: str,
    summary: str,
    artifacts: list[dict[str, Any]] | None = None,
    issues_encountered: list[str] | None = None,
    follow_on_tasks: list[str] | None = None,
    tokens_used: int = 0,
) -> dict[str, Any]:
    """Build a BuildOutput.v1 payload.

    Args:
        task_prompt_id: ID of the originating TaskPrompt
        status: one of 'success' | 'partial' | 'failed'
        summary: human-readable summary (InPACT displays this)
        artifacts: list of {type, path?, description}
        issues_encountered: optional string list
        follow_on_tasks: optional string list (feeds back into Atlas queue)
        tokens_used: LLM tokens consumed (if known)

    Returns:
        BuildOutput.v1 dict, validated.

    Raises:
        BuildOutputInvalidError: if the generated payload does not validate.
    """
    payload = {
        "schema_version": "1.0",
        "task_prompt_id": task_prompt_id,
        "completed_at": _now(),
        "status": status,
        "artifacts": artifacts or [],
        "summary": summary,
        "issues_encountered": issues_encountered or [],
        "follow_on_tasks": follow_on_tasks or [],
        "tokens_used": max(0, int(tokens_used)),
    }
    try:
        validate(payload, "BuildOutput")
    except ContractError as e:
        raise BuildOutputInvalidError(e.errors) from e
    return payload
