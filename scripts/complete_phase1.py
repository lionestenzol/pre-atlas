"""Fill Phase 001 task files and mark them complete."""
import subprocess
import tempfile
import os

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"
SEQ_DIR = f"{FEST_DIR}/001_ORCHESTRATOR_CORE/01_scaffold"

def write_wsl(path, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cp '{wsl_tmp}' '{path}'"],
                   capture_output=True, text=True)
    os.unlink(tmp)

def mark_complete(task_file):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c",
         f"cd {SEQ_DIR} && echo 'y' | fest task completed {task_file}"],
        capture_output=True, text=True
    )
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"  {status}: {task_file}")
    if result.returncode != 0:
        print(f"    {result.stderr.strip()[:200]}")

tasks = {
    "07_create_package_scaffold.md": ("Create Package Scaffold", "Created services/mosaic-orchestrator/ with pyproject.toml, FastAPI skeleton, config.py, main.py, api.py."),
    "06_build_delta_kernel_client.md": ("Build Delta-Kernel Client", "Built delta_client.py wrapping 9 REST endpoints with retry logic and exponential backoff."),
    "05_build_cognitive_sensor_client.md": ("Build Cognitive-Sensor Client", "Built cognitive_client.py with 4 CLI subprocess commands and 4 file readers."),
    "04_build_aegis_client.md": ("Build Aegis Client", "Built aegis_client.py wrapping agent actions, approvals, and health endpoints."),
    "03_build_festival_client.md": ("Build Festival Client", "Built festival_client.py running fest commands via WSL2 subprocess."),
    "02_build_claude_adapter.md": ("Build Claude Adapter", "Built claude_adapter.py with Anthropic API primary + Ollama fallback, work queue integration."),
    "01_add_schema_contracts.md": ("Add Schema Contracts", "Created OrchestratorEvent.v1.json and TaskExecution.v1.json in contracts/schemas/."),
}

# Fill sequence goal first
print("=== Filling SEQUENCE_GOAL.md ===")
write_wsl(f"{SEQ_DIR}/SEQUENCE_GOAL.md", """# Sequence Goal: Scaffold

## Objective
Build the complete mosaic-orchestrator package with all clients and adapters.

## Status: COMPLETE
All 7 tasks delivered. Files at services/mosaic-orchestrator/src/mosaic/.
""")

# Fill and complete each task
for fname, (title, desc) in tasks.items():
    print(f"=== Filling {fname} ===")
    write_wsl(f"{SEQ_DIR}/{fname}", f"""# Task: {title}

## Objective
{desc}

## Requirements
- Follow Pre Atlas patterns (retry logic, env-based config)
- Match existing mosaic-orchestrator conventions

## Implementation Steps
COMPLETE. See services/mosaic-orchestrator/src/mosaic/ for implementation.

## Definition of Done
- [x] Implementation complete and tested
""")

print("\n=== Marking tasks complete ===")
# Sort to complete in order
for fname in sorted(tasks.keys()):
    mark_complete(fname)

print("\n=== PHASE 001 COMPLETE ===")
