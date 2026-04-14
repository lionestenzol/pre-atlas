"""Cortex data contracts — Pydantic models for the execution layer."""

from __future__ import annotations

import uuid
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class TaskIntent(str, Enum):
    CLOSE_LOOP = "close_loop"
    EXECUTE_DIRECTIVE = "execute_directive"
    UPDATE_STATE = "update_state"
    GENERATE_ARTIFACT = "generate_artifact"
    RUN_PIPELINE = "run_pipeline"
    SYNC_SERVICE = "sync_service"
    ARCHIVE_ENTITY = "archive_entity"
    COMPUTE_METRIC = "compute_metric"


class TaskDomain(str, Enum):
    COGNITIVE = "cognitive"
    DELTA = "delta"
    MOSAIC = "mosaic"
    AEGIS = "aegis"
    UASC = "uasc"
    MIROFISH = "mirofish"


class TaskSource(str, Enum):
    GOVERNANCE = "governance"
    COMPOUND_LOOP = "compound_loop"
    GHOST_EXECUTOR = "ghost_executor"
    AUTO_ACTOR = "auto_actor"
    MANUAL = "manual"


class Mode(str, Enum):
    RECOVER = "RECOVER"
    CLOSURE = "CLOSURE"
    MAINTENANCE = "MAINTENANCE"
    BUILD = "BUILD"
    COMPOUND = "COMPOUND"
    SCALE = "SCALE"


class ActionType(str, Enum):
    UASC_COMMAND = "uasc_command"
    API_CALL = "api_call"
    FILE_WRITE = "file_write"
    FILE_READ = "file_read"
    CLAUDE_GENERATE = "claude_generate"
    STATE_UPDATE = "state_update"
    SHELL_EXEC = "shell_exec"
    NOOP = "noop"


class OutputType(str, Enum):
    JSON = "json"
    TEXT = "text"
    BOOLEAN = "boolean"
    VOID = "void"


class PlanMethod(str, Enum):
    TEMPLATE = "template"
    DECOMPOSITION = "decomposition"
    SINGLE_STEP = "single_step"


class TaskStatus(str, Enum):
    READY = "ready"
    LOCKED = "locked"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    ROLLED_BACK = "rolled_back"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEAD = "dead"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    REJECTED = "rejected"
    UNPLANNABLE = "unplannable"


class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class Recommendation(str, Enum):
    ACCEPT = "accept"
    RETRY = "retry"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"


class CheckType(str, Enum):
    OUTPUT_SHAPE = "output_shape"
    STEP_COUNT = "step_count"
    ERROR_STATE = "error_state"
    SIDE_EFFECT = "side_effect"
    COST_OVERRUN = "cost_overrun"


class Severity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


# --- Contract Models ---

class TaskConstraints(BaseModel):
    timeout_seconds: int = 300
    max_cost_usd: float = 0.50
    requires_approval: bool = False
    idempotent: bool = True


class CortexTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    source: TaskSource = TaskSource.MANUAL
    intent: TaskIntent
    domain: TaskDomain
    priority: int = Field(ge=0, le=3, default=1)
    params: dict[str, Any] = Field(default_factory=dict)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    mode_at_creation: Mode | None = None
    status: TaskStatus = TaskStatus.READY
    retry_count: int = 0
    locked_at: int | None = None
    lock_holder: str | None = None


class ExpectedOutput(BaseModel):
    type: OutputType = OutputType.VOID
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema")


class RollbackAction(BaseModel):
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)


class ExecutionStep(BaseModel):
    step_index: int = Field(ge=0)
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    expected_output: ExpectedOutput = Field(default_factory=ExpectedOutput)
    rollback: RollbackAction | None = None
    depends_on: list[int] = Field(default_factory=list)


class ExecutionSpec(BaseModel):
    spec_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    plan_method: PlanMethod = PlanMethod.TEMPLATE
    steps: list[ExecutionStep] = Field(min_length=1, max_length=20)
    estimated_cost_usd: float = 0.0
    estimated_duration_seconds: int = 0
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))


class StepError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class StepResult(BaseModel):
    step_index: int
    status: StepStatus
    output: Any = None
    error: StepError | None = None
    duration_ms: int = 0
    cost_usd: float = 0.0
    started_at: int = 0
    completed_at: int = 0


class ExecutionResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    spec_id: str
    task_id: str
    status: TaskStatus
    step_results: list[StepResult] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    started_at: int = 0
    completed_at: int = 0


class ValidationFailure(BaseModel):
    step_index: int | None = None
    check: CheckType
    expected: Any = None
    actual: Any = None
    severity: Severity = Severity.BLOCKING


class ValidationVerdict(BaseModel):
    verdict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    result_id: str
    task_id: str
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    failures: list[ValidationFailure] = Field(default_factory=list)
    recommendation: Recommendation = Recommendation.ACCEPT
    evaluated_at: int = Field(default_factory=lambda: int(time.time() * 1000))
