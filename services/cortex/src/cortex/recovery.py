"""Failure handling: circuit breaker and stale lock recovery."""

from __future__ import annotations

import time
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field

from cortex.config import config

log = logging.getLogger("cortex.recovery")


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Per-service circuit breaker.

    CLOSED  → normal operation
    OPEN    → all calls rejected (cooldown active)
    HALF_OPEN → one probe call allowed; success → CLOSED, failure → OPEN
    """

    name: str
    failure_threshold: int = config.CB_FAILURE_THRESHOLD
    cooldown_seconds: float = config.CB_COOLDOWN_SECONDS
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    last_failure_at: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def call(self, coro):
        """Wrap an async call with circuit breaker logic."""
        async with self._lock:
            if self.state == BreakerState.OPEN:
                elapsed = time.time() - self.last_failure_at
                if elapsed >= self.cooldown_seconds:
                    self.state = BreakerState.HALF_OPEN
                    log.info("[%s] breaker HALF_OPEN — probing", self.name)
                else:
                    remaining = self.cooldown_seconds - elapsed
                    raise CircuitOpenError(
                        f"{self.name} circuit OPEN — retry in {remaining:.0f}s"
                    )

        try:
            result = await coro
        except Exception as exc:
            async with self._lock:
                self.consecutive_failures += 1
                self.last_failure_at = time.time()
                if self.consecutive_failures >= self.failure_threshold:
                    self.state = BreakerState.OPEN
                    log.warning(
                        "[%s] breaker OPEN after %d failures",
                        self.name,
                        self.consecutive_failures,
                    )
                elif self.state == BreakerState.HALF_OPEN:
                    self.state = BreakerState.OPEN
                    log.warning("[%s] probe failed — back to OPEN", self.name)
            raise exc
        else:
            async with self._lock:
                if self.state == BreakerState.HALF_OPEN:
                    log.info("[%s] probe succeeded — breaker CLOSED", self.name)
                self.state = BreakerState.CLOSED
                self.consecutive_failures = 0
            return result

    @property
    def is_available(self) -> bool:
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.OPEN:
            return (time.time() - self.last_failure_at) >= self.cooldown_seconds
        return True  # HALF_OPEN allows one probe


class CircuitOpenError(Exception):
    pass


class StaleLockRecovery:
    """On startup, release tasks locked longer than 2x their timeout."""

    @staticmethod
    async def recover(delta_client, tasks: list[dict]) -> int:
        now_ms = int(time.time() * 1000)
        released = 0
        for task in tasks:
            if task.get("status") != "locked":
                continue
            locked_at = task.get("locked_at", 0)
            timeout_ms = task.get("constraints", {}).get("timeout_seconds", 300) * 1000
            threshold = timeout_ms * config.STALE_LOCK_MULTIPLIER
            if (now_ms - locked_at) > threshold:
                task_id = task["task_id"]
                retry_count = task.get("retry_count", 0) + 1
                log.warning(
                    "Releasing stale lock: task=%s locked_at=%d retry=%d",
                    task_id,
                    locked_at,
                    retry_count,
                )
                try:
                    await delta_client.update_task_status(
                        task_id,
                        "ready",
                        {"retry_count": retry_count, "released_by": "stale_lock_recovery"},
                    )
                    released += 1
                except Exception:
                    log.exception("Failed to release stale lock for %s", task_id)
        return released
