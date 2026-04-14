"""Fill FESTIVAL_OVERVIEW.md and TODO.md."""
import subprocess, tempfile, os

FEST_DIR = "/root/festival-project/festivals/planning/mosaic-platform-MP0001"

def write_wsl(path, content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    wsl_tmp = tmp.replace('\\', '/').replace('C:', '/mnt/c')
    subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", f"cp '{wsl_tmp}' '{path}'"], capture_output=True, text=True)
    os.unlink(tmp)

write_wsl(f"{FEST_DIR}/FESTIVAL_OVERVIEW.md", """# Mosaic Integration Platform — Festival Overview

## Summary
Unify Pre Atlas systems into a single orchestration platform with swarm simulation (MiroFish), multi-channel messaging (OpenClaw), unified dashboard, and AI task execution with metering.

## Current Status
Phase 1 (Orchestrator Core) COMPLETE. Phase 2 (MiroFish) is NEXT.

## Phase Map
1. 001_ORCHESTRATOR_CORE — COMPLETE (FastAPI on :3005, 4 clients, Claude adapter)
2. 002_MIROFISH — Swarm engine on :3003 (Neo4j + Ollama)
3. 003_OPENCLAW — Multi-channel gateway on :3004 (Telegram/Slack/Discord)
4. 004_DASHBOARD — Next.js UI on :3000
5. 005_WORKFLOWS_METERING — Automation + metering
6. 006_INSTALLER — Docker Compose deployment

## Timeline
9 weeks total, Phases 2-3 can run in parallel.
""")

write_wsl(f"{FEST_DIR}/TODO.md", """# Mosaic Platform TODO

## Immediate
- [x] Complete Phase 1 (Orchestrator Core)
- [ ] Execute Phase 2 (MiroFish) via /weapon
- [ ] Execute Phase 3 (OpenClaw) — can parallel with Phase 2

## Upcoming
- [ ] Phase 4 (Dashboard) after 2+3 complete
- [ ] Phase 5 (Workflows + Metering) after dashboard
- [ ] Phase 6 (Installer) final phase
""")

print("Done!")
