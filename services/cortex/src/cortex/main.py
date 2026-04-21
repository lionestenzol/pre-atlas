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
_inpact_scheduler = None
_inpact_task: asyncio.Task | None = None


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

    # inPACT scheduler (Pattern Breaker, Git Wins, Mode Actuator, Orchestrator, Weekly Review)
    global _inpact_scheduler, _inpact_task
    if config.INPACT_ENABLED:
        from cortex.inpact.scheduler import InpactScheduler
        _inpact_scheduler = InpactScheduler()
        _inpact_task = asyncio.create_task(_inpact_scheduler.run())

    yield

    # Shutdown
    if _loop_task:
        _loop_task.cancel()
    if _approval_task:
        _approval_task.cancel()
    if _inpact_task:
        _inpact_task.cancel()
    if _inpact_scheduler:
        await _inpact_scheduler.stop()
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


@app.get("/inpact/status")
async def inpact_status():
    """Last-run summary for each inPACT automation."""
    if not _inpact_scheduler:
        return {"enabled": False, "reason": "scheduler_not_started"}
    return {
        "enabled": True,
        "tick_count": _inpact_scheduler.tick_count,
        "tick_seconds": config.INPACT_TICK_SECONDS,
        "last_run": _inpact_scheduler.last_run,
    }


@app.post("/inpact/run/{module}")
async def inpact_run(module: str):
    """Manually fire an inPACT automation module (useful for testing)."""
    if not _inpact_scheduler:
        return {"ok": False, "error": "scheduler_not_started"}
    client = _inpact_scheduler.client
    from cortex.inpact import (
        git_wins, mode_actuator, orchestrator,
        pattern_breaker, signals, weekly_review,
    )
    fns = {
        "signals": lambda: signals.push_derived_signals(client),
        "pattern_breaker": lambda: pattern_breaker.run_pattern_check(client),
        "git_wins": lambda: git_wins.log_commits_as_wins(client),
        "mode_actuator": lambda: mode_actuator.apply_mode_actions(client),
        "morning_plan": lambda: orchestrator.morning_plan(client),
        "midday_check": lambda: orchestrator.midday_check(client),
        "evening_review": lambda: orchestrator.evening_review(client),
        "weekly_review": lambda: weekly_review.insert_weekly_draft(client, force=True),
    }
    if module not in fns:
        return {"ok": False, "error": f"unknown module: {module}", "available": list(fns.keys())}
    try:
        result = await fns[module]()
        return {"ok": True, "module": module, "result": result}
    except Exception as e:
        return {"ok": False, "module": module, "error": str(e)}


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
