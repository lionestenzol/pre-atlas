"""Scheduler — the asyncio tick loop that runs every inPACT automation at cadence.

Runs as a background task alongside the existing Cortex execution loop.
Tick cadence is SCHEDULER_TICK_SECONDS (default 300s / 5min).

Cadence map (evaluated each tick against current local time):
  - signals.push_derived_signals       : every tick
  - pattern_breaker.run_pattern_check  : every tick
  - git_wins.log_commits_as_wins       : every 3rd tick (~15 min)
  - mode_actuator.apply_mode_actions   : every 6th tick (~30 min)
  - orchestrator.morning_plan          : first tick where hour == MORNING_HOUR
  - orchestrator.midday_check          : first tick where hour == MIDDAY_HOUR
  - orchestrator.evening_review        : first tick where hour == EVENING_HOUR
  - weekly_review.insert_weekly_draft  : Sunday, first tick where hour == EVENING_HOUR
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from cortex.config import config
from cortex.inpact.client import InpactClient
from cortex.inpact import (
    git_wins,
    mode_actuator,
    orchestrator,
    pattern_breaker,
    signals,
    weekly_review,
)

log = logging.getLogger("cortex.inpact.scheduler")


class InpactScheduler:
    def __init__(self) -> None:
        self.client = InpactClient()
        self.tick_count: int = 0
        self._stop = asyncio.Event()
        self.last_run: dict[str, Any] = {}

    async def stop(self) -> None:
        self._stop.set()
        await self.client.close()

    async def _safe(self, name: str, coro) -> None:
        try:
            result = await coro
            self.last_run[name] = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "result": result,
            }
        except Exception as e:
            log.warning("%s failed: %s", name, e)
            self.last_run[name] = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "error": str(e),
            }

    async def tick(self) -> None:
        self.tick_count += 1
        now = datetime.now()

        # Every tick
        await self._safe("signals", signals.push_derived_signals(self.client))
        await self._safe("pattern_breaker", pattern_breaker.run_pattern_check(self.client))

        # Every 3rd tick (~15 min)
        if self.tick_count % 3 == 0:
            await self._safe("git_wins", git_wins.log_commits_as_wins(self.client))

        # Every 6th tick (~30 min)
        if self.tick_count % 6 == 0:
            await self._safe("mode_actuator", mode_actuator.apply_mode_actions(self.client))

        # Time-of-day one-shots (idempotent-per-day inside each function)
        if now.hour == config.INPACT_MORNING_HOUR:
            await self._safe("morning_plan", orchestrator.morning_plan(self.client))
        if now.hour == config.INPACT_MIDDAY_HOUR:
            await self._safe("midday_check", orchestrator.midday_check(self.client))
        if now.hour == config.INPACT_EVENING_HOUR:
            await self._safe("evening_review", orchestrator.evening_review(self.client))
            if now.weekday() == 6:  # Sunday
                await self._safe("weekly_review", weekly_review.insert_weekly_draft(self.client))

    async def run(self) -> None:
        if not config.INPACT_ENABLED:
            log.info("inPACT scheduler disabled (INPACT_ENABLED=false)")
            return
        log.info(
            "inPACT scheduler starting (tick=%.0fs, morning=%dh, midday=%dh, evening=%dh)",
            config.INPACT_TICK_SECONDS,
            config.INPACT_MORNING_HOUR,
            config.INPACT_MIDDAY_HOUR,
            config.INPACT_EVENING_HOUR,
        )
        while not self._stop.is_set():
            start = time.monotonic()
            await self.tick()
            elapsed = time.monotonic() - start
            sleep_for = max(1.0, config.INPACT_TICK_SECONDS - elapsed)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                continue
