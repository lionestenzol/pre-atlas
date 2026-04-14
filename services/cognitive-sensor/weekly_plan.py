"""
Weekly Plan — Prospective execution planner.

Generates a forward-looking weekly plan based on:
  - Current governance state (mode, lanes, violations)
  - Life signals (energy, finance, skills, network)
  - Behavioral patterns (rolling context, compliance rate)
  - Life phase trajectory

Output: weekly_plan.json (consumed by CycleBoard Weekly Focus screen)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.resolve()

PHASE_PRIORITIES: dict[int, dict[str, Any]] = {
    1: {
        "name": "Stabilization",
        "focus": "Secure energy, housing, transportation, project infrastructure",
        "weekly_targets": [
            "Protect energy: limit household exposure, schedule recovery",
            "Backup all digital/cloud projects",
            "Track micro-budget daily",
            "Maintain neutral household engagement",
        ],
        "red_alert_guidance": "Minimize exposure during predicted interference windows",
    },
    2: {
        "name": "Leverage Accumulation",
        "focus": "Monetize projects, automate systems, build income streams",
        "weekly_targets": [
            "2-4 hrs/day high-leverage project work",
            "Track and optimize income streams",
            "Expand network outreach (1-2 contacts/week)",
            "Automate one recurring manual task",
        ],
        "red_alert_guidance": "Maintain household neutrality; automate around interference",
    },
    3: {
        "name": "Extraction & Autonomy",
        "focus": "Exit toxic environment, achieve independent living",
        "weekly_targets": [
            "Execute housing/independence preparation",
            "Consolidate finances for transition",
            "Transfer project infrastructure to independent control",
            "Maintain digital/project backups",
        ],
        "red_alert_guidance": "Execute extraction logistics around interference windows",
    },
    4: {
        "name": "Scaling",
        "focus": "Diversify income, build assets, scale project impact",
        "weekly_targets": [
            "Scale high-impact projects",
            "Diversify income streams",
            "Build digital/physical assets",
            "Optimize all operational systems",
        ],
        "red_alert_guidance": "Household interference is irrelevant; focus on growth",
    },
    5: {
        "name": "Generational Infrastructure",
        "focus": "Permanent autonomy, compounding systems",
        "weekly_targets": [
            "Oversee automated systems",
            "Evaluate compounding wealth/assets",
            "Audit autonomy systems",
            "Plan long-term generational leverage",
        ],
        "red_alert_guidance": "Full autonomy — minimal manual involvement required",
    },
}

DAY_PROTOCOL = [
    {"block": "Morning Scan", "time": "5-7am", "focus": "Dashboard review, red-alert check, priorities confirmed"},
    {"block": "Deep Work", "time": "7-12pm", "focus": "High-leverage project execution (protected block)"},
    {"block": "Midday Check-in", "time": "12-1pm", "focus": "Energy check, nutrition, micro-rest"},
    {"block": "Afternoon", "time": "1-5pm", "focus": "Continuation or household navigation"},
    {"block": "Evening Ops", "time": "5-7pm", "focus": "Finance tracking, mobility checks, household tasks"},
    {"block": "Night Audit", "time": "7-9pm", "focus": "Daily audit, journal, prep tomorrow"},
    {"block": "Close", "time": "9-10pm", "focus": "Energy recovery, plan next day"},
]


def _load_json(name: str) -> dict[str, Any]:
    path = BASE / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _get_week_dates() -> list[str]:
    """Return dates for the current week (Mon-Sun)."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def compute_weekly_focus(
    gov_state: dict[str, Any],
    life_signals: dict[str, Any],
    compliance_rate: float | None,
) -> dict[str, Any]:
    """Generate prospective weekly focus based on governance + life signals."""

    mode = gov_state.get("mode", "BUILD")
    risk = gov_state.get("risk", "MEDIUM")
    build_allowed = gov_state.get("build_allowed", True)
    life_phase = life_signals.get("life_phase", gov_state.get("life_phase", 1))
    phase_data = PHASE_PRIORITIES.get(life_phase, PHASE_PRIORITIES[1])

    energy = life_signals.get("energy", {})
    finance = life_signals.get("finance", {})
    energy_level = energy.get("energy_level", 50)
    burnout = energy.get("burnout_risk", False)
    red_alert = energy.get("red_alert_active", False)
    runway = finance.get("runway_months", 3.0)

    # Mode-specific weekly priorities
    mode_priorities: dict[str, list[str]] = {
        "CLOSURE": [
            "Close or archive oldest open loop each day",
            "Do not start any new work",
            "Review stalled loops — finish or kill each one",
        ],
        "MAINTENANCE": [
            "Light admin and health actions",
            "One shippable piece from active lane",
            "Archive 5 backlog ideas",
        ],
        "BUILD": [
            "90-minute build block daily (phone out of room)",
            "Ship one asset this week",
            "End each day: write what you shipped",
        ],
    }

    priorities = mode_priorities.get(mode, mode_priorities["BUILD"])

    # Energy-aware adjustments
    energy_notes: list[str] = []
    if burnout:
        energy_notes.append("BURNOUT DETECTED: Schedule 2+ recovery blocks this week before any execution")
    elif energy_level < 30:
        energy_notes.append(f"LOW ENERGY ({energy_level}/100): Reduce scope — maintenance only until recovery")
    elif energy_level < 50:
        energy_notes.append(f"MODERATE ENERGY ({energy_level}/100): One deep work block per day max")

    if red_alert:
        energy_notes.append(f"RED ALERT: {phase_data['red_alert_guidance']}")

    # Financial constraint
    if runway < 2:
        energy_notes.append(f"FINANCIAL CONSTRAINT: Runway {runway:.1f}mo — prioritize revenue-generating work")

    # Compliance feedback
    compliance_note = None
    if compliance_rate is not None:
        pct = round(compliance_rate * 100)
        if pct < 40:
            compliance_note = f"Last 30-day compliance: {pct}% — directives are being ignored. This week: follow the plan."
        elif pct < 70:
            compliance_note = f"Last 30-day compliance: {pct}% — improving but inconsistent."

    # Build daily plan template for each day of the week
    week_dates = _get_week_dates()
    daily_plans: list[dict[str, Any]] = []
    for date_str in week_dates:
        day_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
        plan: dict[str, Any] = {
            "date": date_str,
            "day": day_name,
            "protocol": DAY_PROTOCOL,
        }
        if day_name == "Sunday":
            plan["focus"] = "Weekly audit + next week prep"
            plan["type"] = "audit"
        elif day_name == "Saturday":
            plan["focus"] = "Light project work + backups + reflection"
            plan["type"] = "light"
        else:
            plan["focus"] = priorities[0] if priorities else "Execute daily plan"
            plan["type"] = "standard"
        daily_plans.append(plan)

    return {
        "generated_at": datetime.now().isoformat(),
        "week_of": week_dates[0],
        "life_phase": life_phase,
        "phase_name": phase_data["name"],
        "phase_focus": phase_data["focus"],
        "mode": mode,
        "risk": risk,
        "build_allowed": build_allowed,
        "weekly_priorities": priorities,
        "phase_targets": phase_data["weekly_targets"],
        "energy_notes": energy_notes,
        "compliance_note": compliance_note,
        "daily_plans": daily_plans,
    }


def main() -> None:
    print("=" * 60)
    print("WEEKLY PLANNER")
    print("=" * 60)

    gov_state = _load_json("governance_state.json")
    life_signals = _load_json("life_signals.json")

    compliance_rate = None
    try:
        from behavioral_memory import get_compliance_rate
        compliance_rate = get_compliance_rate(30)
    except Exception:
        pass

    plan = compute_weekly_focus(gov_state, life_signals, compliance_rate)

    out_path = BASE / "weekly_plan.json"
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path.name}")

    # Also write to brain dir for CycleBoard
    brain_path = BASE / "cycleboard" / "brain" / "weekly_plan.json"
    brain_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote cycleboard/brain/{brain_path.name}")

    print(f"\nPhase {plan['life_phase']}: {plan['phase_name']}")
    print(f"Mode: {plan['mode']} | Risk: {plan['risk']}")
    print(f"\nWeekly Priorities:")
    for p in plan["weekly_priorities"]:
        print(f"  - {p}")
    if plan["energy_notes"]:
        print(f"\nEnergy Notes:")
        for n in plan["energy_notes"]:
            print(f"  ! {n}")


if __name__ == "__main__":
    main()
