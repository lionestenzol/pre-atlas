"""Daily cron scheduler — posts briefs and detects stalls."""
import asyncio
import structlog
import httpx
from datetime import datetime, timezone

from openclaw.config import config

log = structlog.get_logger()


class DailyScheduler:
    """Schedule daily briefs and CLOSURE stall detection."""

    def __init__(self, channels: list = None):
        self.channels = channels or []
        self._running = False
        self._task: asyncio.Task | None = None

    async def _post_to_all(self, text: str) -> int:
        """Send a message to all connected channels. Returns success count."""
        sent = 0
        for ch in self.channels:
            if ch.connected:
                try:
                    ok = await ch.send_message(text)
                    if ok:
                        sent += 1
                except Exception as e:
                    log.warning("scheduler.channel_error", channel=ch.channel_type, error=str(e))
        return sent

    async def post_daily_brief(self) -> str:
        """Fetch and post daily brief to all channels."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{config.cognitive_url}/api/v1/brief")
                resp.raise_for_status()
                brief = resp.json().get("brief", "No brief available.")
        except Exception as e:
            brief = f"Could not fetch daily brief: {e}"
            log.warning("scheduler.brief_fetch_failed", error=str(e))

        text = f"*Daily Brief — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*\n\n{brief}"
        sent = await self._post_to_all(text)
        log.info("scheduler.brief_posted", channels=sent)
        return text

    async def check_closure_stall(self) -> str | None:
        """Check if CLOSURE mode has stalled (no completions in threshold hours)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{config.orchestrator_url}/api/v1/status")
                resp.raise_for_status()
                data = resp.json()

            if data.get("mode") != "CLOSURE":
                return None

            # Check last completion time
            last_completion = data.get("last_completion_at")
            if not last_completion:
                return None

            last_dt = datetime.fromisoformat(last_completion)
            hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600

            if hours_since > config.stall_threshold_hours:
                msg = (
                    f"*CLOSURE Stall Detected*\n"
                    f"No completions in {hours_since:.0f}h (threshold: {config.stall_threshold_hours}h).\n"
                    f"Consider trimming scope or switching to MAINTENANCE."
                )
                await self._post_to_all(msg)
                return msg
        except Exception as e:
            log.warning("scheduler.stall_check_failed", error=str(e))
        return None

    async def run_daily_cycle(self):
        """Run both brief and stall check (called by scheduler)."""
        await self.post_daily_brief()
        await self.check_closure_stall()

    def get_cron_config(self) -> dict:
        """Return APScheduler cron trigger config for daily brief."""
        return {
            "hour": config.brief_cron_hour,
            "minute": config.brief_cron_minute,
        }
