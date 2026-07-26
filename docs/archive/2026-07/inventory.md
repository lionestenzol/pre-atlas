# Operating-Stack Inventory

Read-only snapshot of this Windows machine (user `bruke`). Point-in-time: 2026-05-23. Nothing was started, stopped, or changed. Goal: see what's running, what's runnable, and what would need daemonizing for the machine to be "ambient" (everything up in the background without manual starts).

**Headline:** Your Atlas stack is already mostly ambient. A Task Scheduler task `Atlas-Autostart` (runs at logon) launches 12 services via `scripts\start_atlas.ps1`, and Postgres runs as a boot service. The main hole is `atlas\serve.py` (:8887) and some Docker-dependent extras. Details below.

---

## 1. Running processes

### Atlas stack (your servers, all live now)
Listener PID is the one bound to the port; each also has a wrapper/child or two.

| Port | Service | PID | Command |
|---|---|---|---|
| 3000 | mosaic-dashboard | 8792 | `node next dev` (Next.js) |
| 3001 | delta-kernel | 6128 | `node tsx src/api/server.ts` |
| 3002 | aegis-fabric | 7132 | `node --env-file=.env --import tsx/esm src/api/server.ts` |
| 3004 | openclaw | 25132 | `python -m uvicorn openclaw.api:app` |
| 3005 | mosaic-orchestrator | 25140 | `python -m uvicorn mosaic.main:app` |
| 3006 | inPACT (UI) | 23688 | `node http-server . -p 3006 -c-1 --cors` |
| 3007 | code-converter | 24184 | `python server.py` |
| 3008 | uasc-executor | 25024 | `python server.py --port 3008` |
| 3009 | cortex | 5744 | `python -m uvicorn cortex.main:app` |
| 3010 | optogon | 26108 | `python -m uvicorn optogon.main:app` |
| 3030 | blueprint-generator | 7588 | `node next dev -p 3030` |
| 3050 | canvas-engine | 27464 | `node tsx watch src/server.ts` |
| 8887 | atlas/serve.py | 36932 | `pythonw C:\Users\bruke\atlas\serve.py` (substrate dashboard) |

### MCP servers (client-spawned, NOT ambient daemons)
These appear as many duplicate `python`/`node` processes because each MCP client (Claude Desktop, Claude Code, Codex) spawns its own copy. They live and die with the client. They do not need daemonizing.

| Server | Cmd (path) | ~Instances |
|---|---|---|
| everything | `node mcp-servers\everything\dist\index.js` | 4 |
| codex | `node @openai/codex ... mcp-server` | 4 |
| competitor-monitor | `python (Scrapling\.venv) mcp-servers\competitor-monitor\server.py` | 8 |
| weather | `python weather\.venv weather.py` | 6 |
| musescore | `python musescore-mcp\server\musescore_mcp.py` | 4 |
| blender-mcp | `python (Claude Extensions venv / uv cache) blender-mcp.exe` | several |
| android | `node android\mcp-server\src\index.js` | 1 |
| steerpop-android | `node projects\SteerPOP-Android\mcp-server\index.mjs` | 2 |
| playwright | `node @playwright/mcp@latest` | 2-4 |

Vendor/system processes (Adobe, Waves, MSI, Nahimic, Epic, Google Drive, OneDrive, iTunes/Apple, CodeMeter, Immersed, VMware) are excluded as not yours to manage.

---

## 2. Listening ports (localhost)

### Yours (Atlas)
| Port | Proc | Identity |
|---|---|---|
| 3000 | node | mosaic-dashboard (Next.js) |
| 3001 | node | delta-kernel API |
| 3002 | node | aegis-fabric API |
| 3004 | python | openclaw |
| 3005 | python | mosaic-orchestrator |
| 3006 | node | inPACT UI (http-server) |
| 3007 | python | code-converter |
| 3008 | python | uasc-executor |
| 3009 | python | cortex |
| 3010 | python | optogon |
| 3030 | node | blueprint-generator (Next.js) |
| 3050 | node | canvas-engine |
| 8887 | pythonw | atlas/serve.py (substrate dashboard) |

### Infra
| Port | Proc | Identity |
|---|---|---|
| 5432 | postgres | PostgreSQL 12 (Atlas DB) |
| 32233 | Everything | Everything file-index HTTP/ETP server |

