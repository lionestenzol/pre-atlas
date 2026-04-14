"""Cross-Agent Compound Feedback Loop — main orchestrator.

Reads outputs from ALL Pre Atlas services, computes cross-domain compound signals,
feeds them back into the signal pipeline, publishes NATS events, and generates
an actionable compound brief.

Usage:
    result = await run_compound_loop(cognitive, delta, publisher, openclaw)
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Any

from .compound_loops.collector import CompoundSnapshot, LoopResult, collect_snapshot
from .compound_loops.loop_closure_skill import compute_closure_to_skill
from .compound_loops.loop_skill_network import compute_skill_to_network
from .compound_loops.loop_completion_finance import compute_completion_to_finance
from .compound_loops.loop_energy_throttle import compute_energy_throttle
from .compound_loops.loop_risk_cascade import compute_risk_cascade
from .compound_loops.loop_compound_score import compute_compound_score
from .compound_loops.loop_project_health import compute_project_health
from .compound_loops.loop_skill_health import compute_skill_health
from .compound_loops.loop_analyst import compute_analyst_decisions
from .compound_loops.loop_finance_health import compute_finance_health
from .compound_loops.loop_network_health import compute_network_health
from .compound_loops.loop_energy_health import compute_energy_health
from .compound_loops.loop_automation_health import compute_automation_health
from .compound_loops.loop_risk_mitigation import compute_risk_mitigation
from .compound_loops.brief_generator import generate_compound_brief

log = structlog.get_logger()


async def run_compound_loop(
    cognitive: Any,
    delta: Any,
    publisher: Any | None = None,
    openclaw: Any | None = None,
) -> dict[str, Any]:
    """Execute the full compound feedback loop.

    Steps:
        1. Collect immutable snapshot from all services
        2. Run 6 loops (pure computation, no I/O)
        3. Compute compound score
        4. Generate compound brief
        5. Write compound_state.json to brain/
        6. Push signal updates via signal_ingest
        7. Publish NATS events for each fired loop
        8. Notify via OpenClaw if compound_score < 30

    Args:
        cognitive: CognitiveClient instance
        delta: DeltaClient instance
        publisher: Optional NatsPublisher for real-time events
        openclaw: Optional OpenClawClient for critical alerts

    Returns:
        CompoundState dict (also written to brain/compound_state.json)
    """
    started = datetime.now(timezone.utc)
    log.info("compound_loop.start")

    # Step 1: Collect snapshot
    snapshot = await collect_snapshot(cognitive, delta)
    log.info("compound_loop.snapshot_collected")

    # Step 2: Run all 6 loops
    loop_results: dict[str, LoopResult] = {}

    loop_results["project_health"] = compute_project_health(snapshot)
    loop_results["skill_health"] = compute_skill_health(snapshot)
    loop_results["finance_health"] = compute_finance_health(snapshot)
    loop_results["network_health"] = compute_network_health(snapshot)
    loop_results["energy_health"] = compute_energy_health(snapshot)
    loop_results["automation_health"] = compute_automation_health(snapshot)
    loop_results["closure_to_skill"] = compute_closure_to_skill(snapshot)
    loop_results["skill_to_network"] = compute_skill_to_network(snapshot)
    loop_results["completion_to_finance"] = compute_completion_to_finance(snapshot)
    loop_results["energy_to_throttle"] = compute_energy_throttle(snapshot)
    loop_results["risk_cascade"] = compute_risk_cascade(snapshot)

    fired_count = sum(1 for r in loop_results.values() if r.fired)
    log.info("compound_loop.loops_computed", fired=fired_count, total=len(loop_results))

    # Step 3: Compound score
    compound_score, domain_scores = compute_compound_score(snapshot, loop_results)
    loop_results["compound_score"] = LoopResult(
        fired=True,
        input_summary=f"{len(domain_scores)} domains scored",
        output_summary=f"Compound score: {compound_score}/100",
        signal_delta={"compound_score": compound_score, "domain_scores": domain_scores},
    )

    # Step 3b: Risk mitigation (runs AFTER score, needs compound_score + domain_scores)
    loop_results["risk_mitigation"] = compute_risk_mitigation(snapshot, compound_score, domain_scores)

    # Step 3c: Analyst decisions (runs LAST, needs domain_scores)
    loop_results["analyst"] = compute_analyst_decisions(snapshot, domain_scores)

    # Step 4: Generate brief
    brief = generate_compound_brief(snapshot, loop_results, compound_score, domain_scores)

    # Step 5: Build and write compound state
    all_constraints: list[dict[str, str]] = []
    signal_updates: dict[str, Any] = {}

    for result in loop_results.values():
        if result.signal_delta:
            if "constraints" in result.signal_delta:
                all_constraints.extend(result.signal_delta["constraints"])
            if "skills" in result.signal_delta:
                signal_updates["skills"] = result.signal_delta["skills"]
            if "skills_from_subtasks" in result.signal_delta:
                signal_updates["skills_from_subtasks"] = result.signal_delta["skills_from_subtasks"]
            if "skill_usage_update" in result.signal_delta:
                signal_updates["skill_usage_update"] = result.signal_delta["skill_usage_update"]
            if "network" in result.signal_delta:
                signal_updates["network"] = result.signal_delta["network"]
            if "risk_mitigation" in result.signal_delta:
                signal_updates["risk_mitigation"] = result.signal_delta["risk_mitigation"]
            if "analyst_decisions" in result.signal_delta:
                signal_updates["analyst_decisions"] = result.signal_delta["analyst_decisions"]
                signal_updates["analyst_stats"] = result.signal_delta.get("analyst_stats", {})

    compound_state: dict[str, Any] = {
        "schema_version": "1.0.0",
        "generated_at": started.isoformat(),
        "compound_score": compound_score,
        "domain_scores": {k: round(v, 1) for k, v in domain_scores.items()},
        "loops": {k: v.to_dict() for k, v in loop_results.items()},
        "active_constraints": all_constraints,
        "compound_brief": brief,
        "signal_updates": signal_updates,
    }

    # Emit state update task to delta for daemon execution
    try:
        await delta.request_work({
            "type": "system",
            "title": "compound-loop-state-update",
            "metadata": {
                "cmd": "@WORK",
                "inputs": {
                    "handler": "compound_state_update",
                    "compound_state": compound_state,
                    "signal_updates": signal_updates,
                },
                "source": "orchestrator",
                "intent": "update_state",
                "priority": 1,
            }
        })
        log.info("compound_loop.state_emitted_to_delta")
    except Exception as exc:
        log.error("compound_loop.delta_emit_failed", error=str(exc))

    # Step 7: Publish NATS events
    if publisher:
        await _publish_events(publisher, loop_results, compound_score, domain_scores)

    # Step 8: Critical alert
    if openclaw and compound_score < 30:
        try:
            await openclaw.notify(
                channel="default",
                message=f"COMPOUND ALERT: Score {compound_score}/100. {brief.split('### Leverage Move')[1].strip() if '### Leverage Move' in brief else 'Check compound state.'}",
                priority="high",
            )
            log.info("compound_loop.critical_alert_sent", score=compound_score)
        except Exception as exc:
            log.warning("compound_loop.notify_failed", error=str(exc))

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    log.info("compound_loop.complete", score=compound_score, fired=fired_count, elapsed_s=round(elapsed, 2))

    return compound_state
async def _publish_events(
    publisher: Any,
    loop_results: dict[str, LoopResult],
    compound_score: int,
    domain_scores: dict[str, float],
) -> None:
    """Publish NATS events for each fired loop."""
    topic_map = {
        "project_health": "compound.project_health",
        "skill_health": "compound.skill_health",
        "analyst": "compound.analyst",
        "finance_health": "compound.finance_health",
        "network_health": "compound.network_health",
        "energy_health": "compound.energy_health",
        "automation_health": "compound.automation_health",
        "risk_mitigation": "compound.risk_mitigation",
        "closure_to_skill": "compound.closure_to_skill",
        "skill_to_network": "compound.skill_to_network",
        "completion_to_finance": "compound.completion_to_finance",
        "energy_to_throttle": "compound.energy_throttle",
        "risk_cascade": "compound.risk_cascade",
    }

    for loop_name, result in loop_results.items():
        if result.fired and loop_name in topic_map:
            try:
                await publisher.publish(topic_map[loop_name], result.to_dict())
            except Exception as exc:
                log.warning("compound_loop.publish_failed", topic=topic_map[loop_name], error=str(exc))

    # Always publish score update
    try:
        critical_domains = [k for k, v in domain_scores.items() if v < 30]
        await publisher.publish("compound.score_updated", {
            "compound_score": compound_score,
            "domain_scores": {k: round(v, 1) for k, v in domain_scores.items()},
            "critical_domains": critical_domains,
        })
    except Exception as exc:
        log.warning("compound_loop.publish_score_failed", error=str(exc))
