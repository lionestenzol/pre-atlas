# Clock Mechanism — Seqs 2, 3, 4 Build Spec

> Continuation of the "clock mechanism" integration (Plan A).
> Seq 1 (ARCHITECTURE.md + DECISIONS.md) shipped as `6bb3303`.
> This spec covers Seqs 2-4. Execute in a fresh session.

## Context

ChatGPT conversation identified 7 permanent parts every project needs ("clock mechanism").
Pre Atlas had 3 gaps: no root architecture docs (FIXED), no universal task runner, no cold-start bootstrap, 4 services missing READMEs.

Source: `C:/Users/bruke/chatpull/pulls/chatgpt/2025-06-09-the-7-permanent-parts-of-every-project.md`

## Build Order

Two parallel tracks. No dependency between them.

```
Track A: Seq 2 (Justfile) → Seq 3 (Bootstrap)   [sequential — 3 depends on 2]
Track B: Seq 4 (READMEs)                         [independent]
```

Start both tracks simultaneously. Track B finishes first (~30 min). Track A is ~60 min total.

---

## Track A: Seq 2 — Justfile

### Pre-req: install `just`

```powershell
cargo install just
```

Cargo 1.96.0 is on the machine. Verify with `just --version` after install.

### What to build

Single flat `Justfile` at repo root (~150 lines). Shell config:

```just
set shell := ["powershell", "-NoProfile", "-Command"]
set windows-shell := ["powershell", "-NoProfile", "-Command"]
```

### Recipe inventory

**Core lifecycle** (wrap existing `scripts/start_atlas.ps1`, `stop_atlas.ps1`, `status_atlas.ps1`):

| Recipe | Wraps | Notes |
|---|---|---|
| `start` | `scripts/start_atlas.ps1` | Canonical launcher, boots 12 services |
| `stop` | `scripts/stop_atlas.ps1` | **FIX FIRST:** references retired ports 3000/3005/3030, misses 3071/3072 |
| `status` | `scripts/status_atlas.ps1` | **FIX FIRST:** same stale port list as stop |
| `restart` | stop + start | New recipe, no existing script |
| `kill-ports` | `scripts/kill_ports.ps1` | Emergency cleanup |

**Per-service start** (8 recipes):

| Recipe | Service | Port | Command |
|---|---|---|---|
| `start-kernel` | delta-kernel | 3001 | `npm run api` |
| `start-aegis` | aegis-fabric | 3002 | `npm run api` |
| `start-cortex` | cortex | 3009 | `python main.py` |
| `start-optogon` | optogon | 3010 | `python main.py` |
| `start-openclaw` | openclaw | 3004 | `npm run start` |
| `start-uasc` | uasc-executor | 3008 | `python -m uvicorn` |
| `start-canvas` | canvas-engine | 3050 | `npm run start` |
| `start-inpact` | inPACT | 3006 | `npx http-server apps/inpact -p 3006` |

**Testing:**

| Recipe | What |
|---|---|
| `test` | Run all test suites (kernel + aegis + cognitive-sensor) |
| `test-kernel` | `cd services/delta-kernel && npm test` |
| `test-aegis` | `cd services/aegis-fabric && npm test` |
| `test-sensor` | `cd services/cognitive-sensor && python -m pytest tests/` |

**Database:**

| Recipe | What |
|---|---|
| `db-studio` | `npx prisma studio` (if applicable) |
| `db-backup` | Copy `.delta-fabric/` to timestamped backup |

**Operations:**

| Recipe | What |
|---|---|
| `clean` | Remove node_modules, __pycache__, .pyc across all services |
| `logs service` | Tail logs for a given service |
| `install` | npm install + pip install across all active services |

### Pre-build fixes (do these BEFORE writing the Justfile)

1. **Fix `scripts/stop_atlas.ps1`** — update port list: remove 3000, 3005, 3030; add 3071, 3072, 3013 (ws-gateway).
2. **Fix `scripts/status_atlas.ps1`** — same port list fix.
3. **Delete or .gitignore `scripts/setup_n8n_workflows.ps1`** — contains hardcoded JWT at line 5, script is stale.

### Guard

`start_atlas.ps1:33` references `C:\Users\bruke\atlas` (sibling repo). The Justfile `start` recipe should NOT try to fix this — it just wraps the script. Document it as a known dependency in a comment.

### Verification

```powershell
just --list                    # all recipes visible
just start                     # boots the fleet
just status                    # shows running services with correct ports
just stop                      # kills them cleanly
just test-kernel               # proof one test recipe works
```

### Commit

```
feat: add Justfile universal task runner (clock mechanism Seq 2)
```

---

## Track A (continued): Seq 3 — Cold-Start Bootstrap

### Depends on

Seq 2 must be committed first (bootstrap uses `just` recipes internally).

### What to build

`scripts/bootstrap.ps1` — idempotent first-run setup script. Also wire a `just bootstrap` recipe that calls it.

### Bootstrap phases

