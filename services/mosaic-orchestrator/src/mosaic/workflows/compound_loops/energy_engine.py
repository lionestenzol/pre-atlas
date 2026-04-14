"""Pure-function energy engine for the Health/Energy agent.

All functions are pure: data in, result out. Zero I/O.
Handles energy logging, burnout detection, trend analysis, and recovery suggestions.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
from typing import Any


BURNOUT_THRESHOLD = 30       # energy_level below this for N days = burnout
BURNOUT_CONSECUTIVE_DAYS = 3 # days of low energy before burnout flag
RED_ALERT_ENERGY = 40        # below this + declining trend = red alert
TREND_WINDOW_DAYS = 7        # rolling average window


def log_energy_entry(
    log: dict[str, Any],
    date: str,
    energy_level: int,
    mental_load: int = 5,
    sleep_quality: int = 3,
    sleep_hours: float = 0,
    exercise_minutes: int = 0,
    notes: str = "",
    now_iso: str = "",
) -> dict[str, Any]:
    """Return new log with entry added. Immutable."""
    updated = copy.deepcopy(log)
    entries = updated.setdefault("entries", [])

    # Replace if same date exists
    entries = [e for e in entries if e.get("date") != date]

    entries.append({
        "date": date,
        "energy_level": max(0, min(100, energy_level)),
        "mental_load": max(1, min(10, mental_load)),
        "sleep_quality": max(1, min(5, sleep_quality)),
        "sleep_hours": max(0, min(24, sleep_hours)),
        "exercise_minutes": max(0, exercise_minutes),
        "notes": notes,
    })

    # Keep sorted by date, last 90 days
    entries.sort(key=lambda e: e.get("date", ""))
    updated["entries"] = entries[-90:]
    updated["generated_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    return updated


def detect_burnout(entries: list[dict[str, Any]], window_days: int = BURNOUT_CONSECUTIVE_DAYS) -> dict[str, Any]:
    """Detect burnout: N consecutive days with energy < threshold."""
    if len(entries) < window_days:
        return {"burnout_detected": False, "consecutive_low_days": 0}

    recent = entries[-window_days:]
    low_days = sum(1 for e in recent if e.get("energy_level", 50) < BURNOUT_THRESHOLD)
    consecutive = 0
    for e in reversed(recent):
        if e.get("energy_level", 50) < BURNOUT_THRESHOLD:
            consecutive += 1
        else:
            break

    return {
        "burnout_detected": consecutive >= window_days,
        "consecutive_low_days": consecutive,
        "low_days_in_window": low_days,
        "threshold": BURNOUT_THRESHOLD,
    }


def detect_trends(entries: list[dict[str, Any]], window_days: int = TREND_WINDOW_DAYS) -> dict[str, Any]:
    """Compute 7-day moving average and trend direction."""
    if not entries:
        return {"avg_energy": 50.0, "direction": "stable", "delta": 0.0}

    recent = entries[-window_days:] if len(entries) >= window_days else entries
    avg_energy = sum(e.get("energy_level", 50) for e in recent) / len(recent)

    # Compare first half vs second half for direction
    if len(recent) >= 4:
        mid = len(recent) // 2
        first_half = sum(e.get("energy_level", 50) for e in recent[:mid]) / mid
        second_half = sum(e.get("energy_level", 50) for e in recent[mid:]) / (len(recent) - mid)
        delta = second_half - first_half

        if delta > 5:
            direction = "improving"
        elif delta < -5:
            direction = "declining"
        else:
            direction = "stable"
    else:
        delta = 0.0
        direction = "stable"

    # Sleep and exercise averages
    avg_sleep = sum(e.get("sleep_hours", 0) for e in recent) / len(recent)
    avg_exercise = sum(e.get("exercise_minutes", 0) for e in recent) / len(recent)

    return {
        "avg_energy": round(avg_energy, 1),
        "direction": direction,
        "delta": round(delta, 1),
        "avg_sleep_hours": round(avg_sleep, 1),
        "avg_exercise_minutes": round(avg_exercise, 0),
        "data_points": len(recent),
    }


def predict_red_alert(entries: list[dict[str, Any]], now_iso: str) -> dict[str, Any]:
    """Predict interference window if energy is declining and below threshold."""
    if not entries:
        return {"red_alert": False, "reason": ""}

    trends = detect_trends(entries)
    latest_energy = entries[-1].get("energy_level", 50) if entries else 50

    if trends["direction"] == "declining" and latest_energy < RED_ALERT_ENERGY:
        return {
            "red_alert": True,
            "reason": f"Energy declining (delta {trends['delta']}) and below {RED_ALERT_ENERGY}",
            "predicted_low": max(0, latest_energy + trends["delta"]),
        }

    if latest_energy < BURNOUT_THRESHOLD:
        return {
            "red_alert": True,
            "reason": f"Energy at {latest_energy} — below burnout threshold",
            "predicted_low": latest_energy,
        }

    return {"red_alert": False, "reason": ""}


def suggest_recovery(
    energy_level: int,
    mental_load: int,
    trends: dict[str, Any],
) -> list[str]:
    """Actionable recovery suggestions based on current state and trends."""
    suggestions: list[str] = []

    if energy_level < 30:
        suggestions.append("Cancel non-essential meetings and deep work blocks")
        suggestions.append("Take a 20-minute nap or walk outside")
    elif energy_level < 50:
        suggestions.append("Reduce work blocks from 3 to 2 today")

    if mental_load >= 8:
        suggestions.append("Brain dump: write everything on your mind into a scratch file")
        suggestions.append("Defer complex decisions until mental load drops below 6")

    avg_sleep = trends.get("avg_sleep_hours", 0)
    if avg_sleep > 0 and avg_sleep < 6:
        suggestions.append(f"Sleep deficit detected (avg {avg_sleep}h) — target 7.5h tonight")

    avg_exercise = trends.get("avg_exercise_minutes", 0)
    if avg_exercise < 15:
        suggestions.append("No exercise detected — 15-minute walk boosts energy by ~20%")

    if trends.get("direction") == "declining":
        suggestions.append("Energy trending down — block tomorrow morning for recovery")

    if not suggestions:
        suggestions.append("Energy stable — maintain current rhythm")

    return suggestions


def compute_energy_health_signals(
    log: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Aggregate energy health signals for compound scoring."""
    entries = log.get("entries", [])

    if not entries:
        return {
            "burnout": {"burnout_detected": False, "consecutive_low_days": 0},
            "trends": {"avg_energy": 50.0, "direction": "stable", "delta": 0.0, "data_points": 0},
            "red_alert": {"red_alert": False, "reason": ""},
            "recovery_suggestions": ["No energy data — log your first entry"],
            "latest_energy": 50,
            "data_points": 0,
        }

    burnout = detect_burnout(entries)
    trends = detect_trends(entries)
    red_alert = predict_red_alert(entries, now_iso)

    latest = entries[-1]
    recovery = suggest_recovery(
        latest.get("energy_level", 50),
        latest.get("mental_load", 5),
        trends,
    )

    return {
        "burnout": burnout,
        "trends": trends,
        "red_alert": red_alert,
        "recovery_suggestions": recovery,
        "latest_energy": latest.get("energy_level", 50),
        "data_points": len(entries),
    }
