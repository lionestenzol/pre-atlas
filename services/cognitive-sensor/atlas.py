"""
Atlas — Daily Routing Engine.

Usage:
    python atlas.py boot     Set energy, derive state, route the day
    python atlas.py status   View current state
    python atlas.py next     Get next action from decision tree
    python atlas.py loop     View open loops and closure stats
    python atlas.py plan     Midday recalculation
    python atlas.py close    End-of-day closeout
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).parent
STATE_FILE = DIR / "atlas_state.json"
COGNITIVE_STATE = DIR / "cognitive_state.json"
CLOSURES_FILE = DIR / "closures.json"
DAILY_PAYLOAD = DIR / "daily_payload.json"


# ── Readers ──────────────────────────────────────────────

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_cognitive_state():
    data = read_json(COGNITIVE_STATE)
    closure = data.get("closure", {})
    loops = data.get("loops", [])
    return {
        "open_loops": closure.get("open", 0),
        "closure_ratio": closure.get("ratio", 0.0),
        "loop_titles": [(l.get("title", "?"), l.get("score", 0), l.get("convo_id", "")) for l in loops],
    }


def read_closures():
    data = read_json(CLOSURES_FILE)
    stats = data.get("stats", {})
    return {
        "total_closures": stats.get("total_closures", 0),
        "closures_today": stats.get("closures_today", 0),
        "streak_days": stats.get("streak_days", 0),
        "best_streak": stats.get("best_streak", 0),
    }


def read_fest_state():
    """Parse fest list output for active festival counts."""
    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c",
             "cd /root/festival-project && fest list"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"active": 0, "tasks_remaining": 0}

    active = 0
    tasks_remaining = 0
    in_active = False
    for line in output.splitlines():
        if "ACTIVE" in line:
            in_active = True
            continue
        if in_active and line.strip().startswith(("PLANNING", "DUNGEON", "READY", "RITUAL")):
            in_active = False
        if in_active and "[" in line and "]" in line:
            active += 1
            # Parse percentage like [58%] or [0%]
            try:
                pct_str = line.split("[")[1].split("%")[0]
                pct = int(pct_str)
                if pct < 100:
                    tasks_remaining += 1  # count incomplete festivals
            except (IndexError, ValueError):
                pass

    return {"active": active, "tasks_remaining": tasks_remaining}


# ── Decision Engine ──────────────────────────────────────

def derive_pressure(open_loops, critical_tasks):
    if open_loops > 5 or critical_tasks:
        return "high"
    if open_loops <= 2:
        return "low"
    return "medium"


def derive_mode(energy, pressure, open_loops):
    if energy == "low":
        return "RECOVER"
    if pressure == "high" and energy != "high":
        return "CLOSURE"
    if open_loops > 5:
        return "CLOSURE"
    return "BUILD"


def decide_next(state):
    """5-rule decision tree. Returns action string."""
    # Rule 0: energy override — recovery trumps everything
    if state.get("energy") == "low":
        return "Rest. If you must work: smallest possible task."

    critical = state.get("critical_tasks", [])
    if critical:
        return f"Do: {critical[0]}"

    if state.get("open_loops", 0) > 5:
        loops = state.get("top_loop", "unknown")
        return f'Close loops. Top loop: "{loops}"'

    blockers = state.get("blockers", [])
    if blockers:
        return f"Unblock: {blockers[0]}"

    return "Continue main build. Run: fest next"


# ── Output ───────────────────────────────────────────────

def print_routing(state):
    mode = state.get("mode", "?")
    energy = state.get("energy", "?")
    pressure = state.get("pressure", "?")
    loops = state.get("open_loops", 0)
    ratio = state.get("closure_ratio", 0)
    action = state.get("next_action", "?")
    blockers = state.get("blockers", [])

    print()
    print(f"  STATE    -> {mode} | energy:{energy} | pressure:{pressure}")
    mode_priority = {"RECOVER": "Rest + recover", "CLOSURE": "Close loops", "BUILD": "Build"}
    print(f"  PRIORITY -> {mode_priority.get(mode, mode)} ({loops} open, ratio {ratio:.0f}%)")
    print(f"  ACTION   -> {action}")
    print(f"  BLOCKERS -> {', '.join(blockers) if blockers else 'none'}")
    print()


# ── Commands ─────────────────────────────────────────────

def cmd_boot(args):
    # Energy input
    if args.energy:
        energy_map = {"l": "low", "m": "medium", "h": "high"}
        energy = energy_map.get(args.energy[0].lower(), "medium")
    else:
        raw = input("  Energy? [l/m/h]: ").strip().lower()
        energy_map = {"l": "low", "m": "medium", "h": "high"}
        energy = energy_map.get(raw[:1] if raw else "m", "medium")

    # Auto-derive from existing files
    cog = read_cognitive_state()
    closures = read_closures()
    fest = read_fest_state()

    open_loops = cog["open_loops"]
    critical_tasks = []  # MVP: manual population later
    pressure = derive_pressure(open_loops, critical_tasks)
    mode = derive_mode(energy, pressure, open_loops)

    top_loop = cog["loop_titles"][0][0] if cog["loop_titles"] else ""

    action = decide_next({
        "critical_tasks": critical_tasks,
        "open_loops": open_loops,
        "blockers": [],
        "energy": energy,
        "top_loop": top_loop,
    })

    state = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "energy": energy,
        "pressure": pressure,
        "mode": mode,
        "open_loops": open_loops,
        "closure_ratio": cog["closure_ratio"],
        "streak_days": closures["streak_days"],
        "fest_active": fest["active"],
        "fest_incomplete": fest["tasks_remaining"],
        "critical_tasks": critical_tasks,
        "blockers": [],
        "top_loop": top_loop,
        "next_action": action,
        "closed": False,
    }

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("\n  Atlas booted.")
    print_routing(state)


def cmd_status(_args):
    state = read_json(STATE_FILE)
    if not state:
        print("\n  No state. Run: atlas boot")
        return
    if state.get("closed"):
        print("\n  Day is closed. Run: atlas boot to start a new day.")
        return
    print_routing(state)
    # Extra details
    print(f"  Streak     : {state.get('streak_days', 0)} days")
    print(f"  Festivals  : {state.get('fest_active', 0)} active, {state.get('fest_incomplete', 0)} incomplete")
    print(f"  Booted at  : {state.get('generated_at', '?')}")
    print()


def cmd_next(_args):
    state = read_json(STATE_FILE)
    if not state:
        print("\n  No state. Run: atlas boot")
        return
    if state.get("closed"):
        print("\n  Day is closed. Run: atlas boot to start a new day.")
        return
    print_routing(state)


def cmd_loop(_args):
    cog = read_cognitive_state()
    closures = read_closures()

    print("\n  OPEN LOOPS")
    print("  " + "-" * 50)
    for title, score, cid in cog["loop_titles"]:
        print(f"  [{cid:>5}]  {title:<35} score:{score}")
    if not cog["loop_titles"]:
        print("  (none)")

    print()
    print(f"  Open     : {cog['open_loops']}")
    print(f"  Ratio    : {cog['closure_ratio']:.0f}%")
    print(f"  Streak   : {closures['streak_days']} days (best: {closures['best_streak']})")
    print(f"  Today    : {closures['closures_today']} closures")
    print()


def cmd_plan(_args):
    state = read_json(STATE_FILE)
    if not state:
        print("\n  No state. Run: atlas boot")
        return
    if state.get("closed"):
        print("\n  Day is closed. Run: atlas boot")
        return

    # Re-read fresh data, keep existing energy
    cog = read_cognitive_state()
    closures = read_closures()
    fest = read_fest_state()

    energy = state["energy"]
    open_loops = cog["open_loops"]
    critical_tasks = state.get("critical_tasks", [])
    pressure = derive_pressure(open_loops, critical_tasks)
    mode = derive_mode(energy, pressure, open_loops)
    top_loop = cog["loop_titles"][0][0] if cog["loop_titles"] else ""

    action = decide_next({
        "critical_tasks": critical_tasks,
        "open_loops": open_loops,
        "blockers": state.get("blockers", []),
        "energy": energy,
        "top_loop": top_loop,
    })

    state.update({
        "recalc_at": datetime.now().isoformat(timespec="seconds"),
        "pressure": pressure,
        "mode": mode,
        "open_loops": open_loops,
        "closure_ratio": cog["closure_ratio"],
        "streak_days": closures["streak_days"],
        "fest_active": fest["active"],
        "fest_incomplete": fest["tasks_remaining"],
        "top_loop": top_loop,
        "next_action": action,
    })

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("\n  Atlas recalculated.")
    print_routing(state)


def cmd_close(_args):
    state = read_json(STATE_FILE)
    if not state:
        print("\n  No state. Run: atlas boot")
        return
    if state.get("closed"):
        print("\n  Day already closed.")
        return

    closures = read_closures()

    print("\n  DAY CLOSEOUT")
    print("  " + "-" * 50)
    print(f"  Mode     : {state.get('mode', '?')}")
    print(f"  Energy   : {state.get('energy', '?')}")
    print(f"  Action   : {state.get('next_action', '?')}")
    print(f"  Closures : {closures['closures_today']} today")
    print(f"  Streak   : {closures['streak_days']} days")
    print()

    state["closed"] = True
    state["closed_at"] = datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("  Day closed. See you tomorrow.")
    print()


# ── Main ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Atlas — Daily Routing Engine",
    )
    sub = parser.add_subparsers(dest="command")

    boot_p = sub.add_parser("boot", help="Set energy, derive state, route the day")
    boot_p.add_argument("energy", nargs="?", help="Energy level: l/m/h")

    sub.add_parser("status", help="View current state")
    sub.add_parser("next", help="Get next action")
    sub.add_parser("loop", help="View open loops")
    sub.add_parser("plan", help="Midday recalculation")
    sub.add_parser("close", help="End-of-day closeout")

    args = parser.parse_args()

    commands = {
        "boot": cmd_boot,
        "status": cmd_status,
        "next": cmd_next,
        "loop": cmd_loop,
        "plan": cmd_plan,
        "close": cmd_close,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
