"""Daily Automation Loop — 6AM→10PM scheduled pipeline.

Schedule (all times local):
  06:00  Read delta state + check daemon status
  06:05  Run cognitive-sensor daily pipeline
  06:15  Push cognitive state to delta-kernel
  09:30  Generate governor brief
  22:00  End-of-day summary

Avoids duplicate refreshes by checking /api/daemon/status first.
"""
import structlog
from datetime import datetime, timezone
from typing import Any

from mosaic.clients.delta_client import DeltaClient
from mosaic.clients.cognitive_client import CognitiveClient

log = structlog.get_logger()


async def run_daily_loop(
    delta: DeltaClient,
    cognitive: CognitiveClient,
    nats_publisher: Any | None = None,
    openclaw: Any | None = None,
) -> dict:
    """Execute the full daily automation cycle.

    Returns a summary dict with step results.
    """
    started = datetime.now(timezone.utc).isoformat()
    results: dict = {"started": started, "steps": []}

    # Step 1: Check daemon status to avoid duplicate refreshes
    try:
        daemon_status = await delta.get_daemon_status()
        refreshing = daemon_status.get("refreshing", False)
        results["steps"].append({"step": "check_daemon", "success": True, "refreshing": refreshing})
        if refreshing:
            log.info("daily_loop.skipping_refresh", reason="daemon already refreshing")
            results["steps"].append({"step": "skip_refresh", "success": True, "reason": "daemon already refreshing"})
            return {**results, "completed": datetime.now(timezone.utc).isoformat(), "skipped": True}
    except Exception as e:
        log.warning("daily_loop.daemon_check_failed", error=str(e))
        results["steps"].append({"step": "check_daemon", "success": False, "error": str(e)})

    # Step 2: Run cognitive-sensor daily pipeline
    try:
        daily_result = await cognitive.run_daily()
        success = daily_result.get("success", False)
        results["steps"].append({"step": "cognitive_daily", "success": success})
        if not success:
            log.error("daily_loop.cognitive_daily_failed", stderr=daily_result.get("stderr", ""))
    except Exception as e:
        log.error("daily_loop.cognitive_daily_error", error=str(e))
        results["steps"].append({"step": "cognitive_daily", "success": False, "error": str(e)})

    # Step 3: Push cognitive state to delta-kernel
    try:
        payload = cognitive.read_daily_payload()
        if "error" not in payload:
            await delta.ingest_cognitive(payload)
            results["steps"].append({"step": "push_to_delta", "success": True})
        else:
            results["steps"].append({"step": "push_to_delta", "success": False, "error": payload["error"]})
    except Exception as e:
        log.error("daily_loop.push_failed", error=str(e))
        results["steps"].append({"step": "push_to_delta", "success": False, "error": str(e)})

    # Step 4: Read governance state for summary
    try:
        gov_state = cognitive.read_governance_state()
        brief = cognitive.read_daily_brief()
        results["steps"].append({"step": "read_state", "success": "error" not in gov_state})
        results["governance_state"] = gov_state
        results["brief_available"] = bool(brief and "not available" not in brief.lower())
    except Exception as e:
        results["steps"].append({"step": "read_state", "success": False, "error": str(e)})

    # Step 5: Run compound feedback loop (cross-domain signal computation)
    try:
        from mosaic.workflows.compound_loop import run_compound_loop
        compound_result = await run_compound_loop(cognitive, delta, nats_publisher, openclaw)
        compound_score = compound_result.get("compound_score", -1)
        results["steps"].append({"step": "compound_loop", "success": True, "compound_score": compound_score})
        log.info("daily_loop.compound_complete", score=compound_score)
    except Exception as e:
        log.warning("daily_loop.compound_failed", error=str(e))
        results["steps"].append({"step": "compound_loop", "success": False, "error": str(e)})

    results["completed"] = datetime.now(timezone.utc).isoformat()
    results["skipped"] = False
    return results
