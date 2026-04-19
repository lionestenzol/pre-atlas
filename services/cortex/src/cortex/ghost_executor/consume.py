"""consume_directive(Directive) -> TaskPrompt.

Per doctrine/02_ROSETTA_STONE.md Contract 4 (request side). Validates the
incoming Directive and translates it into a TaskPrompt ready for Claude Code.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from ._validator import validate, ContractError


class DirectiveInvalidError(ValueError):
    """Raised when the Directive payload fails schema validation."""

    def __init__(self, details: list[str]) -> None:
        self.details = details
        super().__init__("Directive failed validation: " + "; ".join(details))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def consume_directive(directive: dict[str, Any], working_directory: str = ".") -> dict[str, Any]:
    """Consume a Directive and return a TaskPrompt.

    Args:
        directive: Directive.v1 payload (as dict)
        working_directory: resolved repo path for environment.working_directory

    Returns:
        TaskPrompt.v1 dict, validated against schema.

    Raises:
        DirectiveInvalidError: if the input Directive is invalid.
        ContractError: if the generated TaskPrompt is invalid (should not happen).
    """
    try:
        validate(directive, "Directive")
    except ContractError as e:
        raise DirectiveInvalidError(e.errors) from e

    task = directive.get("task") or {}
    context_bundle = directive.get("context_bundle") or {}
    execution = directive.get("execution") or {}
    prior_attempts_src = context_bundle.get("prior_attempts") or []

    task_prompt = {
        "schema_version": "1.0",
        "id": f"tp_{uuid.uuid4().hex[:12]}",
        "directive_id": directive["id"],
        "issued_at": _now(),
        "instruction": {
            "objective": task.get("label") or task.get("description") or "Execute directive",
            "context": task.get("description") or "",
            "constraints": task.get("constraints") or [],
            "success_criteria": task.get("success_criteria") or ["Complete the task"],
            "failure_criteria": _derive_failure_criteria(task),
        },
        "environment": {
            "working_directory": working_directory,
            "relevant_files": context_bundle.get("relevant_files") or [],
            "available_tools": _default_tools_for(execution.get("target_agent")),
            "infrastructure_context": None,
        },
        "prior_attempts": [
            {
                "summary": attempt.get("outcome", "prior attempt"),
                "what_failed": attempt.get("outcome", ""),
                "what_to_avoid": ", ".join(attempt.get("lessons") or []),
            }
            for attempt in prior_attempts_src
        ],
        "output_spec": {
            "expected_artifacts": ["build output per success_criteria"],
            "format": "structured",
            "location": working_directory,
        },
        "constraints": {
            "max_tokens": 8000,
            "timeout_seconds": execution.get("timeout_seconds") or 1800,
            "do_not_modify": [],
            "require_tests": False,
        },
    }

    # Self-check: we control the shape, but validate to catch regressions.
    validate(task_prompt, "TaskPrompt")
    return task_prompt


def _derive_failure_criteria(task: dict[str, Any]) -> list[str]:
    """Failure criteria default: negation of success + contract rule-of-thumb."""
    successes = task.get("success_criteria") or []
    criteria: list[str] = [f"Did not satisfy: {s}" for s in successes[:3]]
    criteria.append("Any error exit code from executed commands")
    return criteria or ["Task not completed"]


def _default_tools_for(target_agent: str | None) -> list[str]:
    if target_agent == "optogon":
        return ["Optogon path runtime"]
    if target_agent == "human":
        return ["Manual execution"]
    return ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
