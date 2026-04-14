"""Planner agent — decomposes CortexTask into ExecutionSpec."""

from __future__ import annotations

import json
import logging
import time

from cortex.contracts import (
    CortexTask, ExecutionSpec, ExecutionStep, ExpectedOutput, RollbackAction,
    TaskIntent, ActionType, OutputType, PlanMethod,
)
from cortex.config import config

log = logging.getLogger("cortex.planner")

# --- Template Registry ---
# Pre-built specs for known intents. No LLM needed.

TEMPLATES: dict[TaskIntent, callable] = {}


def template(intent: TaskIntent):
    def decorator(fn):
        TEMPLATES[intent] = fn
        return fn
    return decorator


@template(TaskIntent.CLOSE_LOOP)
def _plan_close_loop(task: CortexTask) -> list[ExecutionStep]:
    loop_id = task.params.get("loop_id", "")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.API_CALL,
            params={
                "method": "GET",
                "url": f"{config.DELTA_URL}/api/state",
                "headers": {"Authorization": f"Bearer {config.DELTA_API_KEY}"} if config.DELTA_API_KEY else {},
                "description": "Read current state to confirm loop exists",
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
        ExecutionStep(
            step_index=1,
            action_type=ActionType.UASC_COMMAND,
            params={"token": "@CLOSE_LOOP", "loop_id": loop_id},
            expected_output=ExpectedOutput(type=OutputType.JSON),
            rollback=RollbackAction(
                action_type=ActionType.STATE_UPDATE,
                params={"reopen_loop": loop_id},
            ),
        ),
        ExecutionStep(
            step_index=2,
            action_type=ActionType.STATE_UPDATE,
            params={
                "event": "loop.closed",
                "loop_id": loop_id,
                "timestamp": int(time.time() * 1000),
            },
            expected_output=ExpectedOutput(type=OutputType.VOID),
        ),
    ]


@template(TaskIntent.UPDATE_STATE)
def _plan_update_state(task: CortexTask) -> list[ExecutionStep]:
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.STATE_UPDATE,
            params=task.params,
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
    ]


@template(TaskIntent.EXECUTE_DIRECTIVE)
def _plan_execute_directive(task: CortexTask) -> list[ExecutionStep]:
    """Ghost directives with instructions → Claude generates the work product → state update."""
    instructions = task.params.get("instructions", "")
    directive_type = task.params.get("directive_type", "EXECUTE")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.CLAUDE_GENERATE,
            params={
                "prompt": instructions,
                "max_tokens": 2000,
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
        ExecutionStep(
            step_index=1,
            action_type=ActionType.STATE_UPDATE,
            params={
                "event": "directive.executed",
                "directive_type": directive_type,
                "domain": task.params.get("domain", "unknown"),
                "task_id": task.task_id,
                "timestamp": int(time.time() * 1000),
            },
            expected_output=ExpectedOutput(type=OutputType.VOID),
            depends_on=[0],
        ),
    ]


@template(TaskIntent.RUN_PIPELINE)
def _plan_run_pipeline(task: CortexTask) -> list[ExecutionStep]:
    pipeline = task.params.get("pipeline", "daily")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.API_CALL,
            params={
                "method": "POST",
                "url": f"{config.MOSAIC_URL}/api/v1/tasks/execute",
                "body": {
                    "task_id": task.task_id,
                    "instructions": f"Run {pipeline} pipeline",
                    "priority": task.priority,
                },
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
    ]


