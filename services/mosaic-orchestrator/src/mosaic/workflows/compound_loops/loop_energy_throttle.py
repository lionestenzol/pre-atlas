"""Loop 4: Energy → Execution Throttle.

When energy drops, reduce task load across ALL agents.
Broader than delta-kernel's mode downgrade — this adjusts governance targets.
"""
from __future__ import annotations

from typing import Any

from .collector import CompoundSnapshot, LoopResult

ENERGY_CRITICAL = 30   # below: 50% throttle
ENERGY_LOW = 50        # below: 25% throttle
MENTAL_LOAD_HIGH = 8   # above: 25% throttle


def compute_energy_throttle(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute execution throttle based on energy state.

    Reads:
        snapshot.energy_metrics — energy_level, mental_load, burnout_risk, red_alert_active
        snapshot.governance_state — targets (daily_work_blocks, max_research_minutes)
        snapshot.daily_payload — mode, risk

    Returns:
        LoopResult with throttle info and adjusted targets.
        Does NOT mutate governance_state — consumers check compound_state.
    """
    energy = snapshot.energy_metrics
    gov = snapshot.governance_state
    payload = snapshot.daily_payload

    if "error" in energy:
        return LoopResult(fired=False, input_summary="Missing energy_metrics")

    energy_level = energy.get("energy_level", 100)
    mental_load = energy.get("mental_load", 0)
    burnout_risk = energy.get("burnout_risk", False)
    red_alert = energy.get("red_alert_active", False)

    # Compute throttle percentage
    throttle_pct = 0
    reasons: list[str] = []

    if burnout_risk or red_alert:
        throttle_pct = 50
        reasons.append("burnout_risk" if burnout_risk else "red_alert_active")
    elif energy_level < ENERGY_CRITICAL:
        throttle_pct = 50
        reasons.append(f"energy={energy_level} < {ENERGY_CRITICAL}")
    elif energy_level < ENERGY_LOW:
        throttle_pct = 25
        reasons.append(f"energy={energy_level} < {ENERGY_LOW}")

    if mental_load > MENTAL_LOAD_HIGH and throttle_pct < 25:
        throttle_pct = 25
        reasons.append(f"mental_load={mental_load} > {MENTAL_LOAD_HIGH}")

    if throttle_pct == 0:
        return LoopResult(
            fired=False,
            input_summary=f"energy={energy_level}, load={mental_load}, burnout={burnout_risk}",
        )

    # Adjust governance targets
    targets = gov.get("targets", {}) if "error" not in gov else {}
    daily_blocks = targets.get("daily_work_blocks", 4)
    max_research = targets.get("max_research_minutes", 60)

    multiplier = 1 - (throttle_pct / 100)
    adjusted_blocks = max(1, round(daily_blocks * multiplier))
    adjusted_research = max(15, round(max_research * multiplier))

    mode = payload.get("mode", "UNKNOWN") if "error" not in payload else "UNKNOWN"

    constraints: list[dict[str, str]] = [
        {
            "source_domain": "energy",
            "target_domain": "ALL",
            "constraint": f"{throttle_pct}% throttle: {', '.join(reasons)}",
            "severity": "HIGH" if throttle_pct >= 50 else "MEDIUM",
        }
    ]

    signal_delta = {
        "throttle_pct": throttle_pct,
        "adjusted_targets": {
            "daily_work_blocks": adjusted_blocks,
            "max_research_minutes": adjusted_research,
        },
        "reasons": reasons,
        "constraints": constraints,
    }

    return LoopResult(
        fired=True,
        input_summary=f"energy={energy_level}, load={mental_load}, burnout={burnout_risk}, mode={mode}",
        output_summary=f"{throttle_pct}% throttle. Blocks: {daily_blocks}→{adjusted_blocks}, Research: {max_research}→{adjusted_research}min",
        signal_delta=signal_delta,
        confidence=0.9,  # Energy state is directly measurable
    )
