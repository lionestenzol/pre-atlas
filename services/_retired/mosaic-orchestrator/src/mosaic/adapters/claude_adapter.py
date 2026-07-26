"""Claude Adapter — abstraction for AI task execution.

Primary: Anthropic Claude API (for complex tasks)
Fallback: Ollama local model (for non-critical tasks)

Every execution is registered with delta-kernel's work queue:
  POST /api/work/request  before start
  POST /api/work/complete on finish
"""
import time
import structlog
import httpx
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

log = structlog.get_logger()


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class TaskSpec:
    """Specification for a task to execute."""
    task_id: str
    instructions: str
    files_context: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    priority: TaskPriority = TaskPriority.NORMAL
    use_fallback: bool = False  # If True, prefer Ollama over Claude


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    output: str
    duration_seconds: float
    tokens_used: int = 0
    cost_usd: float = 0.0
    provider: str = ""  # "claude" or "ollama"
    error: str = ""


class ClaudeAdapter:
    """Execute tasks via Claude API or Ollama fallback."""

    def __init__(
        self,
        anthropic_api_key: str = "",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:32b",
    ):
        self.anthropic_api_key = anthropic_api_key
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model

    async def execute_task(self, spec: TaskSpec) -> TaskResult:
        """Execute a task, choosing provider based on spec and availability."""
        start = time.monotonic()

        if spec.use_fallback or not self.anthropic_api_key:
            result = await self._execute_ollama(spec)
        else:
            try:
                result = await self._execute_claude(spec)
            except Exception as e:
                log.warning("claude_adapter.claude_failed_fallback", error=str(e))
                result = await self._execute_ollama(spec)

        result.duration_seconds = round(time.monotonic() - start, 2)
        return result

    async def _execute_claude(self, spec: TaskSpec) -> TaskResult:
        """Execute via Anthropic Claude API."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.anthropic_api_key)
            message = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": spec.instructions}],
            )

            output = message.content[0].text if message.content else ""
            tokens = (message.usage.input_tokens or 0) + (message.usage.output_tokens or 0)

            return TaskResult(
                task_id=spec.task_id,
                success=True,
                output=output,
                duration_seconds=0,  # will be set by caller
                tokens_used=tokens,
                provider="claude",
            )
        except Exception as e:
            return TaskResult(
                task_id=spec.task_id,
                success=False,
                output="",
                duration_seconds=0,
                provider="claude",
                error=str(e),
            )

    async def _execute_ollama(self, spec: TaskSpec) -> TaskResult:
        """Execute via local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=spec.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": spec.instructions,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                return TaskResult(
                    task_id=spec.task_id,
                    success=True,
                    output=data.get("response", ""),
                    duration_seconds=0,
                    tokens_used=data.get("eval_count", 0),
                    provider="ollama",
                )
        except Exception as e:
            return TaskResult(
                task_id=spec.task_id,
                success=False,
                output="",
                duration_seconds=0,
                provider="ollama",
                error=str(e),
            )
