"""Immutable data snapshot collector for compound feedback loops.

Gathers all cross-domain data into a frozen dataclass so loop computations
are pure functions with no I/O or side effects.
"""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from typing import Any

log = structlog.get_logger()


@dataclass(frozen=True)
class LoopResult:
    """Output of a single feedback loop computation."""

    fired: bool
    input_summary: str = ""
    output_summary: str = ""
    signal_delta: dict[str, Any] | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"fired": self.fired}
        if self.input_summary:
            result["input_summary"] = self.input_summary
        if self.output_summary:
            result["output_summary"] = self.output_summary
        if self.signal_delta:
            result["signal_delta"] = self.signal_delta
        if self.confidence < 1.0:
            result["confidence"] = self.confidence
        return result


@dataclass(frozen=True)
class CompoundSnapshot:
    """Immutable snapshot of all cross-domain data needed for compound computation."""

    daily_payload: dict[str, Any]
    governance_state: dict[str, Any]
    life_signals: dict[str, Any]
    completion_stats: dict[str, Any]
    closures: dict[str, Any]
    auto_actor_log: dict[str, Any]
    drift_alerts: dict[str, Any]
    extracted_value: dict[str, Any]
    classifications: dict[str, Any]
    strategic_priorities: dict[str, Any]
    prediction_results: dict[str, Any]
    idea_registry: dict[str, Any]
    delta_unified: dict[str, Any]
    energy_metrics: dict[str, Any]
    finance_metrics: dict[str, Any]
    skills_metrics: dict[str, Any]
    network_metrics: dict[str, Any]
    project_goals: dict[str, Any]
    skill_registry: dict[str, Any]
    analyst_decisions: dict[str, Any]
    financial_ledger: dict[str, Any]
    network_registry: dict[str, Any]
    energy_log: dict[str, Any]
    automation_queue: dict[str, Any]
    risk_state: dict[str, Any]


async def collect_snapshot(cognitive: Any, delta: Any) -> CompoundSnapshot:
    """Gather all data from all services into an immutable snapshot.

    File reads are synchronous (cognitive), HTTP is async (delta).
    All reads are best-effort: missing data returns dict with 'error' key.
    """
    # Async: delta-kernel unified state
    try:
        delta_unified = await delta.get_unified_state()
    except Exception as exc:
        log.warning("collector.delta_failed", error=str(exc))
        delta_unified = {"error": str(exc)}

    # Sync: cognitive-sensor file reads (all best-effort via _read_json)
    return CompoundSnapshot(
        daily_payload=cognitive.read_daily_payload(),
        governance_state=cognitive.read_governance_state(),
        life_signals=cognitive.read_life_signals(),
        completion_stats=cognitive.read_completion_stats(),
        closures=cognitive.read_closures(),
        auto_actor_log=cognitive.read_auto_actor_log(),
        drift_alerts=cognitive.read_drift_alerts(),
        extracted_value=cognitive.read_extracted_value(),
        classifications=cognitive.read_classifications(),
        strategic_priorities=cognitive.read_strategic_priorities(),
        prediction_results=cognitive.read_prediction_results(),
        idea_registry=cognitive.read_idea_registry(),
        delta_unified=delta_unified,
        energy_metrics=cognitive.read_brain_metrics("energy"),
        finance_metrics=cognitive.read_brain_metrics("finance"),
        skills_metrics=cognitive.read_brain_metrics("skills"),
        network_metrics=cognitive.read_brain_metrics("network"),
        project_goals=cognitive.read_project_goals(),
        skill_registry=cognitive.read_skill_registry(),
        analyst_decisions=cognitive.read_analyst_decisions(),
        financial_ledger=cognitive.read_financial_ledger(),
        network_registry=cognitive.read_network_registry(),
        energy_log=cognitive.read_energy_log(),
        automation_queue=cognitive.read_automation_queue(),
        risk_state=cognitive.read_risk_state(),
    )