@template(TaskIntent.SYNC_SERVICE)
def _plan_sync_service(task: CortexTask) -> list[ExecutionStep]:
    target = task.params.get("target_service", "cognitive")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.API_CALL,
            params={
                "method": "GET",
                "url": f"http://localhost:{_port_for(target)}/health",
                "description": f"Health check {target}",
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
        ExecutionStep(
            step_index=1,
            action_type=ActionType.API_CALL,
            params={
                "method": "POST",
                "url": f"{config.DELTA_URL}/api/sync",
                "body": {"service": target},
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
            depends_on=[0],
        ),
    ]


@template(TaskIntent.COMPUTE_METRIC)
def _plan_compute_metric(task: CortexTask) -> list[ExecutionStep]:
    metric = task.params.get("metric", "compound_score")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.API_CALL,
            params={
                "method": "POST",
                "url": f"{config.MOSAIC_URL}/api/v1/compound/run",
                "body": {"metric": metric},
            },
            expected_output=ExpectedOutput(type=OutputType.JSON),
        ),
        ExecutionStep(
            step_index=1,
            action_type=ActionType.STATE_UPDATE,
            params={
                "event": "metric.computed",
                "metric": metric,
                "timestamp": int(time.time() * 1000),
            },
            expected_output=ExpectedOutput(type=OutputType.VOID),
            depends_on=[0],
        ),
    ]


@template(TaskIntent.ARCHIVE_ENTITY)
def _plan_archive(task: CortexTask) -> list[ExecutionStep]:
    entity_id = task.params.get("entity_id", "")
    return [
        ExecutionStep(
            step_index=0,
            action_type=ActionType.STATE_UPDATE,
            params={"action": "archive", "entity_id": entity_id},
            expected_output=ExpectedOutput(type=OutputType.JSON),
            rollback=RollbackAction(
                action_type=ActionType.STATE_UPDATE,
                params={"action": "unarchive", "entity_id": entity_id},
            ),
        ),
    ]


def _port_for(service: str) -> int:
    return {
        "cognitive": 8100,
        "delta": 3001,
        "mosaic": 3005,
        "aegis": 3002,
        "uasc": 3008,
        "mirofish": 3003,
    }.get(service, 8100)


# --- Claude Decomposition (fallback for unknown intents) ---

async def _claude_decompose(task: CortexTask) -> list[ExecutionStep] | None:
    """Use Claude API to decompose an unknown task into execution steps."""
    if not config.ANTHROPIC_API_KEY:
        log.warning("No ANTHROPIC_API_KEY — cannot decompose task %s", task.task_id)
        return None

    try:
        import httpx

        prompt = f"""Decompose this task into deterministic execution steps.

Task:
- intent: {task.intent}
- domain: {task.domain}
- params: {json.dumps(task.params)}

Return a JSON array of steps. Each step must have:
- step_index (int, 0-based)
- action_type (one of: uasc_command, api_call, file_write, file_read, state_update, shell_exec, noop)
- params (object with action-specific parameters)
- expected_output (object with "type": "json"|"text"|"boolean"|"void")

Maximum 10 steps. Be deterministic. No ambiguity."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config.CLAUDE_MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            content = r.json()["content"][0]["text"]

            # Extract JSON from response
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                steps_data = json.loads(content[start:end])
                return [ExecutionStep(**s) for s in steps_data[:10]]

    except Exception:
        log.exception("Claude decomposition failed for task %s", task.task_id)
    return None


# --- Planner Class ---

class Planner:
    async def plan(self, task: CortexTask) -> ExecutionSpec | None:
        """Generate an ExecutionSpec for the given task."""
        # Try template first
        template_fn = TEMPLATES.get(task.intent)
        if template_fn:
            steps = template_fn(task)
            method = PlanMethod.TEMPLATE
            log.info("Task %s planned via template (%d steps)", task.task_id, len(steps))
        else:
            # Fall back to Claude decomposition
            steps = await _claude_decompose(task)
            if not steps:
                return None
            method = PlanMethod.DECOMPOSITION
            log.info("Task %s planned via Claude (%d steps)", task.task_id, len(steps))

        # Estimate cost (rough: $0.003 per Claude call, $0 for deterministic steps)
        est_cost = sum(
            0.003 if s.action_type == ActionType.CLAUDE_GENERATE else 0.0
            for s in steps
        )

        return ExecutionSpec(
            task_id=task.task_id,
            plan_method=method,
            steps=steps,
            estimated_cost_usd=est_cost,
            estimated_duration_seconds=len(steps) * 5,
        )
