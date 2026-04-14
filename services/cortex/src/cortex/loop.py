"""Autonomous execution loop — the brain of Cortex."""

from __future__ import annotations

import asyncio
import logging
import time

from cortex.config import config
from cortex.contracts import (
    CortexTask, ExecutionSpec, ExecutionResult, ValidationVerdict,
    TaskStatus, Recommendation,
)
from cortex.clients.delta_client import DeltaClient
from cortex.clients.aegis_client import AegisClient
from cortex.clients.uasc_client import UascClient
from cortex.recovery import CircuitBreaker, CircuitOpenError

log = logging.getLogger("cortex.loop")

# Local task queue (for direct submissions that bypass delta)
_local_queue: asyncio.Queue[dict] = asyncio.Queue()

# Loop metrics
_metrics = {
    "tasks_processed": 0,
    "tasks_completed": 0,
    "tasks_failed": 0,
    "total_cost_usd": 0.0,
    "last_poll_at": 0,
    "loop_running": False,
    "started_at": int(time.time() * 1000),
}

# Task history (last 20 executions with full trace)
_task_history: list[dict] = []
MAX_HISTORY = 20


def _record_task(task: CortexTask, spec: ExecutionSpec | None, result: ExecutionResult | None, verdict: ValidationVerdict | None, final_status: str) -> None:
    entry = {
        "task_id": task.task_id,
        "intent": task.intent.value if hasattr(task.intent, 'value') else str(task.intent),
        "domain": task.domain.value if hasattr(task.domain, 'value') else str(task.domain),
        "source": task.source.value if hasattr(task.source, 'value') else str(task.source),
        "priority": task.priority,
        "status": final_status,
        "timestamp": int(time.time() * 1000),
        "spec": {
            "plan_method": spec.plan_method.value if spec else None,
            "step_count": len(spec.steps) if spec else 0,
            "estimated_cost_usd": spec.estimated_cost_usd if spec else 0,
        } if spec else None,
        "result": {
            "step_results": [
                {
                    "step_index": sr.step_index,
                    "status": sr.status.value,
                    "action_type": spec.steps[sr.step_index].action_type.value if spec and sr.step_index < len(spec.steps) else "unknown",
                    "duration_ms": sr.duration_ms,
                    "cost_usd": sr.cost_usd,
                    "error": sr.error.model_dump() if sr.error else None,
                }
                for sr in result.step_results
            ] if result else [],
            "total_cost_usd": result.total_cost_usd if result else 0,
            "duration_ms": (result.completed_at - result.started_at) if result else 0,
        } if result else None,
        "verdict": {
            "passed": verdict.passed,
            "confidence": verdict.confidence,
            "recommendation": verdict.recommendation.value,
            "failure_count": len(verdict.failures),
        } if verdict else None,
    }
    _task_history.insert(0, entry)
    if len(_task_history) > MAX_HISTORY:
        _task_history.pop()


def get_loop_status() -> dict:
    return {**_metrics, "queue_size": _local_queue.qsize()}


def get_task_history() -> list[dict]:
    return list(_task_history)


async def enqueue_local_task(task_data: dict) -> str:
    task = CortexTask(**task_data)
    await _local_queue.put(task.model_dump())
    return task.task_id


