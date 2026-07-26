"""Stall Detector — detects 48h task stalls and generates cut lists.

Checks completion_stats.json for zero-completion weeks, then reads
governance_state for open loops to build a cut list.  Notifies via
OpenClaw when a stall is detected.
"""
import structlog
from datetime import datetime, timezone

from mosaic.clients.cognitive_client import CognitiveClient
from mosaic.clients.openclaw_client import OpenClawClient

log = structlog.get_logger()

# No completions in the current week = stall trigger
STALL_THRESHOLD_CLOSED = 0


async def detect_stalls(
    cognitive: CognitiveClient,
    openclaw: OpenClawClient,
    notify_channel: str = "default",
) -> dict:
    """Check for stalls and generate cut lists.

    A stall is defined as closed_week == 0 (no tasks closed this week).
    When detected:
      1. Read governance state for open loops
      2. Build cut list from lowest-priority open items
      3. Send notification via OpenClaw

    Returns a summary dict.
    """
    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stall_detected": False,
        "cut_list": [],
        "notified": False,
    }

    # Read completion stats
    stats = cognitive.read_daily_payload()
    if "error" in stats:
        # Fall back to reading completion_stats.json directly
        import json
        stats_path = cognitive.sensor_dir / "completion_stats.json"
        if stats_path.exists():
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
        else:
            log.warning("stall_detector.no_stats")
            result["error"] = "completion stats unavailable"
            return result

    closed_week = stats.get("closed_week", 0)
    if closed_week > STALL_THRESHOLD_CLOSED:
        log.info("stall_detector.no_stall", closed_week=closed_week)
        return result

    # Stall detected
    result["stall_detected"] = True
    log.warning("stall_detector.stall_detected", closed_week=closed_week)

    # Read governance state for open loops
    gov_state = cognitive.read_governance_state()
    open_loops = gov_state.get("open_loops", [])
    if isinstance(open_loops, int):
        open_loops = []  # numeric count, no detail available

    # Build cut list: suggest closing the oldest / lowest-priority items
    cut_list = []
    for loop in open_loops[:5]:  # Top 5 candidates
        if isinstance(loop, dict):
            cut_list.append({
                "id": loop.get("id", "unknown"),
                "title": loop.get("title", loop.get("topic", "untitled")),
                "age_days": loop.get("age_days", 0),
                "recommendation": "close" if loop.get("age_days", 0) > 14 else "review",
            })
    result["cut_list"] = cut_list

    # Notify via OpenClaw
    if cut_list:
        message = f"STALL ALERT: No tasks closed this week. Cut list ({len(cut_list)} items):\n"
        for item in cut_list:
            message += f"  - [{item['recommendation'].upper()}] {item['title']} ({item['age_days']}d old)\n"
    else:
        message = "STALL ALERT: No tasks closed this week. No specific cut candidates identified — review open loops."

    try:
        await openclaw.notify(channel=notify_channel, message=message, priority="high")
        result["notified"] = True
        log.info("stall_detector.notified", channel=notify_channel)
    except Exception as e:
        log.error("stall_detector.notify_failed", error=str(e))
        result["notify_error"] = str(e)

    return result
