"""
Signal Ingest — Multi-domain life signal API endpoints.

Accepts POST payloads for energy, finance, skills, and network signals.
Writes to life_signals.json (consumed by CycleBoard + delta-kernel).
Also stores daily signals in behavioral_memory daily_snapshots table.

Endpoints:
  POST /api/signals/energy   — { energy_level, mental_load, sleep_quality, burnout_risk, red_alert_active }
  POST /api/signals/finance  — { runway_months, monthly_income, monthly_expenses }
  POST /api/signals/skills   — { utilization_pct, active_learning, mastery_count, growth_count }
  POST /api/signals/network  — { collaboration_score, active_relationships, outreach_this_week }
  POST /api/signals/bulk     — { energy: {...}, finance: {...}, skills: {...}, network: {...} }
  GET  /api/signals          — returns current life_signals.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
SIGNALS_FILE = BASE / "life_signals.json"
BRAIN_DIR = BASE / "cycleboard" / "brain"


def _load_signals() -> dict[str, Any]:
    if SIGNALS_FILE.exists():
        return json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    return _default_signals()


def _default_signals() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "energy": {
            "energy_level": 50,
            "mental_load": 5,
            "sleep_quality": 3,
            "burnout_risk": False,
            "red_alert_active": False,
        },
        "finance": {
            "runway_months": 3.0,
            "monthly_income": 0,
            "monthly_expenses": 0,
            "money_delta": 0,
        },
        "skills": {
            "utilization_pct": 50.0,
            "active_learning": False,
            "mastery_count": 0,
            "growth_count": 0,
        },
        "network": {
            "collaboration_score": 30,
            "active_relationships": 0,
            "outreach_this_week": 0,
        },
        "life_phase": 1,
    }


def _save_signals(signals: dict[str, Any]) -> None:
    signals["generated_at"] = datetime.now().isoformat()
    SIGNALS_FILE.write_text(
        json.dumps(signals, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Also write to brain dir for CycleBoard consumption
    _sync_brain_files(signals)
    log.info("Saved life_signals.json (updated %s)", signals["generated_at"])


def _sync_brain_files(signals: dict[str, Any]) -> None:
    """Write domain-specific brain files for CycleBoard screens."""
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)

    for domain in ("energy", "finance", "skills", "network"):
        data = signals.get(domain, {})
        brain_file = BRAIN_DIR / f"{domain}_metrics.json"
        payload = {
            "generated_at": signals["generated_at"],
            "life_phase": signals.get("life_phase", 1),
            **data,
        }
        brain_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# === PUBLIC API ===


def update_energy(data: dict[str, Any]) -> dict[str, Any]:
    signals = _load_signals()
    energy = signals["energy"]

    if "energy_level" in data:
        energy["energy_level"] = int(_clamp(data["energy_level"], 0, 100))
    if "mental_load" in data:
        energy["mental_load"] = int(_clamp(data["mental_load"], 1, 10))
    if "sleep_quality" in data:
        energy["sleep_quality"] = int(_clamp(data["sleep_quality"], 1, 5))
    if "burnout_risk" in data:
        energy["burnout_risk"] = bool(data["burnout_risk"])
    if "red_alert_active" in data:
        energy["red_alert_active"] = bool(data["red_alert_active"])

    _save_signals(signals)
    return signals


def update_finance(data: dict[str, Any]) -> dict[str, Any]:
    signals = _load_signals()
    fin = signals["finance"]

    if "runway_months" in data:
        fin["runway_months"] = max(0.0, float(data["runway_months"]))
    if "monthly_income" in data:
        fin["monthly_income"] = max(0, float(data["monthly_income"]))
    if "monthly_expenses" in data:
        fin["monthly_expenses"] = max(0, float(data["monthly_expenses"]))

    fin["money_delta"] = fin["monthly_income"] - fin["monthly_expenses"]
    _save_signals(signals)
    return signals


def update_skills(data: dict[str, Any]) -> dict[str, Any]:
    signals = _load_signals()
    sk = signals["skills"]

    if "utilization_pct" in data:
        sk["utilization_pct"] = float(_clamp(data["utilization_pct"], 0, 100))
    if "active_learning" in data:
        sk["active_learning"] = bool(data["active_learning"])
    if "mastery_count" in data:
        sk["mastery_count"] = max(0, int(data["mastery_count"]))
    if "growth_count" in data:
        sk["growth_count"] = max(0, int(data["growth_count"]))

    _save_signals(signals)
    return signals


def update_network(data: dict[str, Any]) -> dict[str, Any]:
    signals = _load_signals()
    net = signals["network"]

    if "collaboration_score" in data:
        net["collaboration_score"] = int(_clamp(data["collaboration_score"], 0, 100))
    if "active_relationships" in data:
        net["active_relationships"] = max(0, int(data["active_relationships"]))
    if "outreach_this_week" in data:
        net["outreach_this_week"] = max(0, int(data["outreach_this_week"]))

    _save_signals(signals)
    return signals


def update_bulk(data: dict[str, Any]) -> dict[str, Any]:
    """Accept partial updates across all domains at once."""
    if "energy" in data:
        update_energy(data["energy"])
    if "finance" in data:
        update_finance(data["finance"])
    if "skills" in data:
        update_skills(data["skills"])
    if "network" in data:
        update_network(data["network"])

    signals = _load_signals()
    if "life_phase" in data:
        signals["life_phase"] = int(_clamp(data["life_phase"], 1, 5))
        _save_signals(signals)

    return signals


def get_signals() -> dict[str, Any]:
    return _load_signals()


if __name__ == "__main__":
    # Initialize with defaults if no signals file exists
    if not SIGNALS_FILE.exists():
        _save_signals(_default_signals())
        print(f"Initialized {SIGNALS_FILE}")
    else:
        print(json.dumps(get_signals(), indent=2))
