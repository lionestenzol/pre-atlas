"""
Atlas Governor: Daily Loop Orchestrator
Runs the full daily pipeline in sequence:

AI-FOR-ITSELF (Level 2):
  1. Ingest & analyze (refresh existing pipeline)
  2. Maintain backlog

AI-FOR-ITSELF (Level 3 — Autonomous):
  2.5. Ghost executor: generate execution directives from Genesis tree

AI-FOR-YOU (Level 1):
  3. Generate daily brief with binary decisions

AI-FOR-SYSTEM (Level 0 — Integration):
  4. Stall detection + notification
  5. Push state to delta-kernel via orchestrator

Can be run from any directory - uses script location as base.
"""
from pathlib import Path
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE = Path(__file__).parent.resolve()

# Service URLs (override via env if needed)
ORCHESTRATOR_URL = "http://localhost:3005"
OPENCLAW_URL = "http://localhost:3004"


def run(script: str, description: str, critical: bool = True) -> bool:
    """Run a script with CWD set to the workspace directory.

    Args:
        script: Script filename relative to BASE.
        description: Human-readable description for logging.
        critical: If False, failures are logged but don't stop the pipeline.

    Returns:
        True if the script ran successfully, False otherwise.
    """
    script_path = BASE / script
    if not script_path.exists():
        print(f"  [SKIP] {script} not found — skipping")
        return False
    print(f"\n{'—' * 50}")
    print(f"  {description}")
    print(f"  Script: {script}")
    print(f"{'—' * 50}")
    start = time.time()
    try:
        subprocess.check_call([sys.executable, str(script_path)], cwd=str(BASE))
        elapsed = time.time() - start
        print(f"  [{description}] completed in {elapsed:.1f}s")
        return True
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start
        if critical:
            raise
        print(f"  [{description}] FAILED in {elapsed:.1f}s (non-critical, continuing)")
        print(f"  Error: {e}")
        return False


def run_stall_check() -> bool:
    """Check for stalled progress and notify via OpenClaw if detected.

    Reads completion_stats.json for zero-completion weeks.
    If stalled, sends a notification to OpenClaw.
    """
    print(f"\n{'—' * 50}")
    print(f"  Stall Detection")
    print(f"{'—' * 50}")

    stats_path = BASE / "completion_stats.json"
    if not stats_path.exists():
        print("  [SKIP] completion_stats.json not found")
        return False

    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        closed_week = stats.get("closed_week", 0)

        if closed_week > 0:
            print(f"  No stall — {closed_week} items closed this week")
            return True

        # Stall detected
        print(f"  STALL DETECTED — 0 items closed this week")

        # Build cut list from governance state
        gov_path = BASE / "governance_state.json"
        cut_items = []
        if gov_path.exists():
            gov = json.loads(gov_path.read_text(encoding="utf-8"))
            open_loops = gov.get("open_loops", [])
            if isinstance(open_loops, list):
                for loop in open_loops[:5]:
                    if isinstance(loop, dict):
                        title = loop.get("title", loop.get("topic", "untitled"))
                        age = loop.get("age_days", 0)
                        action = "CLOSE" if age > 14 else "REVIEW"
                        cut_items.append(f"  - [{action}] {title} ({age}d old)")

        # Notify via OpenClaw
        message = "STALL ALERT: No tasks closed this week."
        if cut_items:
            message += f" Cut list ({len(cut_items)} items):\n" + "\n".join(cut_items)

        try:
            payload = json.dumps({
                "channel": "default",
                "message": message,
                "priority": "high",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{OPENCLAW_URL}/api/v1/notify",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"  Stall notification sent via OpenClaw")
        except urllib.error.URLError:
            print(f"  OpenClaw unavailable — stall notification skipped")

        return True
    except Exception as e:
        print(f"  Stall check failed: {e}")
        return False


def push_to_orchestrator() -> bool:
    """Push daily state to delta-kernel via the orchestrator's daily loop.

    Calls POST /api/v1/workflows/daily on the orchestrator, which
    reads the cognitive-sensor outputs and pushes them to delta-kernel.
    """
    print(f"\n{'—' * 50}")
    print(f"  Delta-Kernel Sync (via Orchestrator)")
    print(f"{'—' * 50}")

    try:
        req = urllib.request.Request(
            f"{ORCHESTRATOR_URL}/api/v1/workflows/daily",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        print(f"  Orchestrator sync complete: {json.dumps(result, indent=2)[:200]}")
        return True
    except urllib.error.URLError as e:
        print(f"  Orchestrator unavailable — delta-kernel sync skipped ({e})")
        return False
    except Exception as e:
        print(f"  Delta-kernel sync failed: {e}")
        return False


def main():
    print("=" * 60)
    print("ATLAS GOVERNOR — DAILY LOOP")
    print("=" * 60)
    total_start = time.time()

    # ── AI-FOR-ITSELF: Ingest & Analyze ──
    print("\n>> Phase 1: Ingest & Analyze State")
    run("loops.py", "Open loop detection")
    run("completion_stats.py", "Completion statistics")
    run("export_cognitive_state.py", "Export cognitive state")
    run("route_today.py", "Route today's mode")
    run("export_daily_payload.py", "Export daily payload")

    # ── AI-FOR-ITSELF: Maintain Backlog ──
    print("\n>> Phase 2: Backlog Maintenance")
    run("wire_cycleboard.py", "Wire cycleboard")
    run("reporter.py", "Reporter")

    # ── AI-FOR-ITSELF: Ghost Executor (autonomous directives) ──
    print("\n>> Phase 2.5: Ghost Executor")
    run("ghost_executor.py", "Ghost executor — autonomous directives", critical=False)

    # ── AI-FOR-YOU: Generate Daily Brief ──
    print("\n>> Phase 3: Governor Daily Brief")
    run("governor_daily.py", "Governor daily pipeline")

    # ── AI-DOES-THE-WORK: Autonomous Execution ──
    print("\n>> Phase 4: Auto Actor (autonomous execution)")
    run("auto_actor.py", "Auto actor — close loops, execute directives, park violations", critical=False)

    # ── CycleBoard visibility: translate auto_actor output into dashboard entries ──
    # Auto-executed directives -> Journal. Needs-approval directives -> [REVIEW] task
    # + proposals.json. Auto-closed loops -> Momentum win. Non-critical: bridge
    # fails gracefully if delta-kernel isn't running.
    print("\n>> Phase 4.5: CycleBoard push (auto_actor -> dashboard)")
    run("cycleboard_push.py", "CycleBoard push — surface auto_actor decisions on the dashboard", critical=False)

    # ── AI-FOR-SYSTEM: Integration ──
    print("\n>> Phase 5: System Integration (non-critical)")
    run_stall_check()
    push_to_orchestrator()

    # ── Summary ──
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"DAILY LOOP COMPLETE — {total_elapsed:.1f}s")
    print(f"Outputs:")
    print(f"  - daily_brief.md            (your brief)")
    print(f"  - governance_state.json      (system state)")
    print(f"  - genesis_output/ghost_*     (execution directives)")
    print(f"  - auto_actor_log.json        (what the system DID)")
    print(f"  - delta-kernel               (state synced)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
