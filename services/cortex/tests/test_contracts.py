"""Unit tests for Cortex data contracts."""

import pytest
from cortex.contracts import (
    CortexTask, ExecutionSpec, ExecutionStep, ExecutionResult, StepResult,
    ValidationVerdict, ValidationFailure, ExpectedOutput,
    TaskIntent, TaskDomain, TaskSource, ActionType, OutputType,
    PlanMethod, TaskStatus, StepStatus, CheckType, Severity, Recommendation,
)


def test_cortex_task_defaults():
    task = CortexTask(
        tenant_id="test-tenant",
        intent=TaskIntent.CLOSE_LOOP,
        domain=TaskDomain.COGNITIVE,
    )
    assert task.task_id  # auto-generated UUID
    assert task.priority == 1
    assert task.status == TaskStatus.READY
    assert task.constraints.timeout_seconds == 300
    assert task.constraints.max_cost_usd == 0.50


def test_cortex_task_with_params():
    task = CortexTask(
        tenant_id="t1",
        intent=TaskIntent.CLOSE_LOOP,
        domain=TaskDomain.DELTA,
        priority=3,
        params={"loop_id": "loop-123"},
        source=TaskSource.AUTO_ACTOR,
    )
    assert task.priority == 3
    assert task.params["loop_id"] == "loop-123"
    assert task.source == TaskSource.AUTO_ACTOR


def test_execution_spec():
    spec = ExecutionSpec(
        task_id="task-1",
        plan_method=PlanMethod.TEMPLATE,
        steps=[
            ExecutionStep(
                step_index=0,
                action_type=ActionType.API_CALL,
                params={"url": "http://localhost:3001/health", "method": "GET"},
                expected_output=ExpectedOutput(type=OutputType.JSON),
            ),
            ExecutionStep(
                step_index=1,
                action_type=ActionType.NOOP,
                params={},
                expected_output=ExpectedOutput(type=OutputType.VOID),
                depends_on=[0],
            ),
        ],
    )
    assert spec.spec_id  # auto-generated
    assert len(spec.steps) == 2
    assert spec.steps[1].depends_on == [0]


def test_execution_result():
    result = ExecutionResult(
        spec_id="spec-1",
        task_id="task-1",
        status=TaskStatus.COMPLETED,
        step_results=[
            StepResult(
                step_index=0,
                status=StepStatus.SUCCESS,
                output={"healthy": True},
                duration_ms=50,
                started_at=1000,
                completed_at=1050,
            ),
        ],
        total_cost_usd=0.0,
        started_at=1000,
        completed_at=1050,
    )
    assert result.status == TaskStatus.COMPLETED
    assert result.step_results[0].output["healthy"] is True


def test_validation_verdict_pass():
    verdict = ValidationVerdict(
        result_id="r1",
        task_id="t1",
        passed=True,
        confidence=1.0,
        recommendation=Recommendation.ACCEPT,
    )
    assert verdict.passed
    assert verdict.failures == []


def test_validation_verdict_fail():
    verdict = ValidationVerdict(
        result_id="r1",
        task_id="t1",
        passed=False,
        confidence=0.0,
        failures=[
            ValidationFailure(
                step_index=0,
                check=CheckType.ERROR_STATE,
                expected="success",
                actual="HTTP_500",
                severity=Severity.BLOCKING,
            ),
        ],
        recommendation=Recommendation.RETRY,
    )
    assert not verdict.passed
    assert len(verdict.failures) == 1
    assert verdict.recommendation == Recommendation.RETRY
