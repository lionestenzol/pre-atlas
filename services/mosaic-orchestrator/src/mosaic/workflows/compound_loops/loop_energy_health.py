"""Loop 12: Energy Health — burnout detection, trend analysis, recovery suggestions.

Reads the energy log, detects burnout patterns, predicts red alerts,
and auto-updates burnout_risk and red_alert_active signals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collector import CompoundSnapshot, LoopResult
from .energy_engine import compute_energy_health_signals


def compute_energy_health(snapshot: CompoundSnapshot) -> LoopResult:
    """Compute energy health from the energy log."""
    energy_log = snapshot.energy_log

    if "error" in energy_log:
        return LoopResult(
            fired=False,
            input_summary="energy_log.json not available",
            output_summary="Skipped — no energy log data",
        )

    entries = energy_log.get("entries", [])
    if not entries:
        return LoopResult(
            fired=True,
            input_summary="0 entries in energy log",
            output_summary="No energy history — log daily entries to enable trend detection",
            signal_delta={
                "energy_log_warning": "No energy entries logged. Track daily to enable burnout detection.",
            },
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_energy_health_signals(energy_log, now_iso)

    # Build signal delta — auto-updates energy signals
    signal_delta: dict[str, Any] = {
        "energy": {
            "burnout_risk": signals["burnout"]["burnout_detected"],
            "red_alert_active": signals["red_alert"]["red_alert"],
        },
        "energy_trends": {
            "direction": signals["trends"]["direction"],
            "avg_energy": signals["trends"]["avg_energy"],
            "delta": signals["trends"]["delta"],
            "avg_sleep_hours": signals["trends"].get("avg_sleep_hours", 0),
            "avg_exercise_minutes": signals["trends"].get("avg_exercise_minutes", 0),
        },
    }

    if signals["burnout"]["burnout_detected"]:
        signal_delta["burnout_alert"] = (
            f"Burnout detected: {signals['burnout']['consecutive_low_days']} consecutive low-energy days"
        )

    if signals["red_alert"]["red_alert"]:
        signal_delta["red_alert_reason"] = signals["red_alert"]["reason"]

    if signals["recovery_suggestions"]:
        signal_delta["recovery_suggestions"] = signals["recovery_suggestions"]

    # Build summaries
    input_summary = (
        f"{signals['data_points']} entries, "
        f"latest energy: {signals['latest_energy']}, "
        f"trend: {signals['trends']['direction']}"
    )

    output_parts = [
        f"Energy: {signals['latest_energy']}",
        f"Trend: {signals['trends']['direction']} ({signals['trends']['delta']:+.0f})",
    ]
    if signals["burnout"]["burnout_detected"]:
        output_parts.append("BURNOUT DETECTED")
    if signals["red_alert"]["red_alert"]:
        output_parts.append("RED ALERT")
    if signals["trends"].get("avg_sleep_hours", 0) > 0:
        output_parts.append(f"Sleep: {signals['trends']['avg_sleep_hours']}h avg")

    return LoopResult(
        fired=True,
        input_summary=input_summary,
        output_summary=" | ".join(output_parts),
        signal_delta=signal_delta,
    )
