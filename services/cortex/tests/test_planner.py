"""Unit tests for the planner agent."""

import pytest
from cortex.contracts import (
    CortexTask, TaskIntent, TaskDomain, ActionType, PlanMethod,
)
from cortex.agents.planner import Planner


@pytest.fixture
def planner():
    return Planner()


@pytest.mark.asyncio
async def test_plan_close_loop(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.CLOSE_LOOP,
        domain=TaskDomain.COGNITIVE,
        params={"loop_id": "loop-42"},
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert spec.task_id == task.task_id
    assert spec.plan_method == PlanMethod.TEMPLATE
    assert len(spec.steps) == 3
    assert spec.steps[0].action_type == ActionType.API_CALL
    assert spec.steps[1].action_type == ActionType.UASC_COMMAND
    assert spec.steps[1].params["loop_id"] == "loop-42"
    assert spec.steps[2].action_type == ActionType.STATE_UPDATE


@pytest.mark.asyncio
async def test_plan_update_state(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.UPDATE_STATE,
        domain=TaskDomain.DELTA,
        params={"key": "mode", "value": "BUILD"},
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert len(spec.steps) == 1
    assert spec.steps[0].action_type == ActionType.STATE_UPDATE


@pytest.mark.asyncio
async def test_plan_run_pipeline(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.RUN_PIPELINE,
        domain=TaskDomain.MOSAIC,
        params={"pipeline": "daily"},
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert spec.steps[0].action_type == ActionType.API_CALL


@pytest.mark.asyncio
async def test_plan_compute_metric(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.COMPUTE_METRIC,
        domain=TaskDomain.MOSAIC,
        params={"metric": "compound_score"},
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert len(spec.steps) == 2
    assert spec.steps[1].depends_on == [0]


@pytest.mark.asyncio
async def test_plan_execute_directive(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.EXECUTE_DIRECTIVE,
        domain=TaskDomain.COGNITIVE,
        params={
            "instructions": "Ship something from the 'AI Consulting' domain.",
            "directive_type": "EXECUTE",
            "domain": "AI Consulting",
        },
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert len(spec.steps) == 2
    assert spec.steps[0].action_type == ActionType.CLAUDE_GENERATE
    assert spec.steps[1].action_type == ActionType.STATE_UPDATE
    assert spec.steps[1].depends_on == [0]
    assert spec.estimated_cost_usd > 0  # Claude call has cost estimate


@pytest.mark.asyncio
async def test_plan_archive_entity(planner):
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.ARCHIVE_ENTITY,
        domain=TaskDomain.AEGIS,
        params={"entity_id": "ent-99"},
    )
    spec = await planner.plan(task)
    assert spec is not None
    assert spec.steps[0].rollback is not None
    assert spec.steps[0].rollback.params["entity_id"] == "ent-99"
