"""
Behavioral Audit Pipeline
Runs conversation classifier + synthesizer to produce BEHAVIORAL_AUDIT.md.

Can be run from any directory - uses script location as base.
"""
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).parent.resolve()

def run(script: str, description: str):
    """Run a script with CWD set to the workspace directory."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Script:  {script}")
    print(f"{'=' * 60}\n")
    start = time.time()
    subprocess.check_call([sys.executable, script], cwd=BASE)
    elapsed = time.time() - start
    print(f"\n[{description}] completed in {elapsed:.1f}s")

print("=" * 60)
print("BEHAVIORAL AUDIT PIPELINE")
print("=" * 60)

total_start = time.time()

# Step 1: Classify all conversations
run("agent_classifier_convo.py", "Step 1: Conversation Classifier")

# Step 2: Synthesize all data into 30-question audit
run("agent_synthesizer.py", "Step 2: Behavioral Audit Synthesizer")

total_elapsed = time.time() - total_start
print(f"\n{'=' * 60}")
print(f"PIPELINE COMPLETE")
print(f"Total time: {total_elapsed:.1f}s")
print(f"Output: BEHAVIORAL_AUDIT.md")
print(f"{'=' * 60}")
