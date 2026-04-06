#!/usr/bin/env python3
"""
AUTO ACTOR — The system does the work, not you.
================================================
Reads governance state and ghost directives, then ACTS:

1. AUTO-CLOSE LOOPS: In CLOSURE mode, automatically archives loops that
   close_loop.py would recommend archiving. No human confirmation needed.

2. EXECUTE DIRECTIVES: Reads ghost_directives.json, builds Claude prompts
   from the directives, and submits them as tasks to the execution queue
   (or runs them directly via the orchestrator API).

3. LANE VIOLATIONS: Automatically parks ideas flagged as lane violations.

This script is designed to run as part of the daily pipeline.
It respects mode gates and only acts within what the current mode allows.

Outputs:
  - auto_actor_log.json  (what it did)
  - Mutations to results.db (loop closures)
  - Tasks submitted to execution queue
"""

import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "results.db"
ORCHESTRATOR_URL = "http://localhost:3005"
OPENCLAW_URL = "http://localhost:3004"

# How many loops to auto-close per daily run (safety cap)
MAX_AUTO_CLOSE_PER_RUN = 5

# How many directives to execute per daily run
MAX_DIRECTIVES_PER_RUN = 3


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_db():
    return sqlite3.connect(str(DB_PATH))


def get_already_decided() -> set[str]:
    """Get convo_ids that already have a decision."""
    if not DB_PATH.exists():
        return set()
    con = get_db()
    cur = con.cursor()
    decided = {str(r[0]) for r in cur.execute(
        "SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE','ARCHIVE')"
    ).fetchall()}
    con.close()
    return decided