### Other apps / vendor (not yours to manage)
| Port | Proc | Best guess |
|---|---|---|
| 135, 7680 | svchost | Windows RPC / service host |
| 139, 445, 1462 | System | SMB / file sharing |
| 902, 912 | vmware-authd | VMware Workstation |
| 5040 | svchost | Windows |
| 5354 | mDNSResponder | Bonjour (Apple) |
| 6985 | WavesLocalServer | Waves Audio |
| 7679 | GoogleDriveFS | Google Drive |
| 9080 | NahimicService | MSI audio |
| 14630 | MSI_Companion_Service | MSI |
| 19294 | AdobeCollabSync | Adobe Acrobat |
| 22350 / 22352 | CodeMeter / CmWebAdmin | License dongle (audio plugins) |
| 24563 / 35783 | Epic*  | Epic Games launcher / online services |
| 26822 / 32683 / 33683 | MSI.* | MSI Terminal / Central server |
| 27015 | AppleMobileDeviceProcess | iTunes |
| 40001 | Immersed-service | Immersed VR |
| 42050 | OneDrive.Sync.Service | OneDrive |
| 49664-49692 | lsass / wininit / svchost / spoolsv / jhi_service / services | Windows RPC endpoints (system) |

---

## 3. Runnable servers / apps

### Atlas stack (the 12 in `scripts\start_atlas.ps1`, low-deps-first order)
| Port | Service | Dir | Stack | Entry |
|---|---|---|---|---|
| 3001 | delta-kernel | `services\delta-kernel` | TS/Express | `npx tsx src/api/server.ts` |
| 3002 | aegis-fabric | `services\aegis-fabric` | TS/Express (+Postgres) | `node --env-file=.env --import tsx/esm src/api/server.ts` |
| 3004 | openclaw | `services\openclaw` | Python/FastAPI | `uvicorn openclaw.api:app` |
| 3005 | mosaic-orchestrator | `services\mosaic-orchestrator` | Python/FastAPI | `uvicorn mosaic.main:app` |
| 3006 | inPACT | `apps\inpact` | static HTML/JS | `http-server . -p 3006` |
| 3007 | code-converter | `apps\code-converter` | Python/FastAPI | `python server.py` |
| 3008 | uasc-executor | `services\uasc-executor` | Python/HTTP | `python server.py --port 3008` |
| 3009 | cortex | `services\cortex` | Python/FastAPI | `uvicorn cortex.main:app` |
| 3010 | optogon | `services\optogon` | Python/FastAPI | `uvicorn optogon.main:app` |
| 3030 | blueprint-generator | `apps\blueprint-generator` | Next.js | `npx next dev -p 3030` |
| 3050 | canvas-engine | `services\canvas-engine` | TS/Express+Vite | `npm run dev` |
| 3000 | mosaic-dashboard | `services\mosaic-dashboard` | Next.js | `npm run dev` |

### Atlas - present but NOT in the autostart set
| Service | Dir | Stack | Why not started |
|---|---|---|---|
| atlas/serve.py | `C:\Users\bruke\atlas` | Python http.server :8887 | Running ad-hoc; not referenced by any task/script |
| mirofish | `services\mirofish` | Python/FastAPI :3003 | Needs Neo4j (Docker), skipped by start_atlas |
| ws-gateway | `services\ws-gateway` | Node NATS<->Socket.IO | Needs NATS (Docker), skipped by start_atlas |
| perception | `services\perception` | Python | No port wired into autostart (has BUILD_LOG) |
| triangulation | `services\triangulation` | Python | No port wired into autostart (has BUILD_LOG) |

### Other projects (sampled - 100+ folders exist under `C:\Users\bruke`; these are workspaces, not ambient daemons)
| Project | Entry | Stack | Port | Running? |
|---|---|---|---|---|
| n8n | `.n8n` (npx n8n) | Node | 5678 | no |
| privateGPT / private-gpt | `docker-compose.yaml` | Docker | - | no (Docker down) |
| POLARIS | `docker-compose.yml` | Docker | - | no |
| firecrawl | `tools\anatomy-research\firecrawl\docker-compose.yaml` | Docker | - | no |
| STRUDEL Loop Engine | Desktop `STRUDEL\launch-loop-engine.bat` | batch | - | no |
| gpt4all | Desktop `gpt4all\bin\chat.exe` | desktop app | - | no |
| weather / competitor-monitor / musescore | see MCP table above | Python | n/a | on-demand (MCP) |

