"""
Drift Detector — detects behavioral drift patterns from daily_snapshots.

Outputs drift_alerts.json with active alerts and a composite drift_score.
Requires at least 3 days of snapshots to produce meaningful output.
"""

import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.resolve()


def _load_config():
    cfg_path = BASE / "governance_config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        return cfg.get("drift_detection", {})
    return {}


def detect_drift(snapshots):
    """
    Given list of snapshot dicts (oldest first), detect drift patterns.
    Returns list of alert dicts.
    """
    cfg = _load_config()
    drought_threshold = cfg.get("closure_drought_days", 5)
    gaming_quality_threshold = cfg.get("archive_gaming_quality_threshold", 30.0)
    stagnation_days = cfg.get("mode_stagnation_days", 14)

    alerts = []

    if len(snapshots) < 3:
        return alerts

    # Sort by date ascending
    snaps = sorted(snapshots, key=lambda x: x.get("date", ""))

    # --- Check 1: closure drought ---
    consecutive_no_close = 0
    for snap in reversed(snaps):
        if (snap.get("closures_today") or 0) == 0:
            consecutive_no_close += 1
        else:
            break

    if consecutive_no_close >= drought_threshold:
        alerts.append({
            "type": "closure_drought",
            "severity": "HIGH",
            "message": f"No closures for {consecutive_no_close} consecutive days. You are stuck.",
            "days": consecutive_no_close,
        })

    # --- Check 2: archive gaming ---
    consecutive_low_quality = 0
    for snap in reversed(snaps):
        cq = snap.get("closure_quality")
        if cq is not None and cq < gaming_quality_threshold:
            consecutive_low_quality += 1
        else:
            break

    if consecutive_low_quality >= 3:
        alerts.append({
            "type": "archive_gaming",
            "severity": "HIGH",
            "message": (
                f"Closure quality below {gaming_quality_threshold:.0f}% for {consecutive_low_quality} days. "
                f"You are archiving loops, not closing them. Archiving doesn't count."
            ),
            "days": consecutive_low_quality,
        })

    # --- Check 3: energy drought (consecutive low-energy days) ---
    energy_drought_threshold = cfg.get("energy_drought_days", 3)
    consecutive_low_energy = 0
    for snap in reversed(snaps):
        el = snap.get("energy_level")
        if el is not None and el < 30:
            consecutive_low_energy += 1
        elif el is not None:
            break
        # Skip days with no energy data

    if consecutive_low_energy >= energy_drought_threshold:
        alerts.append({
            "type": "energy_drought",
            "severity": "HIGH",
            "message": (
                f"Energy below 30 for {consecutive_low_energy} consecutive days. "
                f"Burnout risk is real. Schedule recovery before execution."
            ),
            "days": consecutive_low_energy,
        })

    # --- Check 4: energy-productivity correlation ---
    # If energy is consistently low but closures are happening, flag overexertion
    recent_5 = snaps[-5:] if len(snaps) >= 5 else snaps
    low_energy_closures = sum(
        1 for s in recent_5
        if (s.get("energy_level") or 50) < 30 and (s.get("closures_today") or 0) > 0
    )
    if low_energy_closures >= 3:
        alerts.append({
            "type": "overexertion",
            "severity": "MEDIUM",
            "message": (
                f"Closing loops while energy is depleted ({low_energy_closures} of last 5 days). "
                f"Quality suffers under fatigue. Rest produces better output."
            ),
            "days": low_energy_closures,
        })

    # --- Check 5: mode stagnation ---
    if len(snaps) >= stagnation_days:
        recent = snaps[-stagnation_days:]
        modes = [s.get("mode") for s in recent if s.get("mode")]
        if modes and len(set(modes)) == 1:
            alerts.append({
                "type": "mode_stagnation",
                "severity": "MEDIUM",
                "message": (
                    f"Stuck in {modes[0]} mode for {stagnation_days}+ days. "
                    f"The system has not changed state. Something needs to move."
                ),
                "days": stagnation_days,
            })

    return alerts


def compute_drift_score(alerts):
    """
    Composite drift score 0–10.
    HIGH alerts contribute 4 each, MEDIUM 2 each, capped at 10.
    """
    score = 0
    for alert in alerts:
        if alert.get("severity") == "HIGH":
            score += 4
        elif alert.get("severity") == "MEDIUM":
            score += 2
    return min(score, 10)


def main():
    from behavioral_memory import get_rolling_context
    snapshots = get_rolling_context(14)

    alerts = detect_drift(snapshots)
    drift_score = compute_drift_score(alerts)

    output = {
        "generated_at": datetime.now().isoformat(),
        "drift_score": drift_score,
        "alerts": alerts,
        "snapshot_days_available": len(snapshots),
    }

    out_path = BASE / "drift_alerts.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    if alerts:
        print(f"[drift_detector] drift_score={drift_score}/10, {len(alerts)} alert(s):")
        for a in alerts:
            print(f"  [{a['severity']}] {a['type']}: {a['message']}")
    else:
        if len(snapshots) < 3:
            print(f"[drift_detector] Only {len(snapshots)} snapshot(s) — need 3+ for drift detection. Score=0.")
        else:
            print(f"[drift_detector] No drift detected. Score=0.")

    return output


if __name__ == "__main__":
    main()
