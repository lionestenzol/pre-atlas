"""Idea-to-Simulation Workflow — auto-routes high-alignment ideas to MiroFish.

When an idea has alignment > 0.7, it gets submitted to MiroFish for
swarm simulation.  Results are routed by confidence:
  - confidence > 0.8  → create Festival task
  - 0.5 < conf < 0.8  → post to OpenClaw for human review
  - confidence < 0.5   → archive (no action)
"""
import json
import structlog
from datetime import datetime, timezone

from mosaic.clients.cognitive_client import CognitiveClient
from mosaic.clients.mirofish_client import MirofishClient
from mosaic.clients.openclaw_client import OpenClawClient

log = structlog.get_logger()

ALIGNMENT_THRESHOLD = 0.7


async def find_eligible_ideas(cognitive: CognitiveClient) -> list[dict]:
    """Scan idea_registry.json for ideas with alignment > threshold."""
    registry_path = cognitive.sensor_dir / "idea_registry.json"
    if not registry_path.exists():
        log.warning("idea_simulation.no_registry")
        return []

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    eligible = []

    # Scan execute_now and next_up tiers for high-alignment ideas
    for tier_name in ("execute_now", "next_up"):
        tier_ideas = registry.get("tiers", {}).get(tier_name, [])
        for idea in tier_ideas:
            alignment = idea.get("alignment_score", 0)
            if alignment >= ALIGNMENT_THRESHOLD:
                eligible.append({
                    "canonical_id": idea.get("canonical_id", ""),
                    "title": idea.get("canonical_title", "untitled"),
                    "alignment_score": alignment,
                    "category": idea.get("category", "unknown"),
                    "complexity": idea.get("complexity", "unknown"),
                })

    log.info("idea_simulation.eligible", count=len(eligible))
    return eligible


async def run_idea_to_simulation(
    cognitive: CognitiveClient,
    mirofish: MirofishClient,
    openclaw: OpenClawClient,
    notify_channel: str = "default",
) -> dict:
    """Execute the full idea-to-simulation pipeline.

    Returns a summary with simulation results and routing decisions.
    """
    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ideas_scanned": 0,
        "simulations_started": 0,
        "routing_decisions": [],
    }

    # Find eligible ideas
    eligible = await find_eligible_ideas(cognitive)
    result["ideas_scanned"] = len(eligible)

    if not eligible:
        return result

    for idea in eligible:
        sim_result = {"idea_id": idea["canonical_id"], "title": idea["title"]}

        # Start simulation
        try:
            sim = await mirofish.start_simulation(
                topic=idea["title"],
                agent_count=20,
                tick_count=10,
            )
            sim_id = sim.get("simulation_id", sim.get("id", ""))
            sim_result["simulation_id"] = sim_id
            result["simulations_started"] += 1
            log.info("idea_simulation.started", idea=idea["canonical_id"], sim_id=sim_id)

            # Get report (simulation runs synchronously in MiroFish)
            report = await mirofish.get_report(sim_id)
            confidence = report.get("confidence", report.get("consensus_score", 0))
            sim_result["confidence"] = confidence

            # Route by confidence
            if confidence > 0.8:
                sim_result["action"] = "create_festival_task"
                log.info("idea_simulation.high_confidence", idea=idea["canonical_id"], confidence=confidence)
            elif confidence > 0.5:
                sim_result["action"] = "notify_for_review"
                try:
                    await openclaw.notify(
                        channel=notify_channel,
                        message=f"Idea '{idea['title']}' simulated with moderate confidence ({confidence:.2f}). Review recommended.",
                    )
                except Exception as e:
                    log.warning("idea_simulation.notify_failed", error=str(e))
            else:
                sim_result["action"] = "archive"
                log.info("idea_simulation.low_confidence", idea=idea["canonical_id"], confidence=confidence)

        except Exception as e:
            sim_result["error"] = str(e)
            sim_result["action"] = "failed"
            log.error("idea_simulation.failed", idea=idea["canonical_id"], error=str(e))

        result["routing_decisions"].append(sim_result)

    return result