**Heavy dirs that inflate file counts (not projects):** `anaconda3`, `*.venv` / `site-packages`, `node_modules`, `.cursor\extensions`, `.claude\plugins`, `.codex`. Raw counts under the profile: 1,834 `package.json` and 502 `main/server/app/run.py` - the large majority are inside these, not real entry points. Real Atlas code = the 12 services + `apps\`.

---

## 4. Existing services / scheduled tasks

### Windows services (user-installed)
| Name | State | Start | Note |
|---|---|---|---|
| postgresql-x64-12 | Running | Auto | Atlas DB - starts at BOOT, before login |
| com.docker.service | Stopped | Manual | Docker Desktop engine - off |
| VMware NAT Service | Running | Auto | VMware |
| Antares Central Services, Bonjour, Adobe ARM, GameInput | Running | Auto | vendor |

### Scheduled tasks - yours (healthy)
| Task | Trigger | Action |
|---|---|---|
| `Atlas-Autostart` | At logon | `start_atlas.ps1` (the daemonizer for the 12 services) |
| `PreAtlas-DailyPipeline` | daily | `python run_daily.py` (cognitive-sensor) |
| `PreAtlas-CycleboardRetry` | - | `python cycleboard_push.py` |
| `PreAtlas-Governor-Daily` | daily | `run_governor_daily.ps1` |
| `PreAtlas-Governor-Weekly` | weekly | `run_governor_weekly.ps1` |
| `OllamaHardenReminder` | - | opens `ollama-lockdown\REMINDER.md` |

### Scheduled tasks - yours (STALE, 8 total)
All from a 2026-05-02 session. They point to `.claude\worktrees\` paths that still exist (`pedantic-fermi-e58d26`, `vigorous-hoover-3db0c2`) and the referenced scripts are present - so they are not erroring, just dormant cruft.
- `AtlasExoTick_20260502-093718_{30s,2m,5m,10m,15m}` (5) -> exoskeleton `exo.ps1`. Spent one-shot timers: each fired once on 2026-05-02 (LastTaskResult 0, no NextRunTime) and will not run again.
- `AtlasPlanWatcher_optogon-restore`, `AtlasPlanWatcher_v0_3` (2) -> `plan-check.ps1` against that session's plan files.
- `Optogon Audit` (1) -> `audit.ps1` in the older worktree.

### Process managers
pm2, nssm, ngrok, caddy: **none installed.** Daemonization is 100% via the one Task Scheduler logon task + the Postgres service. Docker is installed but its service is Stopped/Manual.

---

## 5. Dashboards / front doors

| Front door | URL / path | Notes |
|---|---|---|
| inPACT (your main UI) | http://127.0.0.1:3006 | auto-opened by start_atlas when up |
| Mosaic Dashboard | http://127.0.0.1:3000 | Next.js |
| Cortex API health | http://127.0.0.1:3009/health | |
| Atlas substrate dashboard | http://127.0.0.1:8887 | served by `atlas\serve.py` -> `atlas\index.html` |
| Static maps (open via file://) | `Pre Atlas\` root | `atlas_boot.html`, `system-map.html`, `system-tour.html`, `pre-atlas-pattern-map.html` |
| Desktop launcher | `Atlas.lnk` | runs `start_atlas.ps1` (also a Start Menu shortcut per install script) |
| Other local shortcuts | `GPT4All.lnk`, `STRUDEL Loop Engine.lnk`, `Loop Pad.lnk` | separate apps |

---

## 6. Gaps

**Runnable but not auto-started:** `atlas\serve.py` (:8887), `mirofish` (:3003), `ws-gateway`, `perception`, `triangulation`.

**Running ad-hoc, would NOT return after reboot:** `atlas\serve.py` (:8887) is the real one - it's in no task and no service. The 12 Atlas services DO return (Atlas-Autostart at login). MCP servers return when their client launches.

**Timing caveat:** Postgres returns at BOOT (service). The Atlas stack returns at LOGIN (logon task), not boot - so if the box reboots and nobody logs in, the app stack is down while Postgres is up.

**Infra holes:** Redis is not bound (:6379 absent) though aegis is up without it. Docker is Stopped, so anything Docker-bound (mirofish, ws-gateway, privateGPT, firecrawl, POLARIS) cannot run.

**Recommended boot order if fully daemonized** (mirrors start_atlas.ps1, which already does low-deps-first):
1. PostgreSQL (already a boot service)  [+ Redis, if aegis needs it]
2. delta-kernel :3001 (core state engine)
3. aegis-fabric :3002 (depends on Postgres)
4. workers: openclaw :3004, mosaic-orch :3005, code-converter :3007, uasc :3008, cortex :3009, optogon :3010
5. UIs last: inPACT :3006, blueprint :3030, canvas-engine :3050, mosaic-dashboard :3000
6. atlas/serve.py :8887
- Optional / Docker: Docker Desktop -> Neo4j -> mirofish :3003; NATS -> ws-gateway

---

## What to daemonize first

1. **`atlas\serve.py` (:8887)** - the only Atlas surface not in autostart; add one line to `start_atlas.ps1` so the substrate dashboard survives reboot like the rest.
2. **Clear the 8 stale scheduled tasks** - leftovers from a 2026-05-02 session (the exo ticks are spent one-shot timers; the rest target an old worktree's plan files). Nothing is breaking, but removing them de-noises Task Scheduler and makes "what runs" legible.
3. **Decide Redis** - either run it (as a service, if aegis-fabric actually needs it) or confirm aegis runs fine without it and stop expecting it.
4. **Docker autostart -> mirofish + ws-gateway** - if you want the prediction engine and NATS bridge ambient, set `com.docker.service` to Auto and add Neo4j/NATS bring-up; otherwise this stays intentionally out (as it is today).
5. **Prove `Atlas-Autostart` survives a real reboot** - it's registered (AtLogon, RunLevel Limited) but currently the stack is up from a manual run; one reboot test confirms the whole 12-service stack returns hands-free.
