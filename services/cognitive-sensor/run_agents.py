"""
Master orchestrator for the Idea Intelligence System.
Runs all 5 agents in sequence.

Usage: python run_agents.py
"""
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).parent.resolve()


def run(script: str, description: str):
    """Run a script with timing and error handling."""
    print(f"\n{'=' * 60}")
    print(f"  {description}")
    print(f"  Script: {script}")
    print("=" * 60)

    start = time.time()
    try:
        subprocess.check_call([sys.executable, script], cwd=BASE)
        elapsed = time.time() - start
        print(f"\n  Completed in {elapsed:.1f}s")
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start
        print(f"\n  FAILED after {elapsed:.1f}s (exit code {e.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("  IDEA INTELLIGENCE SYSTEM")
    print("  Mining 1,397 conversations for ideas")
    print("=" * 60)

    total_start = time.time()

    run("agent_excavator.py",    "Agent 1: EXCAVATOR — Extracting ideas from conversations")
    run("agent_deduplicator.py", "Agent 2: DEDUPLICATOR — Merging duplicate ideas")
    run("agent_classifier.py",   "Agent 3: CLASSIFIER — Building hierarchy and relationships")
    run("agent_orchestrator.py", "Agent 4: ORCHESTRATOR — Priority scoring and tiers")
    run("agent_reporter.py",     "Agent 5: REPORTER — Generating IDEA_REGISTRY.md")

    total_elapsed = time.time() - total_start

    print(f"\n{'=' * 60}")
    print(f"  COMPLETE — Total time: {total_elapsed:.1f}s")
    print("=" * 60)
    print()
    print("  Outputs:")
    print("    excavated_ideas_raw.json  — Raw extracted ideas")
    print("    ideas_deduplicated.json   — Merged duplicates")
    print("    ideas_classified.json     — Hierarchical structure")
    print("    idea_registry.json        — Priority-ranked registry")
    print("    IDEA_REGISTRY.md          — Human-readable report")
    print()