async def execution_loop(
    delta: DeltaClient,
    aegis: AegisClient,
    uasc: UascClient,
    breakers: dict[str, CircuitBreaker],
) -> None:
    """Main loop: poll → lock → gate → plan → execute → review → complete."""
    from cortex.agents.planner import Planner
    from cortex.agents.executor import Executor
    from cortex.agents.reviewer import Reviewer

    planner = Planner()
    executor = Executor(uasc=uasc, delta=delta)
    reviewer = Reviewer()

    _metrics["loop_running"] = True
    log.info("Execution loop started (poll every %.1fs)", config.POLL_INTERVAL_SECONDS)

    while True:
        try:
            _metrics["last_poll_at"] = int(time.time() * 1000)

            # 1. Get next task (local queue first, then delta-kernel)
            task_data = await _poll_next_task(delta, breakers["delta"])
            if not task_data:
                await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            task = CortexTask(**task_data)
            _metrics["tasks_processed"] += 1
            log.info("Processing task %s [%s/%s]", task.task_id, task.intent, task.domain)

            # 2. Aegis gate
            gate_result = await _aegis_gate(aegis, breakers["aegis"], task)
            if gate_result == "denied":
                await _update_status(delta, task.task_id, TaskStatus.BLOCKED)
                _record_task(task, None, None, None, "blocked")
                continue
            if gate_result == "pending_approval":
                await _update_status(delta, task.task_id, TaskStatus.AWAITING_APPROVAL)
                _record_task(task, None, None, None, "awaiting_approval")
                continue

            # 3. Plan
            await _update_status(delta, task.task_id, TaskStatus.PLANNING)
            spec = await planner.plan(task)
            if not spec:
                await _update_status(delta, task.task_id, TaskStatus.UNPLANNABLE)
                _record_task(task, None, None, None, "unplannable")
                log.warning("Task %s unplannable", task.task_id)
                continue

            if spec.estimated_cost_usd > task.constraints.max_cost_usd:
                await _update_status(delta, task.task_id, TaskStatus.BUDGET_EXCEEDED)
                _record_task(task, spec, None, None, "budget_exceeded")
                log.warning(
                    "Task %s over budget: est=%.3f max=%.3f",
                    task.task_id, spec.estimated_cost_usd, task.constraints.max_cost_usd,
                )
                continue

            # 4. Execute
            await _update_status(delta, task.task_id, TaskStatus.EXECUTING)
            result = await executor.execute(spec)

            # 5. Review
            await _update_status(delta, task.task_id, TaskStatus.REVIEWING)
            verdict = reviewer.validate(spec, result)

            # 6. Act on verdict
            await _handle_verdict(delta, task, spec, result, verdict, planner, executor, reviewer)

        except CircuitOpenError as e:
            log.warning("Circuit open: %s — sleeping", e)
            await asyncio.sleep(config.CB_COOLDOWN_SECONDS)
        except asyncio.CancelledError:
            log.info("Execution loop cancelled")
            _metrics["loop_running"] = False
            return
        except Exception:
            log.exception("Unhandled error in execution loop")
            await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


async def _poll_next_task(delta: DeltaClient, breaker: CircuitBreaker) -> dict | None:
    # Check local queue first
    try:
        return _local_queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    # Poll delta-kernel
    try:
        tasks = await breaker.call(delta.get_pending_tasks())
        if tasks:
            # Sort: priority DESC, created_at ASC
            tasks.sort(key=lambda t: (-t.get("priority", 1), t.get("created_at", 0)))
            return tasks[0]
    except CircuitOpenError:
        raise
    except Exception:
        log.debug("Delta poll failed", exc_info=True)
    return None


async def _aegis_gate(aegis: AegisClient, breaker: CircuitBreaker, task: CortexTask) -> str:
    """Returns 'allowed', 'denied', or 'pending_approval'."""
    try:
        result = await breaker.call(
            aegis.submit_action("execute_task", {"task_id": task.task_id, "intent": task.intent})
        )
        status = result.get("status", "executed")
        if status == "denied":
            log.warning("Aegis DENIED task %s: %s", task.task_id, result.get("policy_decision", {}).get("reason"))
            return "denied"
        if status == "pending_approval":
            log.info("Aegis requires approval for task %s", task.task_id)
            return "pending_approval"
        return "allowed"
    except CircuitOpenError:
        raise
    except Exception:
        log.warning("Aegis gate failed — defaulting to allowed (fail-open for now)")
        return "allowed"


async def _update_status(delta: DeltaClient, task_id: str, status: TaskStatus) -> None:
    try:
        await delta.update_task_status(task_id, status.value)
    except Exception:
        log.debug("Status update failed for %s → %s", task_id, status.value, exc_info=True)


