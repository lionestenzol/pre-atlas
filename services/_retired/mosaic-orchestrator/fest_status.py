"""Quick festival status reader — runs via WSL."""
import subprocess

script = r"""
import os, pathlib
base = pathlib.Path("/root/festival-project/festivals")
for lifecycle in ["active", "planning", "ready"]:
    d = base / lifecycle
    if not d.exists():
        continue
    fests = sorted([x for x in d.iterdir() if x.is_dir()])
    if fests:
        print(f"\n{lifecycle.upper()} ({len(fests)}):")
        for f in fests:
            goal_file = f / "FESTIVAL_GOAL.md"
            goal = "(no goal file)"
            if goal_file.exists():
                lines = goal_file.read_text().strip().split("\n")
                goal = lines[0].lstrip("# ") if lines else "(empty)"
            phases = sorted([x.name for x in f.iterdir() if x.is_dir()])
            print(f"  {f.name}")
            print(f"    Goal: {goal}")
            if phases:
                print(f"    Phases: {', '.join(phases)}")
"""

result = subprocess.run(
    ["wsl", "-d", "Ubuntu", "--", "python3", "-c", script],
    capture_output=True, text=True, timeout=10,
)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr[:300])
