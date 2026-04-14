"""Create all sequences, tasks, and fill content for Mosaic festival."""
import subprocess
import os

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def run(cmd):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cd /root/festival-project && {cmd}"],
        capture_output=True, text=True
    )
    if result.stdout.strip():
        print(result.stdout.strip()[:200])
    if result.returncode != 0 and result.stderr.strip():
        print(f"ERR: {result.stderr.strip()[:200]}")
    return result

def write_file(path, content):
    """Write content to a file in WSL."""
    # Write to temp file on Windows, then copy to WSL
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    # Convert Windows path to WSL path
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    run(f"cp '{wsl_tmp}' '{path}'")
    os.unlink(tmp)

def create_seq(phase, name):
    run(f"cd {FEST_DIR}/{phase} && fest create sequence --name '{name}'")

def create_task(phase, seq, name):
    run(f"cd {FEST_DIR}/{phase}/{seq} && fest create task --name '{name}'")

# ============================================================
# PHASE 001: ORCHESTRATOR_CORE (1 sequence, 7 tasks)
# ============================================================
print("\n=== PHASE 001: ORCHESTRATOR_CORE ===")
create_seq("001_ORCHESTRATOR_CORE", "scaffold")

tasks_001 = [
    ("01_create_package_scaffold", "Create package scaffold", "Create services/mosaic-orchestrator/ with pyproject.toml, __init__.py, config.py, main.py, api.py."),
    ("02_delta_kernel_client", "Build delta-kernel client", "Build delta_client.py wrapping 9 REST endpoints with retry logic."),
    ("03_cognitive_sensor_client", "Build cognitive-sensor client", "Build cognitive_client.py with 4 CLI commands and 4 file readers via subprocess."),
    ("04_aegis_client", "Build aegis client", "Build aegis_client.py wrapping agent actions, approvals, and health endpoints."),
    ("05_festival_client", "Build festival client", "Build festival_client.py running fest commands via WSL2 subprocess."),
    ("06_claude_adapter", "Build claude adapter", "Build claude_adapter.py with Anthropic API primary and Ollama fallback, work queue integration."),
    ("07_schema_contracts", "Add schema contracts", "Create OrchestratorEvent.v1.json and TaskExecution.v1.json in contracts/schemas/."),
]

for fname, title, desc in tasks_001:
    create_task("001_ORCHESTRATOR_CORE", "01_scaffold", title)

# ============================================================
# PHASE 002: MIROFISH (4 sequences, 11 tasks)
# ============================================================
print("\n=== PHASE 002: MIROFISH ===")

# Seq 01: infrastructure
create_seq("002_MIROFISH", "infrastructure")
create_task("002_MIROFISH", "01_infrastructure", "create mirofish scaffold")
create_task("002_MIROFISH", "01_infrastructure", "write docker compose")
create_task("002_MIROFISH", "01_infrastructure", "create simulation report schema")

# Seq 02: knowledge_graph
create_seq("002_MIROFISH", "knowledge graph")
create_task("002_MIROFISH", "02_knowledge_graph", "build document chunker and embedder")
create_task("002_MIROFISH", "02_knowledge_graph", "build entity relation extractor")
create_task("002_MIROFISH", "02_knowledge_graph", "build neo4j writer")

# Seq 03: swarm
create_seq("002_MIROFISH", "swarm")
create_task("002_MIROFISH", "03_swarm", "build agent personality generator")
create_task("002_MIROFISH", "03_swarm", "build simulation runner")
create_task("002_MIROFISH", "03_swarm", "build report generator")

# Seq 04: api
create_seq("002_MIROFISH", "api")
create_task("002_MIROFISH", "04_api", "build rest api")
create_task("002_MIROFISH", "04_api", "verify end to end")

# ============================================================
# PHASE 003: OPENCLAW (3 sequences, 13 tasks)
# ============================================================
print("\n=== PHASE 003: OPENCLAW ===")

