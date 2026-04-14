"""Clean up duplicate/template task files in Mosaic festival.
The fest CLI auto-numbered some files differently. We need to:
1. Remove unfilled template duplicates (the ones fest auto-created with different numbers)
2. Fill SEQUENCE_GOAL.md files
3. Fill remaining unfilled task files for Phases 003-006
"""
import subprocess
import tempfile
import os
import re

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def run_wsl(cmd):
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def write_wsl(path, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cp '{wsl_tmp}' '{path}'"],
                   capture_output=True, text=True)
    os.unlink(tmp)

def read_wsl(path):
    return run_wsl(f"cat '{path}'")

# Step 1: Find all files with [REPLACE: markers
print("=== Finding files with unfilled markers ===")
files_with_markers = run_wsl(
    f"cd {FEST_DIR} && grep -rl '\\[REPLACE:' --include='*.md' | sort"
).split('\n')

print(f"Found {len(files_with_markers)} files with markers")

# Step 2: For each sequence, identify and remove duplicate task files
# (ones created by fest with template markers where we already wrote content)
phases_to_check = ["002_MIROFISH", "003_OPENCLAW", "004_DASHBOARD", "005_WORKFLOWS_METERING", "006_INSTALLER"]

for phase in phases_to_check:
    sequences = run_wsl(f"ls -d {FEST_DIR}/{phase}/*/ 2>/dev/null | xargs -I{{}} basename {{}}").split('\n')
    for seq in sequences:
        if not seq:
            continue
        seq_dir = f"{FEST_DIR}/{phase}/{seq}"
        files = run_wsl(f"ls {seq_dir}/*.md 2>/dev/null").split('\n')

        # Find files with markers
        filled = []
        unfilled = []
        for f in files:
            if not f or f.endswith('SEQUENCE_GOAL.md'):
                continue
            basename = os.path.basename(f)
            # Skip quality gate files
            if any(x in basename for x in ['testing', 'review', 'iterate', 'fest_commit']):
                continue
            content = read_wsl(f)
            if '[REPLACE:' in content:
                unfilled.append(f)
            else:
                filled.append(f)

        # If we have both filled and unfilled versions of the "same" task, remove unfilled
        if filled and unfilled:
            # Check if unfilled are just template duplicates
            for uf in unfilled:
                basename = os.path.basename(uf)
                # Check if there's a filled version with similar name
                uf_name = re.sub(r'^\d+_', '', basename)
                has_filled_version = False
                for ff in filled:
                    ff_name = re.sub(r'^\d+_', '', os.path.basename(ff))
                    if ff_name == uf_name:
                        has_filled_version = True
                        break

                if has_filled_version:
                    print(f"  Removing duplicate: {uf}")
                    run_wsl(f"rm '{uf}'")
                else:
                    print(f"  Unfilled (no duplicate): {uf}")

print("\n=== Filling SEQUENCE_GOAL.md files ===")

sequence_goals = {
    "002_MIROFISH/01_infrastructure": ("Infrastructure", "Set up MiroFish project scaffold, Docker Compose for Neo4j + Ollama, and schema contract."),
    "002_MIROFISH/02_knowledge_graph": ("Knowledge Graph", "Build document chunking, embedding, entity extraction, and Neo4j graph storage."),
    "002_MIROFISH/03_swarm": ("Swarm", "Build agent personality generator, tick-based simulation runner, and report generator."),
    "002_MIROFISH/04_api": ("API", "Build MiroFish REST API and verify end-to-end pipeline."),
    "003_OPENCLAW/01_channels": ("Channels", "Build channel abstraction and Telegram, Slack, Discord implementations."),
    "003_OPENCLAW/02_skills": ("Skills", "Build /status, /brief, /fest, /simulate, /approve skills."),
    "003_OPENCLAW/03_scheduler": ("Scheduler", "Build daily cron, REST API, and config template."),
    "004_DASHBOARD/01_scaffold": ("Scaffold", "Create Next.js app and API proxy layer."),
    "004_DASHBOARD/02_panels": ("Panels", "Build all dashboard panels: mode, festival, simulation, atlas, usage."),
    "005_WORKFLOWS_METERING/01_workflows": ("Workflows", "Build idea-to-simulation, stall detector, and daily automation loop."),
    "005_WORKFLOWS_METERING/02_metering": ("Metering", "Build metering module, wire into adapters, and add endpoints + schemas."),
    "006_INSTALLER/01_docker": ("Docker", "Write root docker-compose.yml, Dockerfiles, and .env.example."),
    "006_INSTALLER/02_installer": ("Installer", "Write installer script, Aegis seed script, and documentation."),
}

