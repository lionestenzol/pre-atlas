"""Skill: /status — returns current mode, risk, and open-loop state."""
import structlog

from openclaw.delta import fetch_delta_derived
from openclaw.channels.base import Message

log = structlog.get_logger()


async def handle_status(message: Message) -> str:
    """Fetch governance state from delta-kernel and format for messaging."""
    try:
        derived = await fetch_delta_derived()

        mode = derived.get("mode", "UNKNOWN")
        risk = derived.get("risk", "UNKNOWN")
        build = "allowed" if derived.get("build_allowed") else "blocked"
        open_loops = derived.get("open_loops", 0)
        streak = derived.get("streak_days", 0)

        return (
            f"*System Status*\n"
            f"Mode: `{mode}`\n"
            f"Risk: `{risk}`\n"
            f"Build: {build}\n"
            f"Open loops: {open_loops}\n"
            f"Streak: {streak}d"
        )
    except Exception as e:
        log.warning("skill.status_failed", error=str(e))
        return f"Could not fetch status: {e}"
