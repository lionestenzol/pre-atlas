"""Cortex — Atlas autonomous execution layer."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cortex.config import config
from cortex.clients.delta_client import DeltaClient
from cortex.clients.aegis_client import AegisClient
from cortex.clients.uasc_client import UascClient
from cortex.recovery import CircuitBreaker, StaleLockRecovery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cortex")

# Shared state
delta = DeltaClient()
aegis = AegisClient()
uasc = UascClient()

breakers = {
    "delta": CircuitBreaker(name="delta"),
    "aegis": CircuitBreaker(name="aegis"),
    "uasc": CircuitBreaker(name="uasc"),
}

_loop_task: asyncio.Task | None = None
_approval_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_task, _approval_task

    log.info("Cortex starting on :%d (instance=%s)", config.PORT, config.INSTANCE_ID)

    # Stale lock recovery on startup
    try:
        tasks = await delta.get_pending_tasks()
        released = await StaleLockRecovery.recover(delta, tasks)
        if released:
            log.info("Released %d stale locks", released)
    except Exception:
        log.warning("Stale lock recovery skipped — delta-kernel unreachable")

    # Start background loops (imported lazily to avoid circular deps)
    from cortex.loop import execution_loop, approval_poll_loop

    _loop_task = asyncio.create_task(execution_loop(delta, aegis, uasc, breakers))
    _approval_task = asyncio.create_task(approval_poll_loop(delta, aegis))

    yield

    # Shutdown
    if _loop_task:
        _loop_task.cancel()
    if _approval_task:
        _approval_task.cancel()
    await delta.close()
    await aegis.close()
    await uasc.close()
    log.info("Cortex shutdown complete")


app = FastAPI(title="Cortex", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    delta_ok = breakers["delta"].is_available
    aegis_ok = breakers["aegis"].is_available
    uasc_ok = breakers["uasc"].is_available
    return {
        "status": "ok" if all([delta_ok, aegis_ok]) else "degraded",
        "instance": config.INSTANCE_ID,
        "upstreams": {
            "delta": "available" if delta_ok else "circuit_open",
            "aegis": "available" if aegis_ok else "circuit_open",
            "uasc": "available" if uasc_ok else "circuit_open",
        },
        "timestamp": int(time.time() * 1000),
    }


@app.get("/status")
async def status():
    from cortex.loop import get_loop_status
    return get_loop_status()


@app.get("/tasks/recent")
async def recent_tasks():
    from cortex.loop import get_task_history
    return get_task_history()


@app.post("/tasks/submit")
async def submit_task(task: dict):
    """Accept a task directly (bypass delta-kernel queue for testing)."""
    from cortex.loop import enqueue_local_task
    task_id = await enqueue_local_task(task)
    return {"status": "queued", "task_id": task_id}


def start():
    import uvicorn
    uvicorn.run(
        "cortex.main:app",
        host="0.0.0.0",
        port=config.PORT,
        log_level="info",
    )


if __name__ == "__main__":
    start()
