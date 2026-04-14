"""Renumber task files in sequences with gaps."""
import subprocess
import re

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def run_wsl(cmd):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# Find all sequences
phases = ["002_MIROFISH", "003_OPENCLAW", "004_DASHBOARD", "005_WORKFLOWS_METERING", "006_INSTALLER"]

for phase in phases:
    seqs = run_wsl(f"ls -d {FEST_DIR}/{phase}/*/").split('\n')
    for seq_path in seqs:
        if not seq_path:
            continue
        seq_path = seq_path.rstrip('/')
        # Get task files (not SEQUENCE_GOAL.md)
        files_raw = run_wsl(f"ls {seq_path}/*.md 2>/dev/null")
        files = [f for f in files_raw.split('\n') if f and 'SEQUENCE_GOAL' not in f]

        # Parse numbers and names
        parsed = []
        for f in files:
            basename = f.split('/')[-1]
            match = re.match(r'^(\d+)_(.+)$', basename)
            if match:
                parsed.append((int(match.group(1)), match.group(2), f))

        # Sort by current number
        parsed.sort(key=lambda x: x[0])

        # Check for gaps
        expected = 1
        renames = []
        for num, name, path in parsed:
            if num != expected:
                new_name = f"{expected:02d}_{name}"
                new_path = '/'.join(path.split('/')[:-1]) + '/' + new_name
                renames.append((path, new_path))
            expected += 1

        if renames:
            seq_name = seq_path.split('/')[-1]
            print(f"  {phase}/{seq_name}: {len(renames)} renames")
            for old, new in renames:
                run_wsl(f"mv '{old}' '{new}'")

print("Done!")
