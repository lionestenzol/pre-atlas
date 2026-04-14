"""Executor agent — walks an ExecutionSpec step-by-step."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from cortex.contracts import (
    ExecutionSpec, ExecutionResult, StepResult, StepError,
    ActionType, StepStatus, TaskStatus,
)
from cortex.config import config
from cortex.clients.delta_client import DeltaClient
from cortex.clients.uasc_client import UascClient

log = logging.getLogger("cortex.executor")


class Executor:
    def __init__(self, uasc: UascClient, delta: DeltaClient) -> None:
        self._uasc = uasc
        self._delta = delta
        self._http = httpx.AsyncClient(timeout=30.0)

    async def execute(self, spec: ExecutionSpec) -> ExecutionResult:
        """Execute all steps in the spec sequentially."""
        step_results: list[StepResult] = []
        started_at = int(time.time() * 1000)
        total_cost = 0.0
        final_status = TaskStatus.COMPLETED

        for step in spec.steps:
            # Check dependencies
            for dep_idx in step.depends_on:
                dep = next((r for r in step_results if r.step_index == dep_idx), None)
                if not dep or dep.status != StepStatus.SUCCESS:
                    step_results.append(StepResult(
                        step_index=step.step_index,
                        status=StepStatus.SKIPPED,
                        error=StepError(code="DEP_FAILED", message=f"Dependency step {dep_idx} not successful"),
                        started_at=int(time.time() * 1000),
                        completed_at=int(time.time() * 1000),
                    ))
                    final_status = TaskStatus.PARTIAL
                    continue

            result = await self._execute_step(step)
            step_results.append(result)
            total_cost += result.cost_usd

            if result.status == StepStatus.FAILED:
                # Retry once if retryable
                if result.error and result.error.retryable:
                    log.info("Retrying step %d (retryable)", step.step_index)
                    retry_result = await self._execute_step(step)
                    step_results[-1] = retry_result
                    total_cost += retry_result.cost_usd
                    if retry_result.status == StepStatus.FAILED:
                        final_status = TaskStatus.FAILED
                        break
                else:
                    final_status = TaskStatus.FAILED
                    break

        return ExecutionResult(
            spec_id=spec.spec_id,
            task_id=spec.task_id,
            status=final_status,
            step_results=step_results,
            total_cost_usd=total_cost,
            started_at=started_at,
            completed_at=int(time.time() * 1000),
        )

    async def rollback(self, spec: ExecutionSpec, result: ExecutionResult) -> None:
        """Roll back completed steps in reverse order."""
        completed = [
            r for r in result.step_results if r.status == StepStatus.SUCCESS
        ]
        for step_result in reversed(completed):
            step = next((s for s in spec.steps if s.step_index == step_result.step_index), None)
            if step and step.rollback:
                log.info("Rolling back step %d via %s", step.step_index, step.rollback.action_type)
                try:
                    from cortex.contracts import ExecutionStep, ExpectedOutput
                    rollback_step = ExecutionStep(
                        step_index=step.step_index,
                        action_type=step.rollback.action_type,
                        params=step.rollback.params,
                        expected_output=ExpectedOutput(),
                    )
                    await self._execute_step(rollback_step)
                except Exception:
                    log.exception("Rollback failed for step %d", step.step_index)

    async def _execute_step(self, step) -> StepResult:
        """Dispatch a single step to the appropriate handler."""
        started_at = int(time.time() * 1000)
        try:
            handler = self._DISPATCH.get(step.action_type)
            if not handler:
                return StepResult(
                    step_index=step.step_index,
                    status=StepStatus.FAILED,
                    error=StepError(code="UNKNOWN_ACTION", message=f"No handler for {step.action_type}"),
                    started_at=started_at,
                    completed_at=int(time.time() * 1000),
                )
            output, cost = await handler(self, step.params)
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.SUCCESS,
                output=output,
                cost_usd=cost,
                started_at=started_at,
                completed_at=int(time.time() * 1000),
            )
        except httpx.HTTPStatusError as e:
            retryable = e.response.status_code >= 500
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.FAILED,
                error=StepError(
                    code=f"HTTP_{e.response.status_code}",
                    message=str(e),
                    retryable=retryable,
                ),
                started_at=started_at,
                completed_at=int(time.time() * 1000),
            )
        except httpx.HTTPError as e:
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.FAILED,
                error=StepError(code="NETWORK", message=str(e), retryable=True),
                started_at=started_at,
                completed_at=int(time.time() * 1000),
            )
        except Exception as e:
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.FAILED,
                error=StepError(code="INTERNAL", message=str(e), retryable=False),
                started_at=started_at,
                completed_at=int(time.time() * 1000),
            )

    # --- Step Handlers ---

    async def _handle_api_call(self, params: dict) -> tuple:
        method = params.get("method", "GET").upper()
        url = params["url"]
        body = params.get("body")
        headers = params.get("headers", {})

        if method == "GET":
            r = await self._http.get(url, headers=headers)
        elif method == "POST":
            r = await self._http.post(url, json=body, headers=headers)
        elif method == "PUT":
            r = await self._http.put(url, json=body, headers=headers)
        elif method == "DELETE":
            r = await self._http.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        r.raise_for_status()
        try:
            return r.json(), 0.0
        except Exception:
            return r.text, 0.0

    async def _handle_uasc_command(self, params: dict) -> tuple:
        token = params["token"]
        cmd_params = {k: v for k, v in params.items() if k != "token"}
        result = await self._uasc.exec_command(token, cmd_params)
        return result, 0.0

    async def _handle_file_write(self, params: dict) -> tuple:
        path = Path(params["path"])
        content = params["content"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "bytes": len(content)}, 0.0

    async def _handle_file_read(self, params: dict) -> tuple:
        path = Path(params["path"])
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        return {"path": str(path), "content": content, "bytes": len(content)}, 0.0

    async def _handle_claude_generate(self, params: dict) -> tuple:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("No ANTHROPIC_API_KEY configured")

        prompt = params["prompt"]
        max_tokens = params.get("max_tokens", 1000)

        r = await self._http.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": params.get("model", config.CLAUDE_MODEL),
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        data = r.json()
        text = data["content"][0]["text"]
        # Rough cost estimate: $3/MTok input, $15/MTok output for Sonnet
        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
        cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
        return {"text": text}, cost

    async def _handle_state_update(self, params: dict) -> tuple:
        result = await self._delta.post_timeline_event(params)
        return result, 0.0

    async def _handle_shell_exec(self, params: dict) -> tuple:
        import asyncio
        command = params["command"]
        cwd = params.get("cwd")
        timeout = params.get("timeout", 30)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")

        if proc.returncode != 0:
            raise RuntimeError(f"Command failed (rc={proc.returncode}): {stderr.decode()}")

        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": proc.returncode,
        }, 0.0

    async def _handle_noop(self, params: dict) -> tuple:
        return {"noop": True}, 0.0

    _DISPATCH = {
        ActionType.API_CALL: _handle_api_call,
        ActionType.UASC_COMMAND: _handle_uasc_command,
        ActionType.FILE_WRITE: _handle_file_write,
        ActionType.FILE_READ: _handle_file_read,
        ActionType.CLAUDE_GENERATE: _handle_claude_generate,
        ActionType.STATE_UPDATE: _handle_state_update,
        ActionType.SHELL_EXEC: _handle_shell_exec,
        ActionType.NOOP: _handle_noop,
    }
