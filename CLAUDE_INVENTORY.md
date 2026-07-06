# CLAUDE INVENTORY — everything Claude Code touched on this machine

> **What this is.** A single pickup guide so that *anyone* — you, a future LLM, an
> engineer, or a beginner — can open any project Claude built on this machine and
> immediately know: **where it is · how to find it · how to start it · what it does ·
> how it works · whether it's alive.**
>
> **Why it exists.** Built 2026-06-25, the last CC session before a break, with no
> guarantee the conversation history survives. This file is the memory that replaces
> the chat. It is self-contained — you do not need any prior context to use it.
>
> **Machine:** Windows 11 · user `bruke` · home = `C:\Users\bruke`
> **Primary shell:** PowerShell 7 (also Git Bash). Paths with spaces (`Pre Atlas`) need quotes.
>
> **▶ Standalone CLI tools (bearings · gw · sigil · fest · skill-pytools):** see
> **[`C:\Users\bruke\TOOLS.md`](../TOOLS.md)** — the canonical index of every tool
> extracted into its own installable product: where each lives, its GitHub repo,
> how to install, and how to use it. Re-install all: `pwsh -File C:\Users\bruke\bin\install-atlas-tools.ps1`.

---

## 0. HOW TO USE THIS FILE (read this first)

### The universal "how do I start anything" pattern
Every runnable project here follows one of four shapes. To start *any* component:

1. **Open the folder.** Look for a `README.md`, `CLAUDE.md`, `HANDOFF*.md`, or
   `.claude/launch.json` — these tell you how it runs.
2. **`.claude/launch.json` is the boot truth.** If a folder has one, it lists every
   service's exact start command, port, and working directory. Read it first.
3. **Match the shape:**
   - **Node/TS service** → `cd <folder>` then `npm run dev` or `npx tsx <entry>.ts`
   - **Python service** → `cd <folder>` then `python -m uvicorn <pkg>.server:app --port <N>` (FastAPI) or `python server.py`
   - **Static HTML app** → `npx http-server <folder> -p <N> -c-1 --cors` then open `http://localhost:<N>`
   - **CLI tool** → run the named binary/script (e.g. `fest.exe`, `python orchestrate.py`)
4. **Find where it lives** with the `es` tool (instant machine-wide search — see §9).

### The three maps that already exist (use them, don't redo them)
| Map | Path | What it gives you |
|---|---|---|
| **atlas-manifest.yaml** | `Pre Atlas\atlas-manifest.yaml` | Interface-first map of the 35-system Pre Atlas monorepo: every API route, port, seam, contract. ~7.6k tokens — uploadable to an LLM whole. **The single best artifact for understanding Pre Atlas.** |
| **REPO_RUNDOWN.md** | `Pre Atlas\REPO_RUNDOWN.md` | Trusted structure map of the Pre Atlas repo. |
| **MEMORY.md** | `.claude\projects\C--Users-bruke-Pre-Atlas\memory\MEMORY.md` | Claude's persistent project memory — per-project status, "shipped/parked/retired", commit hashes, gotchas. 253 lines indexing ~120 topic files in the same folder. |

> If you only keep one thing: **`Pre Atlas\atlas-manifest.yaml` + this file.**

---

## 1. TIER 1 — Pre Atlas (the main system)

**What it is:** A personal behavioral-governance system — a federated monorepo of 35
systems. Architecture: **hub-and-spoke over SQLite + one-way HTTP seams**; JSON-Schema
contracts are the wire format. It is NOT an event bus.

- **Root:** `C:\Users\bruke\Pre Atlas` (note the space)
- **Sibling repo:** `C:\Users\bruke\pre-atlas` (hyphen) — hosts `delta-scp`. The two-repo split is load-bearing; don't merge them.
- **Database half:** `C:\Users\bruke\atlas` (private GitHub `lionestenzol/atlas`) — the substrate/state repo.
- **The hub:** `delta-kernel` (port 3001). ALL durable state lives here in SQLite. Every other service reads/writes through it.
- **6 modes (FSM):** `RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE`