```
Phase 0: Preflight checks
  - Node.js >= 18 (v22.22.0 on machine)
  - Python >= 3.11 (3.13.2 on machine)
  - just --version (installed in Seq 2)
  - Git (for submodule)
  - Optional: Docker check (warn if absent, don't fail)

Phase 1: npm install (Tier 1 — Node/TS services)
  - services/delta-kernel
  - services/aegis-fabric
  - services/canvas-engine
  - services/ws-gateway
  (delta-scp out of scope — Supabase dependency)

Phase 2: Python venvs + pip install (Tier 2 — Python services)
  Per-service venvs (matches existing project pattern):
  - services/cortex
  - services/optogon
  - services/uasc-executor
  - services/openclaw (has Python components)
  - services/atlas-map-api
  - services/memory-hub
  - services/search-stack
  OPTIONAL (skip by default, flag to include):
  - services/cognitive-sensor (2GB torch)
  - services/droplist
  - services/perception
  - services/triangulation

Phase 3: Environment setup
  - Auto-copy services/aegis-fabric/.env.example → .env (if .env missing)
  - Warn about .aegis-tenant-key (optional, dev mode skips auth)
  - Check for .env at repo root (docker-compose only, not required)

Phase 4: Submodule
  - git submodule update --init services/crucix
  - DO NOT git add services/crucix (submodule sits dirty by design)

Phase 5: Smoke test
  - Start Core 5 (delta-kernel, aegis-fabric, cortex, optogon, inPACT)
  - Health-check each: GET /health or equivalent
  - Report pass/fail table
  - Stop all after check
```

### Idempotency rules

- `npm install` is naturally idempotent
- `pip install` into existing venv is idempotent
- `.env` copy only if target missing (never overwrite)
- Submodule init is idempotent
- Smoke test is stateless

### Flags

```powershell
.\scripts\bootstrap.ps1                  # Core + Standard tiers
.\scripts\bootstrap.ps1 -Full            # Include Optional tier (cognitive-sensor, etc.)
.\scripts\bootstrap.ps1 -SkipSmoke       # Skip Phase 5 health checks
```

### Verification

```powershell
just bootstrap                  # runs scripts/bootstrap.ps1
# On a machine with deps already installed: completes in <60s, no errors
# Smoke test: 5/5 Core services respond
```

### Commit

```
feat: add cold-start bootstrap script (clock mechanism Seq 3)
```

---

## Track B: Seq 4 — Service READMEs

### What to build

4 READMEs, each 40-80 lines. Template:

```markdown
# <Service Name>

> One-line description

## What it does

2-3 paragraphs explaining purpose, role in the system, key behaviors.

## Quick Start

\`\`\`powershell
cd services/<name>
<install command>
<start command>
\`\`\`

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|

## API Reference

| Method | Route | Purpose |
|---|---|---|

## Architecture

\`\`\`
<directory tree, 2-3 levels>
\`\`\`

## Stack

- Runtime, framework, key deps

## Tests

How to run, or "No tests yet" if none exist.

## Part of Pre Atlas

Link to ARCHITECTURE.md, note role in the system.
```

### Per-service notes

**openclaw** (:3004, TS/Express, ~1,800 LOC)
- External tool orchestration layer
- Wraps third-party APIs behind unified interface
- Credential vault pattern
- Read `services/openclaw/src/` to discover endpoints and env vars

**optogon** (:3010, TS/Express, ~2,200 LOC)
- Signal-processing layer
- Collects/processes signals from other services
- MUST note: emission gated behind `OPTOGON_SIGNAL_EMIT` env var (off by default, per ADR-003)
- Read `services/optogon/src/` for signal types and API

**uasc-executor** (:3008, Python/FastAPI, ~2,300 LOC)
- HMAC-authenticated command execution
- 4 endpoints: /health, /commands, /runs, /exec
- 10 registered commands: @WORK, @WRAP, @CLEAN, @BUILD, @DEPLOY, @CLOSE_LOOP, @SEND_DRAFT, @BRIEF, @EXECUTE, @SNAPSHOT
- Shell injection hardening
- MUST reference TRUST_BOUNDARY.md
- Tests: `test_server_smoke.py` (10 functions)

**ws-gateway** (:3013, TS/Express+ws, ~800 LOC)
- WebSocket gateway for real-time event streaming
- Port was 3011, moved to 3013 (register-preview-server fix, verified)
- No tests — state "No tests yet" explicitly

### Verification

Each README: read the service source, confirm every endpoint/env-var/command listed actually exists (code-recon locate mode). Don't invent.

### Commit

```
docs: add READMEs for openclaw, optogon, uasc-executor, ws-gateway (clock mechanism Seq 4)
```

---

## Session plan (for the fresh session)

```
1. Read this spec
2. Install just (cargo install just) — 2 min
3. Fork into two parallel tracks:

   Track A                              Track B
   --------                             --------
   Fix stop_atlas.ps1 ports             Read openclaw source → README
   Fix status_atlas.ps1 ports           Read optogon source → README
   Delete/ignore n8n script             Read uasc-executor source → README
   Write Justfile                       Read ws-gateway source → README
   Verify: just --list, start/stop      Verify: endpoints match source
   Commit Seq 2                         Commit Seq 4
   Write bootstrap.ps1                  (done)
   Wire just bootstrap recipe
   Verify: just bootstrap
   Commit Seq 3

4. Final: git log --oneline to confirm 3 clean commits
```

## Done when

- `just --list` shows all recipes
- `just start` / `just stop` / `just status` work with correct ports
- `just bootstrap` runs idempotently, Core 5 pass smoke test
- 4 new READMEs exist, each verified against source
- 3 commits on `feat/atlas-setup-ui`
