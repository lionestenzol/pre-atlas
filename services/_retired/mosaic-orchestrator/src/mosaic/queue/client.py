"""Queue client — asyncpg-based access to the execution_queue table."""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
import structlog

log = structlog.get_logger()


class QueueClient:
    """Manages the execution_queue table in PostgreSQL."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str, max_size: int = 5) -> None:
        self._pool = await asyncpg.create_pool(dsn, min_size=1, max_size=max_size)
        log.info("queue_client.connected", dsn=dsn.split("@")[-1])

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("QueueClient not connected — call connect() first")
        return self._pool

    async def enqueue(
        self,
        task_id: str,
        payload: dict[str, Any],
        priority: int = 1,
        executor: str = "claude",
        timeout_secs: int = 300,
        max_attempts: int = 3,
    ) -> str:
        """Insert a new job into the queue. Returns the job_id."""
        job_id = str(uuid.uuid4())
        await self.pool.execute(
            """
            INSERT INTO execution_queue
                (job_id, task_id, executor, priority, payload, timeout_secs, max_attempts)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
            """,
            job_id,
            task_id,
            executor,
            priority,
            json.dumps(payload),
            timeout_secs,
            max_attempts,
        )
        log.info("queue.enqueued", job_id=job_id, task_id=task_id, priority=priority)
        return job_id

    async def claim(self, executor_type: str, instance_id: str) -> dict[str, Any] | None:
        """Claim the highest-priority pending job. Returns None if queue empty.

        Uses FOR UPDATE SKIP LOCKED for safe concurrent access.
        """
        row = await self.pool.fetchrow(
            """
            UPDATE execution_queue
            SET status = 'claimed',
                claimed_by = $2,
                claimed_at = NOW(),
                heartbeat_at = NOW(),
                attempt = attempt + 1
            WHERE job_id = (
                SELECT job_id FROM execution_queue
                WHERE status = 'pending' AND executor = $1
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            executor_type,
            instance_id,
        )
        if row is None:
            return None
        return dict(row)

    async def heartbeat(self, job_id: str, instance_id: str) -> None:
        """Update heartbeat timestamp for a running job."""
        await self.pool.execute(
            """
            UPDATE execution_queue
            SET heartbeat_at = NOW(), status = 'running'
            WHERE job_id = $1 AND claimed_by = $2
            """,
            job_id,
            instance_id,
        )

    async def complete(self, job_id: str, result: dict[str, Any]) -> None:
        """Mark a job as completed with its result."""
        await self.pool.execute(
            """
            UPDATE execution_queue
            SET status = 'completed',
                completed_at = NOW(),
                result = $2::jsonb
            WHERE job_id = $1
            """,
            job_id,
            json.dumps(result),
        )
        log.info("queue.completed", job_id=job_id)

    async def fail(self, job_id: str, error: str) -> str:
        """Mark a job as failed. Returns final status ('pending' if retryable, else 'dead')."""
        row = await self.pool.fetchrow(
            "SELECT attempt, max_attempts FROM execution_queue WHERE job_id = $1",
            job_id,
        )
        if row is None:
            return "dead"

        if row["attempt"] >= row["max_attempts"]:
            await self.pool.execute(
                """
                UPDATE execution_queue
                SET status = 'dead', error = $2, completed_at = NOW()
                WHERE job_id = $1
                """,
                job_id,
                error,
            )
            log.warning("queue.dead", job_id=job_id, attempts=row["attempt"])
            return "dead"

        # Requeue for retry
        await self.pool.execute(
            """
            UPDATE execution_queue
            SET status = 'pending',
                error = $2,
                claimed_by = NULL,
                claimed_at = NULL,
                heartbeat_at = NULL
            WHERE job_id = $1
            """,
            job_id,
            error,
        )
        log.info("queue.requeued", job_id=job_id, attempt=row["attempt"])
        return "pending"

    async def reap_stale(self, ttl_secs: int = 300) -> int:
        """Reset jobs with expired heartbeats back to pending.

        Returns the number of reaped jobs.
        """
        result = await self.pool.execute(
            """
            UPDATE execution_queue
            SET status = 'pending',
                claimed_by = NULL,
                claimed_at = NULL,
                heartbeat_at = NULL
            WHERE status IN ('claimed', 'running')
              AND heartbeat_at < NOW() - ($1 || ' seconds')::INTERVAL
              AND attempt < max_attempts
            """,
            str(ttl_secs),
        )
        count = int(result.split()[-1])
        if count > 0:
            log.warning("queue.reaped_stale", count=count, ttl_secs=ttl_secs)
        return count

    async def stats(self) -> dict[str, int]:
        """Return counts grouped by status."""
        rows = await self.pool.fetch(
            "SELECT status, COUNT(*)::int AS count FROM execution_queue GROUP BY status"
        )
        return {row["status"]: row["count"] for row in rows}

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Fetch a single job by ID."""
        row = await self.pool.fetchrow(
            "SELECT * FROM execution_queue WHERE job_id = $1", job_id
        )
        if row is None:
            return None
        result = dict(row)
        # Serialize UUID and datetime for JSON response
        for key, val in result.items():
            if isinstance(val, uuid.UUID):
                result[key] = str(val)
            elif hasattr(val, "isoformat"):
                result[key] = val.isoformat()
        return result
