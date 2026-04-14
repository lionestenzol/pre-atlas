"""
Atlas Governor: Weekly Loop Orchestrator
Runs the full weekly pipeline in sequence:

AI-FOR-ITSELF (Level 2):
  1. Run full daily loop first (latest state)
  2. Run behavioral audit pipeline (classifier + synthesizer)

AI-FOR-YOU (Level 1):
  3. Generate weekly governor packet with 3-5 binary decisions

Can be run from any directory - uses script location as base.
"""
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).parent.resolve()


FAILURES = []


def run(script: str, description: str, critical: bool = True):
    """Run a script with CWD set to the workspace directory.
    If critical=True, failure stops the pipeline.
    If critical=False, failure is logged and pipeline continues.
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
        msg = f"  [FAILED] {description} ({script}) after {elapsed:.1f}s — exit code {e.returncode}"
        print(msg)
        FAILURES.append(msg)
        if critical:
            raise
        return False


def main():
    print("=" * 60)
    print("ATLAS GOVERNOR — WEEKLY LOOP")
    print("=" * 60)
    total_start = time.time()

    # ── Phase 1: Run daily loop for latest state ──
    print("\n>> Phase 1: Daily Loop (fresh state)")
    run("run_daily.py", "Full daily loop")

    # ── Phase 2: Behavioral audit ──
    print("\n>> Phase 2: Behavioral Audit")
    run("agent_classifier_convo.py", "Conversation classifier", critical=False)
    run("agent_synthesizer.py", "Behavioral audit synthesizer", critical=False)

    # ── Phase 3: Idea pipeline refresh ──
    # These haven't run since Feb 9. Run them weekly so governor has fresh data.
    print("\n>> Phase 3: Idea Pipeline Refresh")
    run("agent_excavator.py", "Idea excavator", critical=False)
    run("agent_deduplicator.py", "Idea deduplicator", critical=False)
    run("agent_classifier.py", "Idea classifier", critical=False)
    run("agent_orchestrator.py", "Idea orchestrator (registry)", critical=False)

    # ── Phase 4: Weekly governor packet ──
    print("\n>> Phase 4: Governor Weekly Packet")
    run("governor_weekly.py", "Governor weekly pipeline")

    # ── Summary ──
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"WEEKLY LOOP COMPLETE — {total_elapsed:.1f}s")
    if FAILURES:
        print(f"\n⚠ {len(FAILURES)} step(s) failed (non-critical):")
        for f in FAILURES:
            print(f"  {f}")
    print(f"\nOutputs:")
    print(f"  - daily_brief.md              (today's brief)")
    print(f"  - governance_state.json        (system state)")
    print(f"  - governor_headline.json       (headline for atlas_boot)")
    print(f"  - BEHAVIORAL_AUDIT.md          (30-question audit)")
    print(f"  - idea_registry.json           (refreshed idea pipeline)")
    print(f"  - weekly_governor_packet.md    (your weekly packet)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
