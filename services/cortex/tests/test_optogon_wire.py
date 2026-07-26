"""Smoke tests for the Optogon-into-Cortex wire."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cortex.contracts import (
    CortexTask, TaskIntent, TaskDomain, ActionType,
    ExecutionSpec, ExecutionStep, ExpectedOutput, OutputType, StepStatus, TaskStatus,
)
from cortex.agents.planner import Planner
from cortex.agents.executor import Executor
from cortex.clients.optogon_client import OptogonClient


@pytest.mark.asyncio
async def test_planner_emits_optogon_session():
    """RUN_PATH intent must produce a single OPTOGON_SESSION step with the path_id."""
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.RUN_PATH,
        domain=TaskDomain.COGNITIVE,
        params={"path_id": "commit_a_file", "initial_context": {"foo": "bar"}},
    )
    spec = await Planner().plan(task)
    assert spec is not None
    assert len(spec.steps) == 1
    step = spec.steps[0]
    assert step.action_type == ActionType.OPTOGON_SESSION
    assert step.params["path_id"] == "commit_a_file"
    assert step.params["initial_context"] == {"foo": "bar"}
    assert step.expected_output.type == OutputType.JSON


@pytest.mark.asyncio
async def test_executor_dispatches_optogon():
    """Executor must dispatch OPTOGON_SESSION steps to the OptogonClient."""
    fake_response = {
        "session_id": "sess-123",
        "state": {"closed_at": 999},
        "response": "done",
        "signals": [],
        "outputs": {"codex_success": True},
        "turns_walked": 3,
        "closed": True,
    }

    optogon = OptogonClient()
    optogon.run_session = AsyncMock(return_value=fake_response)

    uasc = AsyncMock()
    delta = AsyncMock()

    executor = Executor(uasc=uasc, delta=delta, optogon=optogon)

    spec = ExecutionSpec(
        task_id="task-1",
        steps=[
            ExecutionStep(
                step_index=0,
                action_type=ActionType.OPTOGON_SESSION,
                params={"path_id": "commit_a_file", "initial_context": {"k": "v"}},
                expected_output=ExpectedOutput(type=OutputType.JSON),
            ),
        ],
    )

    result = await executor.execute(spec)

    assert result.status == TaskStatus.COMPLETED
    assert len(result.step_results) == 1
    sr = result.step_results[0]
    assert sr.status == StepStatus.SUCCESS
    assert sr.output == fake_response

    optogon.run_session.assert_awaited_once_with(
        path_id="commit_a_file",
        initial_context={"k": "v"},
        context_package=None,
        sitepull_audit_dir=None,
    )

    await optogon.close()


@pytest.mark.asyncio
async def test_optogon_client_construction():
    """OptogonClient must point at :3010 and close cleanly."""
    c = OptogonClient()
    assert c._base.endswith(":3010")
    await c.close()