def record_decision(convo_id: str, decision: str, title: str) -> bool:
    """Record a loop decision in the database and notify delta-kernel."""
    con = get_db()
    cur = con.cursor()

    # Check not already decided
    existing = cur.execute(
        "SELECT decision FROM loop_decisions WHERE convo_id=?", (convo_id,)
    ).fetchone()
    if existing:
        con.close()
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute(
        "INSERT INTO loop_decisions (convo_id, decision, date) VALUES (?, ?, ?)",
        (convo_id, decision, now)
    )
    con.commit()
    con.close()

    # Notify delta-kernel
    try:
        req = urllib.request.Request(
            "http://localhost:3001/api/law/close_loop",
            data=json.dumps({
                "loop_id": convo_id,
                "title": title,
                "outcome": "closed" if decision == "CLOSE" else "archived",
                "actor": "auto_actor",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    return True


def compute_auto_decision(convo_id: str, mode: str) -> tuple[str, str] | None:
    """Compute what to do with a loop — same logic as close_loop.py but autonomous.

    Returns (decision, reason) or None if we should skip.
    """
    # Load classification data
    cls_path = BASE / "conversation_classifications.json"
    if cls_path.exists():
        data = load_json(cls_path)
        convos = data.get("conversations", data) if isinstance(data, dict) else data
        classifications = {str(c.get("convo_id", i)): c for i, c in enumerate(convos)} if isinstance(convos, list) else {}
    else:
        classifications = {}

    cls = classifications.get(str(convo_id), {})
    outcome = cls.get("outcome", "unknown")
    trajectory = cls.get("emotional_trajectory", "unknown")
    intensity = cls.get("intensity", "unknown")

    # Strong archive signals — act without asking
    if outcome == "abandoned":
        return ("ARCHIVE", "Abandoned conversation — auto-archived")
    if outcome == "looped" and trajectory in ("spiral", "negative_arc"):
        return ("ARCHIVE", "Spiral/negative arc with no resolution — auto-archived")
    if intensity == "low" and outcome == "looped":
        return ("ARCHIVE", "Low intensity loop — auto-archived")
    if outcome == "looped":
        return ("ARCHIVE", "Looped without resolution — auto-archived")

    # Strong close signals
    if outcome == "resolved":
        return ("CLOSE", "Reached resolution — auto-closed")
    if outcome == "produced":
        return ("CLOSE", "Produced output — auto-closed")

    # In CLOSURE mode with unknown classification: archive aggressively.
    # If the system can't even classify the conversation, it's not important
    # enough to keep open. This is the core behavior change — the system
    # stops waiting for you to triage and starts clearing the backlog.
    if mode == "CLOSURE" and outcome == "unknown":
        return ("ARCHIVE", "Unknown outcome in CLOSURE mode — auto-archived to clear backlog")

    # Don't auto-act on ambiguous cases in non-CLOSURE modes
    return None


def auto_close_loops(mode: str) -> list[dict[str, str]]:
    """Automatically close/archive loops that have clear signals.

    Returns list of actions taken.
    """
    loops_path = BASE / "loops_latest.json"
    if not loops_path.exists():
        return []

    loops = load_json(loops_path)
    if not isinstance(loops, list):
        return []

    decided = get_already_decided()
    open_loops = [l for l in loops if str(l.get("convo_id", "")) not in decided]

    actions: list[dict[str, str]] = []
    for loop in open_loops:
        if len(actions) >= MAX_AUTO_CLOSE_PER_RUN:
            break

        convo_id = str(loop.get("convo_id", ""))
        title = loop.get("title", "untitled")
        result = compute_auto_decision(convo_id, mode)

        if result is None:
            continue

        decision, reason = result
        if record_decision(convo_id, decision, title):
            actions.append({
                "convo_id": convo_id,
                "title": title,
                "decision": decision,
                "reason": reason,
            })
            print(f"  [{decision}] #{convo_id}: {title} — {reason}")

    return actions


def submit_task_to_queue(task_id: str, instructions: str, priority: str = "normal") -> str | None:
    """Submit a task to the orchestrator execution queue.

    Returns job_id if queued, or the direct result if queue is disabled.
    """
    try:
        payload = json.dumps({
            "task_id": task_id,
            "instructions": instructions,
            "priority": priority,
            "timeout_seconds": 300,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{ORCHESTRATOR_URL}/api/v1/tasks/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode("utf-8"))

        if result.get("status") == "queued":
            return result.get("job_id")
        elif result.get("success"):
            # Direct execution mode — write result immediately
            return f"direct:{result.get('task_id', task_id)}"
        else:
            print(f"  Task failed: {result.get('error', 'unknown')}")
            return None
    except Exception as e:
        print(f"  Task submission failed: {e}")
        return None


def execute_ghost_directives() -> list[dict[str, Any]]:
    """Read ghost directives and submit them as real work.

    For each directive, builds a Claude prompt that produces actionable output.
    """
    directives_path = BASE / "genesis_output" / "ghost_directives.json"
    if not directives_path.exists():
        print("  No ghost directives found")
        return []

    data = load_json(directives_path)
    if not isinstance(data, dict):
        return []

    directives = data.get("directives", [])
    if not directives:
        print("  No directives to execute")
        return []

    # Load governance state for context
    gov = load_json(BASE / "governance_state.json")
    mode = gov.get("mode", "BUILD")
    lanes = gov.get("active_lanes", [])
    lane_names = [l.get("name", "") for l in lanes if isinstance(l, dict)]

    results: list[dict[str, Any]] = []
    executed = 0

    for directive in directives:
        if executed >= MAX_DIRECTIVES_PER_RUN:
            break
        if directive.get("blocked"):
            continue

        dtype = directive.get("type", "")
        domain = directive.get("domain", "")
        rationale = directive.get("rationale", "")
        suggested = directive.get("suggested_action", "")

        # Build a concrete Claude prompt based on directive type
        if dtype == "EXECUTE":
            prompt = (
                f"You are an autonomous agent for a personal productivity system. "
                f"The system is in {mode} mode with active lanes: {', '.join(lane_names)}.\n\n"
                f"DIRECTIVE: Execute on the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a concrete, actionable output. This could be:\n"
                f"- A draft document or outline\n"
                f"- A step-by-step execution plan with specific actions\n"
                f"- A decision memo with clear recommendations\n"
                f"- Code, copy, or content that advances this domain\n\n"
                f"Be specific and produce something the user can immediately use or publish. "
                f"Do NOT produce vague advice. Produce the actual work product."
            )
        elif dtype == "INVEST":
            prompt = (
                f"You are an autonomous agent for a personal productivity system in {mode} mode.\n\n"
                f"DIRECTIVE: Deepen the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a research brief that:\n"
                f"1. Identifies the 3 biggest gaps in this domain\n"
                f"2. Lists specific resources, tools, or experiments to close each gap\n"
                f"3. Estimates time investment for each (in hours)\n"
                f"4. Recommends which gap to close first and why\n\n"
                f"Be concrete. Name specific tools, books, courses, or experiments."
            )
        elif dtype == "RESURRECT":
            prompt = (
                f"You are an autonomous agent for a personal productivity system in {mode} mode.\n\n"
                f"DIRECTIVE: Evaluate whether to resurrect the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a kill-or-revive analysis:\n"
                f"1. What was the original intent of this domain?\n"
                f"2. Has anything changed (market, skills, interest) since it went dormant?\n"
                f"3. KILL recommendation: why to permanently archive this\n"
                f"4. REVIVE recommendation: what specifically to do in the next 2 hours\n"
                f"5. Your verdict: KILL or REVIVE, with one sentence explaining why\n\n"
                f"Be decisive. No hedging."
            )
        else:
            continue

        task_id = f"ghost-{dtype.lower()}-{domain[:20].replace(' ', '_')}"
        print(f"  Submitting: {task_id}")
        job_id = submit_task_to_queue(task_id, prompt, priority="normal")

        results.append({
            "directive_type": dtype,
            "domain": domain,
            "task_id": task_id,
            "job_id": job_id,
            "submitted_at": datetime.now().isoformat(),
        })
        executed += 1

    return results


def park_lane_violations() -> list[dict[str, str]]:
    """Auto-park ideas that are flagged as lane violations."""
    gov = load_json(BASE / "governance_state.json")
    violations = gov.get("lane_violations", [])

    if not violations:
        return []

    parked: list[dict[str, str]] = []
    for v in violations:
        if not isinstance(v, dict):
            continue
        title = v.get("title", "")
        rec = v.get("recommendation", "")
        if rec == "park" and title:
            parked.append({"title": title, "action": "parked"})
            print(f"  [PARK] {title}")

    # Write parked violations to a tracking file
    if parked:
        parked_path = BASE / "parked_violations.json"
        existing = load_json(parked_path) if parked_path.exists() else []
        if not isinstance(existing, list):
            existing = []
        existing.extend([{**p, "date": datetime.now().isoformat()} for p in parked])
        parked_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return parked


def main():
    print("=" * 60)
    print("  AUTO ACTOR — Autonomous Execution")
    print("=" * 60)
    total_start = time.time()

    log: dict[str, Any] = {
        "run_at": datetime.now().isoformat(),
        "loops_closed": [],
        "directives_executed": [],
        "violations_parked": [],
    }

    # Load governance state
    gov = load_json(BASE / "governance_state.json")
    mode = gov.get("mode", "BUILD")
    print(f"\n  Mode: {mode}")

    # 1. Auto-close loops (always — this is the #1 way to reduce friction)
    print(f"\n>> Auto-Close Loops")
    log["loops_closed"] = auto_close_loops(mode)
    if not log["loops_closed"]:
        print("  No loops eligible for auto-close")

    # 2. Park lane violations
    print(f"\n>> Park Lane Violations")
    log["violations_parked"] = park_lane_violations()
    if not log["violations_parked"]:
        print("  No violations to park")

    # 3. Execute ghost directives (submit work to Claude)
    print(f"\n>> Execute Ghost Directives")
    log["directives_executed"] = execute_ghost_directives()

    # Write action log
    log_path = BASE / "auto_actor_log.json"
    log["duration_seconds"] = round(time.time() - total_start, 1)
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    total_elapsed = time.time() - total_start
    closed = len(log["loops_closed"])
    directives = len(log["directives_executed"])
    parked = len(log["violations_parked"])

    print(f"\n{'=' * 60}")
    print(f"  AUTO ACTOR COMPLETE — {total_elapsed:.1f}s")
    print(f"  Loops closed/archived: {closed}")
    print(f"  Directives submitted:  {directives}")
    print(f"  Violations parked:     {parked}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