async def _handle_verdict(
    delta: DeltaClient,
    task: CortexTask,
    spec: ExecutionSpec,
    result: ExecutionResult,
    verdict: ValidationVerdict,
    planner,
    executor,
    reviewer,
) -> None:
    if verdict.passed and verdict.recommendation == Recommendation.ACCEPT:
        await _update_status(delta, task.task_id, TaskStatus.COMPLETED)
        _metrics["tasks_completed"] += 1
        _metrics["total_cost_usd"] += result.total_cost_usd
        _record_task(task, spec, result, verdict, "completed")
        log.info(
            "Task %s COMPLETED (cost=$%.4f, steps=%d)",
            task.task_id, result.total_cost_usd, len(result.step_results),
        )
        try:
            await delta.post_timeline_event({
                "type": "task.completed",
                "task_id": task.task_id,
                "intent": task.intent,
                "cost_usd": result.total_cost_usd,
                "steps": len(result.step_results),
                "timestamp": int(time.time() * 1000),
            })
        except Exception:
            log.debug("Timeline event post failed", exc_info=True)

    elif verdict.recommendation == Recommendation.RETRY:
        task.retry_count += 1
        if task.retry_count < config.MAX_RETRIES:
            log.info("Retrying task %s (attempt %d/%d)", task.task_id, task.retry_count, config.MAX_RETRIES)
            new_spec = await planner.plan(task)
            if new_spec:
                new_result = await executor.execute(new_spec)
                new_verdict = reviewer.validate(new_spec, new_result)
                await _handle_verdict(delta, task, new_spec, new_result, new_verdict, planner, executor, reviewer)
            else:
                await _update_status(delta, task.task_id, TaskStatus.DEAD)
                _metrics["tasks_failed"] += 1
                _record_task(task, spec, result, verdict, "dead")
        else:
            await _update_status(delta, task.task_id, TaskStatus.DEAD)
            _metrics["tasks_failed"] += 1
            _record_task(task, spec, result, verdict, "dead")
            log.error("Task %s DEAD after %d retries", task.task_id, config.MAX_RETRIES)

    elif verdict.recommendation == Recommendation.ROLLBACK:
        await executor.rollback(spec, result)
        await _update_status(delta, task.task_id, TaskStatus.ROLLED_BACK)
        _metrics["tasks_failed"] += 1
        _record_task(task, spec, result, verdict, "rolled_back")
        log.warning("Task %s ROLLED BACK", task.task_id)

    elif verdict.recommendation == Recommendation.ESCALATE:
        await _update_status(delta, task.task_id, TaskStatus.ESCALATED)
        _metrics["tasks_failed"] += 1
        _record_task(task, spec, result, verdict, "escalated")
        log.error("Task %s ESCALATED — requires human review", task.task_id)


async def approval_poll_loop(delta: DeltaClient, aegis: AegisClient) -> None:
    """Poll aegis for resolved approvals and re-queue tasks."""
    log.info("Approval poll loop started (every %.0fs)", config.APPROVAL_POLL_SECONDS)
    while True:
        try:
            approvals = await aegis.get_pending_approvals()
            for approval in approvals:
                status = approval.get("status", "PENDING")
                task_id = approval.get("params", {}).get("task_id")
                if not task_id:
                    continue
                if status == "APPROVED":
                    log.info("Approval granted for task %s — re-queuing", task_id)
                    await _update_status(delta, task_id, TaskStatus.READY)
                elif status == "REJECTED":
                    log.info("Approval rejected for task %s", task_id)
                    await _update_status(delta, task_id, TaskStatus.REJECTED)
                elif status == "EXPIRED":
                    log.info("Approval expired for task %s", task_id)
                    await _update_status(delta, task_id, TaskStatus.EXPIRED)
        except asyncio.CancelledError:
            return
        except Exception:
            log.debug("Approval poll failed", exc_info=True)
        await asyncio.sleep(config.APPROVAL_POLL_SECONDS)
