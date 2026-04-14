"""Unit tests for the reviewer agent."""

import pytest
from cortex.contracts import (
    ExecutionSpec, ExecutionStep, ExecutionResult, StepResult, StepError,
    ExpectedOutput, RollbackAction,
    ActionType, OutputType, PlanMethod, TaskStatus, StepStatus,
    Recommendation, CheckType,
)
from cortex.agents.reviewer import Reviewer


@pytest.fixture
def reviewer():
    return Reviewer()


def _make_spec(steps: list[ExecutionStep]) -> ExecutionSpec:
    return ExecutionSpec(
        task_id="task-1",
        plan_method=PlanMethod.TEMPLATE,
        steps=steps,
        estimated_cost_usd=0.01,
    )


def _make_result(task_status: TaskStatus, step_results: list[StepResult]) -> ExecutionResult:
    return ExecutionResult(
        spec_id="spec-1",
        task_id="task-1",
        status=task_status,
        step_results=step_results,
        total_cost_usd=sum(s.cost_usd for s in step_results),
        started_at=1000,
        completed_at=2000,
    )


def test_accept_on_success(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.NOOP, params={},
                      expected_output=ExpectedOutput(type=OutputType.VOID)),
    ])
    result = _make_result(TaskStatus.COMPLETED, [
        StepResult(step_index=0, status=StepStatus.SUCCESS, started_at=1000, completed_at=1050),
    ])
    verdict = reviewer.validate(spec, result)
    assert verdict.passed is True
    assert verdict.recommendation == Recommendation.ACCEPT
    assert verdict.confidence == 1.0


def test_retry_on_retryable_failure(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.API_CALL,
                      params={"url": "http://x", "method": "GET"},
                      expected_output=ExpectedOutput(type=OutputType.JSON)),
    ])
    result = _make_result(TaskStatus.FAILED, [
        StepResult(
            step_index=0, status=StepStatus.FAILED,
            error=StepError(code="HTTP_500", message="Internal Server Error", retryable=True),
            started_at=1000, completed_at=1050,
        ),
    ])
    verdict = reviewer.validate(spec, result)
    assert verdict.passed is False
    assert verdict.recommendation == Recommendation.RETRY


def test_rollback_on_permanent_failure_with_rollback(reviewer):
    spec = _make_spec([
        ExecutionStep(
            step_index=0, action_type=ActionType.STATE_UPDATE, params={},
            expected_output=ExpectedOutput(type=OutputType.JSON),
            rollback=RollbackAction(action_type=ActionType.STATE_UPDATE, params={"undo": True}),
        ),
    ])
    result = _make_result(TaskStatus.FAILED, [
        StepResult(
            step_index=0, status=StepStatus.FAILED,
            error=StepError(code="HTTP_400", message="Bad Request", retryable=False),
            started_at=1000, completed_at=1050,
        ),
    ])
    verdict = reviewer.validate(spec, result)
    assert verdict.passed is False
    assert verdict.recommendation == Recommendation.ROLLBACK


def test_escalate_on_permanent_failure_no_rollback(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.SHELL_EXEC, params={},
                      expected_output=ExpectedOutput(type=OutputType.JSON)),
    ])
    result = _make_result(TaskStatus.FAILED, [
        StepResult(
            step_index=0, status=StepStatus.FAILED,
            error=StepError(code="INTERNAL", message="crash", retryable=False),
            started_at=1000, completed_at=1050,
        ),
    ])
    verdict = reviewer.validate(spec, result)
    assert verdict.passed is False
    assert verdict.recommendation == Recommendation.ESCALATE


def test_step_count_mismatch(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.NOOP, params={},
                      expected_output=ExpectedOutput(type=OutputType.VOID)),
        ExecutionStep(step_index=1, action_type=ActionType.NOOP, params={},
                      expected_output=ExpectedOutput(type=OutputType.VOID)),
    ])
    result = _make_result(TaskStatus.COMPLETED, [
        StepResult(step_index=0, status=StepStatus.SUCCESS, started_at=1000, completed_at=1050),
    ])
    verdict = reviewer.validate(spec, result)
    assert any(f.check == CheckType.STEP_COUNT for f in verdict.failures)


def test_cost_overrun_warning(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.NOOP, params={},
                      expected_output=ExpectedOutput(type=OutputType.VOID)),
    ])
    result = _make_result(TaskStatus.COMPLETED, [
        StepResult(step_index=0, status=StepStatus.SUCCESS, cost_usd=0.10,
                   started_at=1000, completed_at=1050),
    ])
    result.total_cost_usd = 0.10  # 10x the estimated 0.01
    verdict = reviewer.validate(spec, result)
    assert any(f.check == CheckType.COST_OVERRUN for f in verdict.failures)
    # Warnings don't block — should still accept
    assert verdict.passed is True
    assert verdict.recommendation == Recommendation.ACCEPT


def test_output_shape_mismatch(reviewer):
    spec = _make_spec([
        ExecutionStep(step_index=0, action_type=ActionType.API_CALL,
                      params={"url": "http://x", "method": "GET"},
                      expected_output=ExpectedOutput(type=OutputType.JSON)),
    ])
    result = _make_result(TaskStatus.COMPLETED, [
        StepResult(step_index=0, status=StepStatus.SUCCESS, output="not json",
                   started_at=1000, completed_at=1050),
    ])
    verdict = reviewer.validate(spec, result)
    assert any(f.check == CheckType.OUTPUT_SHAPE for f in verdict.failures)