for path, (name, desc) in sequence_goals.items():
    write_wsl(f"{FEST_DIR}/{path}/SEQUENCE_GOAL.md", f"""# Sequence Goal: {name}

## Objective
{desc}

## Deliverables
See task files in this sequence for detailed implementation steps.
""")
    print(f"  Filled: {path}/SEQUENCE_GOAL.md")

print("\n=== Filling remaining unfilled task files ===")

# Phase 003-006 task content (brief but sufficient for weapon)
task_content = {
    # Phase 003: OpenClaw
    "003_OPENCLAW/01_channels/create_openclaw_scaffold": """# Task: Create OpenClaw Package Scaffold

## Objective
Create services/openclaw/ with FastAPI on port 3004.

## Requirements
- Mirror mosaic-orchestrator structure
- FastAPI with uvicorn
- Config from env vars (channel tokens)

## Implementation Steps
1. Create services/openclaw/ with pyproject.toml
2. Create src/openclaw/__init__.py, config.py, main.py, api.py
3. Health endpoint at GET /api/v1/health

## Definition of Done
- [ ] FastAPI starts on port 3004
- [ ] Health endpoint returns 200
""",
    "003_OPENCLAW/01_channels/build_channel_abstraction": """# Task: Build Channel Abstraction

## Objective
Create base channel interface for multi-platform messaging.

## Requirements
- Abstract base: send_message, register_command, start, stop
- Message dataclass with common fields

## Implementation Steps
1. Create src/openclaw/channels/base.py
2. Define Channel ABC with required methods
3. Define Message, Command dataclasses

## Definition of Done
- [ ] Base channel class defined
- [ ] Message types defined
""",
    "003_OPENCLAW/01_channels/build_telegram_channel": """# Task: Build Telegram Channel

## Objective
Implement Telegram bot channel using python-telegram-bot.

## Requirements
- Webhook-based message handling
- Command registration (/status, /brief, etc.)
- Message formatting for Telegram markdown

## Implementation Steps
1. Create src/openclaw/channels/telegram.py
2. Implement TelegramChannel(Channel)
3. Add webhook handler, command parser

## Definition of Done
- [ ] Telegram bot responds to /status
- [ ] Messages formatted correctly
""",
    "003_OPENCLAW/01_channels/build_slack_channel": """# Task: Build Slack Channel

## Objective
Implement Slack channel using slack-bolt.

## Requirements
- Event subscription
- Slash command handling
- Block Kit message formatting

## Implementation Steps
1. Create src/openclaw/channels/slack.py
2. Implement SlackChannel(Channel)

## Definition of Done
- [ ] Slack app responds to slash commands
""",
    "003_OPENCLAW/01_channels/build_discord_channel": """# Task: Build Discord Channel

## Objective
Implement Discord channel using discord.py.

## Requirements
- Gateway connection
- Slash command handling

## Implementation Steps
1. Create src/openclaw/channels/discord.py
2. Implement DiscordChannel(Channel)

## Definition of Done
- [ ] Discord bot responds to commands
""",
    "003_OPENCLAW/02_skills/build_status_skill": """# Task: Build /status Skill

## Objective
Build skill that returns current mode, lanes, and festival status.

## Requirements
- Call orchestrator GET /api/v1/status
- Format response per channel

## Implementation Steps
1. Create src/openclaw/skills/status.py
2. Fetch from orchestrator, format, return

## Definition of Done
- [ ] /status returns mode + festival info
""",
    "003_OPENCLAW/02_skills/build_brief_skill": """# Task: Build /brief Skill

## Objective
Build skill that returns daily brief.

## Implementation Steps
1. Create src/openclaw/skills/brief.py
2. Read daily_brief.md via cognitive client

## Definition of Done
- [ ] /brief returns formatted daily brief
""",
    "003_OPENCLAW/02_skills/build_fest_skill": """# Task: Build /fest Skill

## Objective
Proxy festival CLI commands through messaging.

## Implementation Steps
1. Create src/openclaw/skills/fest.py
2. Proxy: fest status, fest next, fest progress

## Definition of Done
- [ ] /fest status returns festival progress
""",
    "003_OPENCLAW/02_skills/build_simulate_skill": """# Task: Build /simulate Skill

## Objective
Trigger MiroFish simulation from messaging.

## Implementation Steps
1. Create src/openclaw/skills/simulate.py
2. POST to MiroFish /api/v1/simulations

## Definition of Done
- [ ] /simulate starts a new simulation
""",
    "003_OPENCLAW/02_skills/build_approve_skill": """# Task: Build /approve Skill

## Objective
Access Aegis approval queue from messaging.

## Implementation Steps
1. Create src/openclaw/skills/approve.py
2. GET/POST Aegis approvals

## Definition of Done
- [ ] /approve lists and handles pending approvals
""",
    "003_OPENCLAW/03_scheduler/build_daily_cron": """# Task: Build Daily Cron

## Objective
Post daily brief at 9:30 AM, detect stalls in CLOSURE mode.

## Implementation Steps
1. Create src/openclaw/scheduler.py
2. Schedule: 9:30 AM post brief to all channels
3. CLOSURE: check 48h no completion, post trimming proposal

## Definition of Done
- [ ] Brief posted at scheduled time
- [ ] Stall detection works in CLOSURE mode
""",
    "003_OPENCLAW/03_scheduler/build_rest_api": """# Task: Build OpenClaw REST API

## Objective
Add REST endpoints for programmatic notification.

## Implementation Steps
1. Add to api.py: POST /api/v1/notify, GET /api/v1/channels, GET /api/v1/health

## Definition of Done
- [ ] POST /notify sends message to specified channels
- [ ] GET /channels lists connected channels
""",
    "003_OPENCLAW/03_scheduler/create_config_template": """# Task: Create Config Template

## Objective
Create config.yaml template for channel tokens.

## Implementation Steps
1. Create services/openclaw/config.yaml.example
2. Document all env vars (TELEGRAM_TOKEN, SLACK_TOKEN, etc.)

## Definition of Done
- [ ] Config template documents all variables
""",
    # Phase 004: Dashboard
    "004_DASHBOARD/01_scaffold/create_nextjs_app": """# Task: Create Next.js App

## Objective
Scaffold services/mosaic-dashboard/ with Next.js + TypeScript + Tailwind on port 3000.

## Implementation Steps
1. npx create-next-app@latest services/mosaic-dashboard --typescript --tailwind
2. Configure port 3000

## Definition of Done
- [ ] Next.js starts on port 3000
""",
    "004_DASHBOARD/01_scaffold/build_api_proxy_layer": """# Task: Build API Proxy Layer

## Objective
Proxy API calls from dashboard to backend services.

## Implementation Steps
1. Create Next.js API routes proxying to :3001, :3003, :3005
2. No CORS needed (same-origin)

## Definition of Done
- [ ] /api/delta/* proxies to :3001
- [ ] /api/mirofish/* proxies to :3003
- [ ] /api/mosaic/* proxies to :3005
""",
    "004_DASHBOARD/02_panels/build_mode_governance_panel": """# Task: Build Mode & Governance Panel

## Objective
Show current mode, risk, lanes, countdown with color coding.

## Implementation Steps
1. Create components/ModePanel.tsx
2. Fetch from /api/v1/status, poll every 30s
3. Color-code by mode

## Definition of Done
- [ ] Mode panel shows current state
- [ ] Auto-refreshes every 30s
""",
    "004_DASHBOARD/02_panels/build_festival_manager_panel": """# Task: Build Festival Manager Panel

## Objective
Show festival progress, task list, Execute Next button, cut list in CLOSURE.

## Implementation Steps
1. Create components/FestivalPanel.tsx
2. Show progress bars, task list from festival client

## Definition of Done
- [ ] Festival progress visible
- [ ] Execute Next triggers Claude adapter
""",
    "004_DASHBOARD/02_panels/build_simulation_panel": """# Task: Build Simulation Panel

## Objective
Upload doc, start simulation, show progress, D3.js consensus visualization.

## Implementation Steps
1. Create components/SimulationPanel.tsx
2. File upload → POST /simulations
3. D3.js consensus chart

## Definition of Done
- [ ] Can start simulation from UI
- [ ] Consensus visualization renders
""",
    "004_DASHBOARD/02_panels/build_atlas_clusters_view": """# Task: Build Atlas Clusters View

## Objective
Plotly scatter plot of ideas (alignment vs effort).

## Implementation Steps
1. Create components/AtlasClusters.tsx
2. Fetch idea_registry.json data
3. Plotly scatter with alignment on X, effort on Y

## Definition of Done
- [ ] Scatter plot renders with real data
""",
    "004_DASHBOARD/02_panels/build_ai_usage_counter": """# Task: Build AI Usage Counter

## Objective
Live AI usage counter with pause button.

## Implementation Steps
1. Create components/UsageCounter.tsx
2. Fetch from /api/v1/metering/usage
3. Pause button calls POST /api/v1/metering/pause

## Definition of Done
- [ ] Live usage display
- [ ] Pause/resume works
""",
    # Phase 005: Workflows + Metering
    "005_WORKFLOWS_METERING/01_workflows/build_idea_to_simulation_workflow": """# Task: Build Idea-to-Simulation Workflow

## Objective
Auto-route high-alignment ideas to MiroFish simulation.

## Implementation Steps
1. Create src/mosaic/workflows/idea_simulation.py
2. alignment > 0.7 → MiroFish → confidence > 0.8: create Festival; 0.5-0.8: post to OpenClaw; < 0.5: archive

## Definition of Done
- [ ] High-alignment ideas auto-trigger simulation
- [ ] Results routed by confidence
""",
    "005_WORKFLOWS_METERING/01_workflows/build_stall_detector": """# Task: Build Stall Detector

## Objective
Detect 48h task stalls and generate cut lists.

## Implementation Steps
1. Create src/mosaic/workflows/stall_detector.py
2. Check festival progress, flag 48h gaps
3. CLOSURE mode: auto-apply via Aegis gate

## Definition of Done
- [ ] Stalls detected after 48h
- [ ] Cut list sent to OpenClaw
""",
    "005_WORKFLOWS_METERING/01_workflows/build_daily_automation_loop": """# Task: Build Daily Automation Loop

## Objective
Full daily automation: 6AM→10PM cycle.

## Implementation Steps
1. Create src/mosaic/workflows/daily_loop.py
2. Schedule: 6:00 read state → 6:05 atlas daily → 6:15 push → 9:30 brief → continuous dispatch → 10:00 PM summary
3. Check /api/daemon/status to avoid duplicate refreshes

## Definition of Done
- [ ] Daily loop runs all steps
- [ ] No duplicate refreshes with governance_daemon.ts
""",
    "005_WORKFLOWS_METERING/02_metering/build_metering_module": """# Task: Build Metering Module

## Objective
SQLite-based AI usage tracking.

## Implementation Steps
1. Create src/mosaic/metering/meter.py
2. SQLite ~/.mosaic/metering.db, table usage_log(id, ts, service, seconds, tokens, cost_usd)
3. Free tier: 3600s. Pause flag stops new AI dispatch

## Definition of Done
- [ ] Usage logged to SQLite
- [ ] Pause flag respected
""",
    "005_WORKFLOWS_METERING/02_metering/wire_metering_into_adapters": """# Task: Wire Metering into Adapters

## Objective
Track usage from Claude adapter and MiroFish calls.

## Implementation Steps
1. Add meter.log() calls to claude_adapter.py
2. Add meter.log() calls to MiroFish client

## Definition of Done
- [ ] All AI calls tracked in metering DB
""",
    "005_WORKFLOWS_METERING/02_metering/build_metering_endpoints": """# Task: Build Metering Endpoints

## Objective
Wire the existing placeholder endpoints in api.py.

## Implementation Steps
1. Implement GET /api/v1/metering/usage (returns daily/weekly/total)
2. Implement POST /api/v1/metering/pause (toggle AI dispatch)

## Definition of Done
- [ ] Usage endpoint returns correct data
- [ ] Pause/resume controls AI dispatch
""",
    "005_WORKFLOWS_METERING/02_metering/add_metering_schemas": """# Task: Add Metering Schemas

## Objective
Create MeteringUsage.v1.json and WorkflowEvent.v1.json.

## Implementation Steps
1. Create contracts/schemas/MeteringUsage.v1.json
2. Create contracts/schemas/WorkflowEvent.v1.json

## Definition of Done
- [ ] Both schemas in contracts/schemas/
- [ ] Follow draft-07 format
""",
    # Phase 006: Installer
    "006_INSTALLER/01_docker/write_root_docker_compose": """# Task: Write Root Docker Compose

## Objective
Single docker-compose.yml for all 10 services.

## Implementation Steps
1. Create root docker-compose.yml
2. Include: orchestrator, mirofish, openclaw, dashboard, delta-kernel, aegis + postgres, redis, neo4j, ollama
3. mosaic-net network, health checks

## Definition of Done
- [ ] docker compose up starts all services
- [ ] Health checks pass
""",
    "006_INSTALLER/01_docker/write_dockerfiles": """# Task: Write Dockerfiles

## Objective
Dockerfiles for all 6 app services.

## Implementation Steps
1. Create Dockerfile for each service
2. Python services: 3.11-slim, pip install, uvicorn
3. Node services: node:20-slim, npm ci, next start

## Definition of Done
- [ ] All 6 Dockerfiles build successfully
""",
    "006_INSTALLER/01_docker/write_env_example": """# Task: Write .env.example

## Objective
Document all environment variables needed.

## Implementation Steps
1. Create .env.example at repo root
2. List all tokens, keys, passwords, URLs with comments

## Definition of Done
- [ ] .env.example covers all services
""",
    "006_INSTALLER/02_installer/write_installer_script": """# Task: Write Installer Script

## Objective
One-command setup: installer.sh

## Implementation Steps
1. Create installer.sh
2. Detect OS, check Docker, pull Ollama models, cp .env.example .env, docker compose up -d, health wait, print URL

## Definition of Done
- [ ] installer.sh works on clean machine with Docker
""",
    "006_INSTALLER/02_installer/write_aegis_seed_script": """# Task: Write Aegis Seed Script

## Objective
Seed Aegis with Mosaic tenant, agents, and policies.

## Implementation Steps
1. Create seed-mosaic.sh
2. Create Mosaic tenant, 4 agents (orchestrator, mirofish, openclaw, dashboard), mode-aware policies

## Definition of Done
- [ ] Aegis seeded with correct tenant and agents
""",
    "006_INSTALLER/02_installer/write_documentation": """# Task: Write Documentation

## Objective
MOSAIC_README.md and update PRE_ATLAS_MAP.md.

## Implementation Steps
1. Create MOSAIC_README.md (architecture, setup, usage)
2. Update PRE_ATLAS_MAP.md with new services

## Definition of Done
- [ ] README covers full architecture
- [ ] PRE_ATLAS_MAP.md updated
""",
}

# Now find and fill all unfilled task files
for phase in phases_to_check:
    sequences = run_wsl(f"ls -d {FEST_DIR}/{phase}/*/ 2>/dev/null").split('\n')
    for seq_path in sequences:
        if not seq_path:
            continue
        seq_name = os.path.basename(seq_path.rstrip('/'))
        files = run_wsl(f"ls {seq_path}*.md 2>/dev/null").split('\n')

        for filepath in files:
            if not filepath or filepath.endswith('SEQUENCE_GOAL.md'):
                continue
            basename = os.path.basename(filepath)
            # Skip quality gate files
            if any(x in basename for x in ['testing', 'review', 'iterate', 'fest_commit']):
                continue

            content = read_wsl(filepath)
            if '[REPLACE:' in content:
                # Try to find matching content
                # Strip number prefix and .md suffix to get task name
                task_name = re.sub(r'^\d+_', '', basename.replace('.md', ''))
                key = f"{phase}/{seq_name}/{task_name}"

                if key in task_content:
                    write_wsl(filepath, task_content[key])
                    print(f"  Filled: {basename}")
                else:
                    print(f"  NO CONTENT for: {key} ({basename})")

print("\n=== CLEANUP COMPLETE ===")
