"""
Master refresh script for the Cognitive Operating System.
Runs the full analysis pipeline in sequence.

Can be run from any directory - uses script location as base.
"""
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).parent.resolve()

def run(script: str):
    """Run a script with CWD set to the workspace directory."""
    subprocess.check_call([sys.executable, script], cwd=BASE)

run("loops.py")
run("completion_stats.py")
run("export_cognitive_state.py")
run("route_today.py")
run("export_daily_payload.py")
run("wire_cycleboard.py")
run("reporter.py")
run("build_dashboard.py")
print("Refreshed.")
