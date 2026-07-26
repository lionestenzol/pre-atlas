"""Embedded executor — background asyncio task that polls the queue and executes Claude jobs.

Runs inside the mosaic-orchestrator process. Reuses the existing ClaudeAdapter
for actual execution — no code duplication.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from mosaic.adapters.claude_adapter import ClaudeAdapter, TaskSpec, TaskPriority
from mosaic.metering.metering import MeteringStore
from mosaic.queue.client import QueueClient
from mosaic.queue.publisher import NatsPublisher

log = structlog.get_logger()

# Map priority integers back to TaskPriority enum
_PRIORITY_MAP = {0: TaskPriority.LOW, 1: TaskPriority.NORMAL, 2: TaskPriority.HIGH, 3: TaskPriority.CRITICAL}


class EmbeddedExecutor:
    """Polls the execution_queue and runs Claude jobs in the background."""

    def __init__(
        self,
        queue: QueueClient,
        publisher: NatsPublisher,
        adapter: ClaudeAdapter,
        metering: MeteringStore,
        instance_id: str,
        poll_interval: float = 1.0,
        heartbeat_interval: float = 30.0,
        reap_interval: float = 60.0,
        heartbeat_ttl: int = 300,
    ) -> None:
        self._queue = queue
        self._publisher = publisher
        self._adapter = adapter
        self._metering = metering
        self._instance_id = instance_id
        self._poll_interval = poll_interval
        self._heartbeat_interval = heartbeat_interval
        self._reap_interval = reap_interval
        self._heartbeat_ttl = heartbeat_ttl
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._reap_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the poll and reaper loops."""
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._reap_task = asyncio.create_task(self._reap_loop())
        log.info("executor.started", instance_id=self._instance_id)

    async def stop(self) -> None:
        """Stop the executor gracefully."""
        self._running = False
        for task in (self._poll_task, self._reap_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        log.info("executor.stopped", instance_id=self._instance_id)

    async def _poll_loop(self) -> None:
        """Continuously poll for and execute jobs."""
        while self._running:
            try:
                job = await self._queue.claim("claude", self._instance_id)
                if job:
                    asyncio.create_task(self._execute_job(job))
                else:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("executor.poll_error", error=str(e))
                await asyncio.sleep(self._poll_interval * 5)

    async def _reap_loop(self) -> None:
        """Periodically reap stale jobs."""
        while self._running:
            try:
                await asyncio.sleep(self._reap_interval)
                await self._queue.reap_stale(self._heartbeat_ttl)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("executor.reap_error", error=str(e))

    async def _execute_job(self, job: dict[str, Any]) -> None:
        """Execute a single job with heartbeat and result reporting."""
        job_id = str(job["job_id"])
        heartbeat_task: asyncio.Task[None] | None = None

        try:
            # Start heartbeat
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(job_id))

            # Build TaskSpec from payload
            payload = job["payload"] if isinstance(job["payload"], dict) else {}
            spec = TaskSpec(
                task_id=payload.get("task_id", job.get("task_id", "queue")),
                instructions=payload.get("instructions", ""),
                files_context=payload.get("files_context", []),
                timeout_seconds=job.get("timeout_secs", 300),
                priority=_PRIORITY_MAP.get(job.get("priority", 1), TaskPriority.NORMAL),
                use_fallback=payload.get("use_fallback", False),
            )

            log.info("executor.running", job_id=job_id, task_id=spec.task_id)

            # Execute via the existing ClaudeAdapter
            result = await self._adapter.execute_task(spec)

            # Record metering
            self._metering.record_usage(
                result.duration_seconds, result.tokens_used, result.provider, f"queue:{job_id}"
            )

            # Mark complete
            result_data = {
                "task_id": result.task_id,
                "success": result.success,
                "output": result.output,
                "duration_seconds": result.duration_seconds,
                "tokens_used": result.tokens_used,
                "provider": result.provider,
                "error": result.error,
            }

            if result.success:
                await self._queue.complete(job_id, result_data)
            else:
                await self._queue.fail(job_id, result.error or "execution failed")

            # Emit NATS event (matches TaskCompletedEvent in websocket.ts)
            await self._publisher.publish(
                "task.completed",
                {
                    "jobId": job_id,
                    "outcome": "success" if result.success else "failed",
                    "durationMs": int(result.duration_seconds * 1000),
                    "queueAdvanced": True,
                    "nextJobStarted": None,
                },
            )

        except Exception as e:
            log.error("executor.job_failed", job_id=job_id, error=str(e))
            await self._queue.fail(job_id, str(e))
            await self._publisher.publish(
                "task.completed",
                {
                    "jobId": job_id,
                    "outcome": "failed",
                    "durationMs": 0,
                    "queueAdvanced": True,
                    "nextJobStarted": None,
                },
            )
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self, job_id: str) -> None:
        """Send heartbeats for a running job until cancelled."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._queue.heartbeat(job_id, self._instance_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("executor.heartbeat_failed", job_id=job_id, error=str(e))
