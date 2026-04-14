"""Add fest_phase_type frontmatter to all PHASE_GOAL.md files."""
import subprocess
import tempfile
import os

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def read_wsl(path):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cat '{path}'"],
        capture_output=True, text=True
    )
    return result.stdout

def write_wsl(path, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cp '{wsl_tmp}' '{path}'"],
                   capture_output=True, text=True)
    os.unlink(tmp)

phases = [
    "001_ORCHESTRATOR_CORE",
    "002_MIROFISH",
    "003_OPENCLAW",
    "004_DASHBOARD",
    "005_WORKFLOWS_METERING",
    "006_INSTALLER",
]

for phase in phases:
    path = f"{FEST_DIR}/{phase}/PHASE_GOAL.md"
    content = read_wsl(path)
    # Add frontmatter if not present
    if not content.startswith("---"):
        new_content = f"---\nfest_phase_type: implementation\n---\n\n{content}"
        write_wsl(path, new_content)
        print(f"  Fixed: {phase}")
    else:
        print(f"  Already has frontmatter: {phase}")

print("\nDone!")
