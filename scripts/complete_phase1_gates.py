"""Mark Phase 001 quality gate tasks as complete."""
import subprocess

FEST_DIR = "/root/festival-project/festivals/active/mosaic-platform-MP0001"
SEQ_DIR = f"{FEST_DIR}/001_ORCHESTRATOR_CORE/01_scaffold"

def run_wsl(cmd):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
        capture_output=True, text=True
    )
    return result

# List remaining tasks
result = run_wsl(f"ls {SEQ_DIR}/*.md")
files = [f.split('/')[-1] for f in result.stdout.strip().split('\n')
         if f and 'SEQUENCE_GOAL' not in f]

print("Files:", files)

# Mark quality gates complete
gate_files = [f for f in files if any(g in f for g in ['testing', 'review', 'iterate', 'fest_commit'])]
print(f"\nMarking {len(gate_files)} gate tasks complete...")

for gf in sorted(gate_files):
    result = run_wsl(f"cd {SEQ_DIR} && echo y | fest task completed {gf}")
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"  {status}: {gf}")
    if result.returncode != 0:
        print(f"    {result.stderr.strip()[:200]}")