### How to start Pre Atlas (three ways)
1. **Whole stack, scripted:** `Pre Atlas\scripts\start_atlas.ps1` (the autostart bundle; a Task-Scheduler self-heal re-spawns delta-kernel within 15 min if it crashes).
2. **Clickable boot page:** start the shell, then open the setup UI:
   ```powershell
   cd "C:\Users\bruke\Pre Atlas"
   npx http-server . -p 8888 -c-1 --cors    # atlas-shell
   # open http://localhost:8888/atlas-setup.html  → preset/per-service Start-Stop grid
   ```
3. **One service at a time:** read `Pre Atlas\.claude\launch.json` — it has the exact
   command for all 36 launch configs. Examples below.

### Pre Atlas port map (boot truth — from `.claude/launch.json`)
| Port | Service | Lang | Start (cwd is under `Pre Atlas\`) | Status |
|---|---|---|---|---|
| **3001** | **delta-kernel** (the hub) | TS/Express | `cd services/delta-kernel && npx tsx src/api/server.ts` | **ACTIVE** |
| 5173 | delta-web (its React UI) | Vite | `cd services/delta-kernel/web && npx vite` | active |
| 3002 | aegis-fabric (admin gateway/policy) | TS/Express | `cd services/aegis-fabric && npx tsx src/api/server.ts` | active |
| 3004 | openclaw | Python/FastAPI | `uvicorn openclaw.api:app --port 3004` (PYTHONPATH=src) | retired |
| 3005 | mosaic-orchestrator | Python/FastAPI | `uvicorn mosaic.main:app --port 3005` | retired |
| 3006 | inpact (the product UI) | static JS | `npx http-server apps/inpact -p 3006 -c-1 --cors` | active |
| 3007 | code-converter (Py→C++) | Python | `cd apps/code-converter && python server.py` | active ⚠ RCE risk |
| 3008 | uasc-executor | Python | `cd services/uasc-executor && python server.py --port 3008` | active |
| 3009 | cortex (autonomous exec) | Python/FastAPI | `uvicorn cortex.main:app --port 3009` | **gated OFF** |
| 3010 | optogon (path-runtime FSM) | Python/FastAPI | `cd services/optogon && uvicorn optogon.main:app --port 3010` | **gated OFF** |
| 3011 | lattice (tree/graph/timeline UI) | static JS | `npx http-server apps/lattice -p 3011 -c-1 --cors` | active |
| 3012 | delta-scp (repo→symbol map) | TS | in **hyphen repo**: `cd C:/Users/bruke/pre-atlas/services/delta-scp && npx tsx src/demo-server.ts` | active |
| 3050 | canvas-engine (URL→React clone) | TS/Express | `cd services/canvas-engine && npm run dev` | active |
| 3070 | search-stack (28-provider router) | Python/FastAPI+MCP | `uvicorn search_stack.server:app --port 3070` (`.venv`) | active |
| 3071 | memory-hub | Python/FastAPI | `uvicorn memory_hub.server:app --port 3071` (`.venv`) | active |
| 3072 | atlas-map-api (GPS substrate) | Python/FastAPI | `uvicorn atlas_map_api.server:app --port 3072` (`.venv`) | active |
| 3073 | droplist (capture→DAG executor) | Python/FastAPI | `uvicorn droplist.server:app --port 3073` | active |
| 3075 | triangulation | Python/FastAPI | `uvicorn triangulation.api:app --port 3075` | stub |
| 3000 | mosaic-dashboard | Next.js | `cd services/mosaic-dashboard && npm run dev` | retired |
| 3030 | blueprint-generator | Next.js | `cd apps/blueprint-generator && npx next dev -p 3030` | retired |
| 5000 | ai-exec-pipeline | Python | `cd apps/ai-exec-pipeline && python server.py` | retired |
| 8765 | cognitive-sensor triage-server | Python | `cd services/cognitive-sensor && python triage_server.py` | dormant |
| 8888 | atlas-shell (serves repo root + atlas-setup.html) | static | `npx http-server . -p 8888 -c-1 --cors` | active |
| 8893 | thread-cards (cognitive-sensor) | static | `npx http-server services/cognitive-sensor -p 8893` | active |
| 8894 | anatomy | static | `npx http-server anatomy -p 8894` | active |
| 8897 | audit-map | static | `npx http-server audit -p 8897` | active |
| 8898 | hydra (GitHub-crawling snake game) | static | `npx http-server apps/hydra -p 8898` | active |
| 8899 | hydra-engine (digests eaten repos) | Python | `python apps/hydra/engine.py` | active |
| 5174 | delta-scp-web (SaaS UI) | Vite | `cd apps/delta-scp-web && npx vite --port 5174 --strictPort` | active |
| — | crucix (dashboard "jarvis") | Node | `cd services/crucix && node server.mjs` (git **submodule**) | active |
| — | ws-gateway (NATS↔socket.io) | TS | not autostarted | dormant |

**Lifecycle flags you MUST respect** (from the manifest):
- **gated_default_off:** `cortex`, `optogon` — they only *act* behind env flags (`CORTEX_BRIDGE_APPLY=1`, `AUTO_TRIAGE_APPLY=1`). Default = propose-only.
- **stub, do not build on:** `perception`, `triangulation`.
- **retired, do not build on:** `mirofish`, `openclaw`, `mosaic-dashboard`, `mosaic-orchestrator`, `blueprint-generator`, `ai-exec-pipeline`.
- **security flags:** `code-converter` = RCE risk; `crucix`/`hydra`/`webos` = XSS (per the ship-readiness audit). Don't expose these publicly without hardening.

**Key gotchas (Pre Atlas):**
- `/api/*` writes on delta-kernel need a **Bearer key** — fetch it from the exempt `GET /api/auth/token`.
- `services/crucix` is a **git submodule** that sits `-dirty`. NEVER `git add -A` it — commit *inside* the submodule first, or exclude with `git add -A ':!services/crucix'`.
- The cycleboard "governance blob" (`GET/PUT /api/cycleboard` on :3001) is the ONE thing all behavioral surfaces read. `setup/apply.py` writes one profile into it.
- Current branch `feat/atlas-setup-ui` is **126 commits ahead of main** — most work isn't merged to main yet. See `BEARINGS_2026-06-25.md`.

---

## 2. TIER 2 — Standalone shipped projects (outside Pre Atlas)

Each card: **path · what · start · status.** Find any of them with `es <name> -p`.

### anatomy-saas — deterministic TSX→anatomy-HTML compiler
- **Path:** `C:\Users\bruke\anatomy-saas` (own git repo, root commit `e87df2e`)
- **What:** LLM-free compiler that turns a React/TSX component into an annotated anatomy HTML (leader lines + click-to-code drawers). The lead Tier-1 SaaS bet (~70% deterministic moat).
- **Start:** it's a compiler + test suite (84 tests, byte-identical output). Run its tests; serve the examples: `npx http-server C:\Users\bruke\anatomy-saas\packages\compiler\examples -p 8911 -c-1 --cors`.
- **Related skill:** `/anatomy-map` (`~/.claude/skills/anatomy-map`).
- **Status:** seq 01 SHIPPED 2026-06-25; seq 02/03 next.

### fest — Festival methodology CLI (native Windows binary)
- **Path:** binary `C:\Users\bruke\bin\fest.exe` (on PATH) · source+deps `C:\Users\bruke\fest-win` · data `C:\Users\bruke\festival-project`
- **What:** project-planning tool — festivals → phases → sequences → tasks with proof-gated done-conditions. Used by `/groundwork`, `/autopilot`, `/fest`.
- **Start:** just run `fest.exe <command>` from anywhere. Use flag form, not bare interactive TUI (it hangs headless). Doc: `fest-win\FEST_WINDOWS_PORT.md`.
- **Status:** SHIPPED 2026-06-25 (replaced the old WSL path).

### binre — reverse-engineering / debug pipeline
- **Path:** `C:\Users\bruke\binre`
- **What:** orchestrates DiE + Dependencies + Ghidra (headless) + x64dbg + Frida into a merged `report.json`.
- **Start:** `cd C:\Users\bruke\binre && python orchestrate.py`. E2E: `python tests/run_e2e.py`. Plan: `BINRE_TRACING_GROUNDWORK_PLAN.md`.
- **Status:** active (touched today 2026-06-25).

### web-audit (sitepull) — reverse-engineer & vendor a hosted site
- **Path:** `C:\Users\bruke\web-audit` (separate git repo)
- **What:** probe a URL, fingerprint its bundle, vendor assets, produce a zero-dependency local copy with stubbed backend. The `sitepull` CLI.
- **Start:** it's a Node CLI — see its README; `/web-audit` skill drives it. canvas-engine reads it via `WEB_AUDIT_ROOT` env.
- **Status:** shipped, stable.

### Scrapling — anti-bot web scraping (Python)
- **Path:** `C:\Users\bruke\Scrapling` (venv at `.venv`)
- **What:** Scrapling 0.4.7 — stealth headless scraping, Cloudflare/Turnstile bypass, spiders.
- **Start:** activate `.venv`, then use the `/scrapling-official` or `/web-extract-workflow` skill. Smoke tests in `C:\Users\bruke\scrapling-smoke`.
- **Status:** shipped 2026-05-02.

### competitor-monitor — track a competitor's site over time
- **Path:** template `~/templates/competitor-monitor` · skill `~/.claude/skills/competitor-monitor` · MCP server `~/mcp-servers/competitor-monitor` (commit `3299679`, registered) · output `~/intel/`
- **What:** weekly intel snapshots + optional 2-page competitive briefs ($0 marginal cost via claude CLI fallback).
- **Start:** use `/competitor-monitor` skill, or the MCP tools (`get_intel`, `diff_intel`, `get_brief`). Example data: `~/intel/plausible/`.
- **Status:** shipped 2026-05-03.

### MB3D / fractal toolchain (3 shipped tools)
- **m3p-to-fract** — `C:\Users\bruke\m3p-to-fract` · first open-source MB3D `.m3p` → Mandelbulber2 `.fract` converter (14 formulas, 10/10 tests). Start: it's a CLI converter, see README.
- **mb3d-blender** — `C:\Users\bruke\mb3d-blender` · Blender 4.x addon (`dist/mb3d_blender.zip`, 4 KB): pick `.m3p` → renders via Mb2 `--nogui` → loads PNG into Blender. Install the zip as a Blender addon.
- **mb3d_anim_demo** / **mandelbulber2_install** / **fractal-machine** — supporting fractal experiments.
- **Skills:** `/mandelbulb3d`, `/mandelbulber2`. Status: shipped 2026-05-12.

### Audio / DSP
- **nih-plug** — `C:\Users\bruke\nih-plug` · Rust→VST3→FL Studio loop. Start: `cargo xtask bundle gain --release` → FL auto-rescans `target/bundled`. Status: bootstrap done 2026-05-16.
- **fl356-sandbox** — `C:\Users\bruke\fl356-sandbox\unpack-runtime` · FL 3.5.6 deterministic WAV renderer. Start: `python32 fl356_render.py --song s.json --out s.wav`. Status: weapon-closed 2026-05-16.
- **surge-xt**, **airwindows** — reference plugin source clones (study material for nih-plug).

### three.js / creative-coding learning rigs
- **Paths:** `three-js`, `three-stack`, `three-hero`, `three-hero-v2`, `r3f`, `anime-js`, `remotion-test` (all under home).
- **What:** demo rigs comparing vanilla three.js vs React-Three-Fiber, anime.js, Remotion. The keeper findings live in the **skills** (`/three-js`, `/react-three-fiber`, `/anime-js`, `/remotion`), not the rigs.
- **Start:** each is a static/Vite demo — `npm install && npm run dev` or open the HTML. Status: reference, not products.

### Other standalone (lower-info — open the folder's README/CLAUDE.md to orient)
| Folder | Best guess | First move |
|---|---|---|
| `operator-system` | Operator/handoff system (the `/handoff-out` outbox lives here) | read its README |
| `STRUDEL` | Got real work 2026-06-25 (`enterprise-hardening` branch, `.audit/lattice/system-map.html`) but **no memory written** | **read its README/CLAUDE.md first** |
| `POLARIS`, `STEMai`, `META ATLAS`, `Creator Ecosystem OS` | Earlier projects, have `.claude/launch.json` (POLARIS, STEMai) | read `.claude/launch.json` + README |
| `element-map`, `task-manager`, `everything-claude-code` | Tooling/experiments | read README |
| `ngendo-re`, `ngendo-audit` | RE/audit work (Apr 2026) | read README |
| `musescore-mcp`, `musescore-mcp-bridge` | MuseScore MCP integration | `/musescore` MCP tools |
| `ollama-lockdown` | `~/ollama-lockdown/{lock,unlock,status}.ps1` — firewall-locks Ollama to localhost | run `unlock.ps1` to pull models |
| `screenshot-to-code` | cloned tool; needs `ANTHROPIC_API_KEY` + canvas-engine | read README |
| `disk-cleanup-scan` | today's cleanup scan output | data, not a service |

---

## 3. THE `.claude` FOLDER — your Claude Code toolkit

**Path:** `C:\Users\bruke\.claude` — this is where *Claude itself* is configured. The
"claude folder" you asked about. Everything here is global (applies to all projects).

### 3a. Skills (`~/.claude/skills/`) — invoked as `/<name>`
Your personal skills, by category. Each is a folder with a `SKILL.md`.

| Category | Skills |
|---|---|
| **Orchestration / planning** | `groundwork` (map→verify→plan), `autopilot` (drive a festival), `fest`, `weapon` (autonomous finisher), `project-finisher`, `verified-audit`, `deep-research`, `mini-ship` |
| **Code recon / search** | `code-recon` (**the recon tool — use this, never agents**), `search-first`, `search-stack`, `delta-scp` (repo→symbol map) |
| **Web extraction** | `web-audit`, `scrapling-official`, `web-extract-workflow`, `competitor-monitor` |
| **Creative coding** | `three-js`, `three-js-migrate`, `react-three-fiber`, `anime-js`, `anime-js-migrate`, `remotion`, `anatomy-map`, `mandelbulb3d`, `mandelbulber2`, `touchdesigner` |
| **Quality / process** | `tdd-workflow`, `security-review`, `coding-standards`, `frontend-patterns`, `backend-patterns`, `wasp-patterns`, `verification-loop`, `eval-harness`, `strategic-compact`, `continuous-learning-v2`, `cookbook` |
| **Bridges / handoff** | `claude-bridge` (web↔local via Google Drive), `handoff-out`, `codex-delegate` (dispatch to OpenAI Codex CLI, 38 skills) |
| **Misc** | `st3gg` (PNG steganography), `repo-inventory` (this skill) |

To see a skill's instructions: open `~/.claude/skills/<name>/SKILL.md`.

### 3b. Subagents (`~/.claude/agents/`)
`planner`, `architect`, `code-reviewer`, `security-reviewer`, `build-error-resolver`,
`refactor-cleaner`, `typescript-reviewer`, `python-reviewer`, `wasp-reviewer`,
`tdd-guide`, `claim-verifier` (adversarial fact-checker for agent reports).
> **Rule (locked):** route all code *recon* to the `code-recon` skill, NOT agents.
> `claim-verifier` is the exception — use it to adversarially check load-bearing claims.

### 3c. Scripts & hooks (`~/.claude/scripts/`)
- `hooks/` — Stop/PreToolUse/PostToolUse hooks (e.g. `append-retrospective.js` writes session retros to `~/.claude/logs/session-retrospectives/`).
- `ledger/` — tool-outcome ledger: mines transcripts → `tool-outcomes.jsonl`; `router.py` (Thompson sampling, currently does NOT beat random — needs reward enrichment), `append_outcome.py` (live Stop hook).
- `lib/`, `atlas-log-append.js` (the atlas-log you see at session start), `audit_sessions.py`, `claude-goal.js`.

### 3d. Other `.claude` dirs
- `commands/` — custom slash commands (`/plan`, `/show`, `/status`, `/verify`, `/tgt`, `/td`, `/learn`, `/mini-ship`, `/jargonize`, …).
- `plans/` — saved plan docs (named like `splendid-tumbling-sundae.md`).
- `projects/C--Users-bruke-Pre-Atlas/memory/` — **the persistent memory** (MEMORY.md + ~120 `project_*` / `feedback_*` / `reference_*` topic files). This is the richest record of what was built and why.
- `rules/` — global rules (`common/` + `wasp/`): assemble-first, code-as-furniture, context-cadence, file-search, security, testing, etc. These are loaded into every session.
- `logs/`, `metrics/`, `telemetry/`, `workflows/`, `scheduled-tasks/`, `sessions/` — operational data.

### 3e. Global MCP servers
- **everything** (`~/mcp-servers/everything`) — voidtools file search (the `es` engine, also via MCP).
- **competitor-monitor** (`~/mcp-servers/competitor-monitor`) — fresh-web competitive intel.
- **atlas-map** (in-process, in `~/.claude.json`) — `atlas_where/locate/neighbors/path/search/describe/call/status` over the Pre Atlas map (:3072).
- **search-stack** — the 28-provider search router (Pre Atlas :3070).
- Plus connected: musescore, blender, codex, computer-use, scheduled-tasks, n8n-mcp.

### 3f. `~/bin` and `~/tools`
- `~/bin/fest.exe` (festival CLI), `~/bin/atl.cmd` (atlas CLI shim).
- `~/tools/` — RE/unpacking kit: `AspackDie`, `unipacker`, `WiseUnpacker`, `orcastor-unpack`, `flsdk`, `python32` (32-bit Python for FL work), `ST3GG` (steg toolkit, patched — don't blindly `git pull`).

---

## 4. WHAT'S ACTUALLY RUNNING (scheduled / background)
- **Task Scheduler `PreAtlas-DropList-Daemon`** — droplist daemon, installed + verified. (`autopilot:false` protects hand-made plans.)
- **Atlas autostart** — `Pre Atlas\scripts\start_atlas.ps1` + a 15-min self-heal TimeTrigger re-spawns delta-kernel if it dies.
- **`bridge-poll`** (`*/30`) — claude-bridge poller over `G:\My Drive\claude\for-cc\`.
- **mini-ship Stop hook** + **retrospective Stop hook** + **tool-outcome Stop hook** fire at session end.

---

## 5. CROSS-CUTTING CONVENTIONS & GOTCHAS (hard-won)
- **`es` first.** For "where is X / is Y running / what version of Z," use `es.exe` (§9) before grep/Glob/which/tasklist.
- **Paths with spaces.** `Pre Atlas` (space) ≠ `pre-atlas` (hyphen) — they are *different repos*. Quote paths in PowerShell/Bash.
- **Two-repo split is load-bearing.** delta-scp lives in the hyphen repo on purpose.
- **Verify before asserting.** Don't trust agent findings or stale docs; re-grep at HEAD before acting. Plans rot — re-verify against current code.
- **Assemble, don't generate.** For solved categories (graph layout, drag-drop, FSM, parsing, dates, fuzzy-search, validation, queues), name the library before hand-rolling. See `~/.claude/rules/common/assemble-first.md`.
- **Code = furniture.** Found a bug? Fix it inline this session, or defer with a date+owner. No "documented and left rotting."
- **No em-dashes / no colored left-rail accents in UI** (Bruke's banned "AI tells").
- **PowerShell `$_` mangles** when passed inline via Bash — write a `.ps1` file first.
- **Synthetic `gh api`** — star counts/dates from `gh api` in this env are FABRICATED. Verify repo facts on real github.com.

---

## 6. HOW TO FIND ANYTHING — `es` (Everything CLI) cheat sheet
`es.exe` is at `C:\Program Files\Everything\es.exe` (on PATH). Instant NTFS-wide search.

```bash
es <name> -p                      # find any file/folder whose path contains <name>
es <name> -p -n 30                # limit to 30 results
es launch.json !node_modules -p   # every Claude run-config on the machine
es ext:md path:"C:\Users\bruke\Pre Atlas" -n 100   # all docs in a folder
es README.md !node_modules -p -n 200               # every project README
es <name> -p -get-result-count    # just the count
```
> The `-p` flag (match full path) is REQUIRED whenever you use `!exclude` or `path:`.

---

## 7. INDEX — every Claude-touched home-dir folder (one-liner each)
> Sorted roughly by recency. Caches/system folders omitted. "?" = open its README to confirm.

**Pre Atlas core:** `Pre Atlas` (the monorepo) · `pre-atlas` (hyphen — delta-scp) · `atlas` (substrate/state repo).

**Standalone, documented:** `anatomy-saas` · `binre` · `web-audit` · `Scrapling`(+`scrapling-smoke`) · `competitor-monitor`(+`intel`) · `fest-win`(+`festival-project`,`bin/fest.exe`) · `m3p-to-fract` · `mb3d-blender` · `mb3d_anim_demo` · `nih-plug` · `fl356-sandbox` · `surge-xt` · `airwindows` · `mandelbulber2_install` · `fractal-machine` · `ollama-lockdown` · `operator-system` · `screenshot-to-code` · `musescore-mcp`(+bridge) · `mcp-servers`.

**Learning rigs (reference, not products):** `three-js` · `three-stack` · `three-hero` · `three-hero-v2` · `r3f` · `anime-js` · `remotion-test` · `element-map`.

**Lower-info (read README first):** `STRUDEL`? · `POLARIS`? · `STEMai`? · `META ATLAS`? · `Creator Ecosystem OS`? · `task-manager`? · `everything-claude-code`? · `ngendo-re`? · `ngendo-audit`? · `disk-cleanup-scan` (scan output) · `research`? · `Library`?

**Config/tooling dirs:** `.claude` (toolkit — §3) · `bin` · `tools` · `.codex` · `.semgrep` · `.obey` · `.gemini` · `.supabase`.

**Old / likely pre-Claude (verify before assuming Claude built them):** `URBANNOMAD` · `FRagOS` · `StreamCore` · `LANDi` · `Symbolic Language Core Vault` · `BONES` · `D099` · `privateGPT` · `gpt4all` · `task-manager` · `my-*` scaffolds · misc 2024 folders.

---

## 8. IF YOU'RE PICKING THIS UP COLD — do this first
1. Open `Pre Atlas\atlas-manifest.yaml` — read the whole thing (it's small). Now you understand the main system.
2. Open `.claude\projects\C--Users-bruke-Pre-Atlas\memory\MEMORY.md` — read the index. Now you know status of everything.
3. To run the main system: `Pre Atlas\scripts\start_atlas.ps1`, then open `http://localhost:8888/atlas-setup.html`.
4. To find any file: `es <name> -p`.
5. To understand any single folder: open its `README.md` / `CLAUDE.md` / `.claude/launch.json`.

*Built 2026-06-25 by Claude Code (Opus 4.8). Boot truth from `.claude/launch.json`; status from project memory; structure from `atlas-manifest.yaml`. Where a start command was inferred rather than verified, the card says "see README."*