# Seq 01: channels
create_seq("003_OPENCLAW", "channels")
create_task("003_OPENCLAW", "01_channels", "create openclaw scaffold")
create_task("003_OPENCLAW", "01_channels", "build channel abstraction")
create_task("003_OPENCLAW", "01_channels", "build telegram channel")
create_task("003_OPENCLAW", "01_channels", "build slack channel")
create_task("003_OPENCLAW", "01_channels", "build discord channel")

# Seq 02: skills
create_seq("003_OPENCLAW", "skills")
create_task("003_OPENCLAW", "02_skills", "build status skill")
create_task("003_OPENCLAW", "02_skills", "build brief skill")
create_task("003_OPENCLAW", "02_skills", "build fest skill")
create_task("003_OPENCLAW", "02_skills", "build simulate skill")
create_task("003_OPENCLAW", "02_skills", "build approve skill")

# Seq 03: scheduler
create_seq("003_OPENCLAW", "scheduler")
create_task("003_OPENCLAW", "03_scheduler", "build daily cron")
create_task("003_OPENCLAW", "03_scheduler", "build rest api")
create_task("003_OPENCLAW", "03_scheduler", "create config template")

# ============================================================
# PHASE 004: DASHBOARD (2 sequences, 7 tasks)
# ============================================================
print("\n=== PHASE 004: DASHBOARD ===")

# Seq 01: scaffold
create_seq("004_DASHBOARD", "scaffold")
create_task("004_DASHBOARD", "01_scaffold", "create nextjs app")
create_task("004_DASHBOARD", "01_scaffold", "build api proxy layer")

# Seq 02: panels
create_seq("004_DASHBOARD", "panels")
create_task("004_DASHBOARD", "02_panels", "build mode governance panel")
create_task("004_DASHBOARD", "02_panels", "build festival manager panel")
create_task("004_DASHBOARD", "02_panels", "build simulation panel")
create_task("004_DASHBOARD", "02_panels", "build atlas clusters view")
create_task("004_DASHBOARD", "02_panels", "build ai usage counter")

# ============================================================
# PHASE 005: WORKFLOWS_METERING (2 sequences, 7 tasks)
# ============================================================
print("\n=== PHASE 005: WORKFLOWS_METERING ===")

# Seq 01: workflows
create_seq("005_WORKFLOWS_METERING", "workflows")
create_task("005_WORKFLOWS_METERING", "01_workflows", "build idea to simulation workflow")
create_task("005_WORKFLOWS_METERING", "01_workflows", "build stall detector")
create_task("005_WORKFLOWS_METERING", "01_workflows", "build daily automation loop")

# Seq 02: metering
create_seq("005_WORKFLOWS_METERING", "metering")
create_task("005_WORKFLOWS_METERING", "02_metering", "build metering module")
create_task("005_WORKFLOWS_METERING", "02_metering", "wire metering into adapters")
create_task("005_WORKFLOWS_METERING", "02_metering", "build metering endpoints")
create_task("005_WORKFLOWS_METERING", "02_metering", "add metering schemas")

# ============================================================
# PHASE 006: INSTALLER (2 sequences, 6 tasks)
# ============================================================
print("\n=== PHASE 006: INSTALLER ===")

# Seq 01: docker
create_seq("006_INSTALLER", "docker")
create_task("006_INSTALLER", "01_docker", "write root docker compose")
create_task("006_INSTALLER", "01_docker", "write dockerfiles")
create_task("006_INSTALLER", "01_docker", "write env example")

# Seq 02: installer
create_seq("006_INSTALLER", "02_installer")
create_task("006_INSTALLER", "02_installer", "write installer script")
create_task("006_INSTALLER", "02_installer", "write aegis seed script")
create_task("006_INSTALLER", "02_installer", "write documentation")

print("\n=== STRUCTURE CREATION COMPLETE ===")
