"""Reviewer agent — validates ExecutionResult against ExecutionSpec."""

from __future__ import annotations

import logging

from cortex.contracts import (
    ExecutionSpec, ExecutionResult, ValidationVerdict, ValidationFailure,
    StepStatus, TaskStatus, CheckType, Severity, Recommendation,
)

log = logging.getLogger("cortex.reviewer")


class Reviewer:
    def validate(self, spec: ExecutionSpec, result: ExecutionResult) -> ValidationVerdict:
        """Validate result against spec. Pure logic, no I/O."""
        failures: list[ValidationFailure] = []

        # Check 1: Step count
        expected_count = len(spec.steps)
        actual_count = len(result.step_results)
        if actual_count != expected_count:
            failures.append(ValidationFailure(
                check=CheckType.STEP_COUNT,
                expected=expected_count,
                actual=actual_count,
                severity=Severity.BLOCKING if actual_count < expected_count else Severity.WARNING,
            ))

        # Check 2: Error states
        for sr in result.step_results:
            if sr.status == StepStatus.FAILED:
                failures.append(ValidationFailure(
                    step_index=sr.step_index,
                    check=CheckType.ERROR_STATE,
                    expected="success",
                    actual=sr.error.model_dump() if sr.error else "unknown",
                    severity=Severity.BLOCKING,
                ))

        # Check 3: Output shape validation
        for sr in result.step_results:
            if sr.status != StepStatus.SUCCESS:
                continue
            step = next((s for s in spec.steps if s.step_index == sr.step_index), None)
            if not step:
                continue
            expected_type = step.expected_output.type.value
            if expected_type == "void":
                continue
            if expected_type == "json" and not isinstance(sr.output, (dict, list)):
                failures.append(ValidationFailure(
                    step_index=sr.step_index,
                    check=CheckType.OUTPUT_SHAPE,
                    expected="json (dict or list)",
                    actual=type(sr.output).__name__,
                    severity=Severity.WARNING,
                ))
            elif expected_type == "text" and not isinstance(sr.output, str):
                failures.append(ValidationFailure(
                    step_index=sr.step_index,
                    check=CheckType.OUTPUT_SHAPE,
                    expected="text (str)",
                    actual=type(sr.output).__name__,
                    severity=Severity.WARNING,
                ))
            elif expected_type == "boolean" and not isinstance(sr.output, bool):
                failures.append(ValidationFailure(
                    step_index=sr.step_index,
                    check=CheckType.OUTPUT_SHAPE,
                    expected="boolean",
                    actual=type(sr.output).__name__,
                    severity=Severity.WARNING,
                ))

        # Check 4: Cost overrun
        if spec.estimated_cost_usd > 0 and result.total_cost_usd > spec.estimated_cost_usd * 2:
            failures.append(ValidationFailure(
                check=CheckType.COST_OVERRUN,
                expected=spec.estimated_cost_usd,
                actual=result.total_cost_usd,
                severity=Severity.WARNING,
            ))

        # Determine recommendation
        blocking = [f for f in failures if f.severity == Severity.BLOCKING]
        warnings = [f for f in failures if f.severity == Severity.WARNING]

        if not failures:
            recommendation = Recommendation.ACCEPT
            passed = True
            confidence = 1.0
        elif not blocking and warnings:
            # Warnings only — accept with lower confidence
            recommendation = Recommendation.ACCEPT
            passed = True
            confidence = max(0.5, 1.0 - 0.1 * len(warnings))
        elif result.status == TaskStatus.FAILED:
            # Check if any failed steps are retryable
            retryable = any(
                sr.error and sr.error.retryable
                for sr in result.step_results
                if sr.status == StepStatus.FAILED
            )
            if retryable:
                recommendation = Recommendation.RETRY
            else:
                # Check if we have rollback actions available
                has_rollback = any(s.rollback for s in spec.steps)
                recommendation = Recommendation.ROLLBACK if has_rollback else Recommendation.ESCALATE
            passed = False
            confidence = 0.0
        else:
            recommendation = Recommendation.ESCALATE
            passed = False
            confidence = 0.0

        verdict = ValidationVerdict(
            result_id=result.result_id,
            task_id=result.task_id,
            passed=passed,
            confidence=confidence,
            failures=failures,
            recommendation=recommendation,
        )

        log.info(
            "Verdict for task %s: passed=%s rec=%s failures=%d",
            result.task_id, passed, recommendation.value, len(failures),
        )
        return verdict
