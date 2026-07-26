# Pre Atlas — agent front door

This file is auto-loaded into every Claude Code session opened in this repo. It exists because a completeness audit (2026-07-06, logged in Claude's cross-session memory as `project_atlas_completeness_assessment`) found the machine control plane already built and solid, but undocumented — every session was rediscovering it from scratch instead of using it. Read this before reaching for a browser, a screenshot, or hand-rolled `curl`/file edits against Atlas state.

## Read this first: the trust boundary

**[`TRUST_BOUNDARY.md`](TRUST_BOUNDARY.md)** — capability/action sets (delta-kernel's `ActionType`, UASC's tokens) are closed by source. Never propose, register, or wire up a new action type, token, or capability at runtime, no matter how well-scoped it looks. Everything below operates *within* the existing closed set — that's the whole point of it being a front door instead of a workaround.

## Human doors — outside Claude Code

Atlas has two doors that do not require a Claude Code session. Both ship as packaged Windows binaries from fest [`atlas-doors-AD0001`](../festival-project/festivals/active/atlas-doors-AD0001/). Full doc: [`docs/DOORS.md`](docs/DOORS.md).

### `atlas.exe` — the CLI door

Portable Windows binary compiled from [`services/delta-kernel/src/cli/atlas-ai.ts`](services/delta-kernel/src/cli/atlas-ai.ts) via Node SEA. Installed at `C:\Users\bruke\bin\atlas.exe` and on user PATH. Runs from any terminal, any cwd, no Node required.

```
atlas help          # command schema
atlas state         # full snapshot (round-trips through delta-kernel :3001)
atlas next          # recommended action for current mode/energy
atlas task add "…"  # write path
atlas morning       # start-of-day compound
```

Exits with a one-line friendly error and code 3 if delta-kernel :3001 is offline (no stack trace). Needs `ATLAS_REPO_ROOT=C:\Users\bruke\Pre Atlas` in user env so it finds `services/cognitive-sensor/` sidecars from its installed location — already set. Rebuild: `cd services/delta-kernel && npx esbuild src/cli/atlas-ai.ts --bundle --platform=node --target=node20 --format=cjs --outfile=build/atlas.cjs && node --experimental-sea-config build/sea-config.json && node -e "require('fs').copyFileSync(process.execPath,'build/atlas.exe')" && npx postject build/atlas.exe NODE_SEA_BLOB build/sea-prep.blob --sentinel-fuse NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2`.

### `AtlasTray.exe` — the tray app door

Tauri v2 shell wrapping [`atlas-mission-control.html`](atlas-mission-control.html). Sits in the Windows system tray with an "A" icon; window title is "Atlas". Left-click the tray icon to restore the window; right-click for Open + Quit. X-button hides to tray without exiting. Autostarts at login via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Atlas` -> `C:\Users\bruke\bin\AtlasTray.exe`. Source: [`apps/atlas-tray/`](apps/atlas-tray/). Rebuild: `cd apps/atlas-tray && npx tauri build --no-bundle` (produces `src-tauri/target/release/AtlasTray.exe`). **Filename note:** the binary is `AtlasTray.exe`, not `Atlas.exe`, because Windows filesystem lookups are case-insensitive and `Atlas.exe` in the same dir as `atlas.exe` overwrites the CLI on copy. Product display name stays "Atlas".

## The front door, in order of preference (Claude Code / agents)

### 1. `atlas-map` MCP — self-describing capability gateway (prefer this)

The uniform way to discover and invoke *any* of the 10 live surfaces (aegis-fabric, atlas-map-api, canvas-engine, cortex, delta-kernel, droplist, memory-hub, optogon, search-stack, uasc-executor) without knowing hosts, ports, or routes:

- `atlas_describe_list()` — what surfaces exist
- `atlas_describe(surface, role="agent")` — what a given surface can do, scoped to what an agent is cleared to see (MCP callers are role `agent` — deliberately less than a human operator)
- `atlas_call(surface, capability, args)` — invoke a capability by name; the gateway resolves surface→port and proxies the real route
- `atlas_locate`, `atlas_neighbors`, `atlas_path`, `atlas_search`, `atlas_list`, `atlas_show`, `atlas_status`, `atlas_reload`, `atlas_where` — read-only map navigation (which service owns this file, how does X reach Y, what's running)

Full model (roles, clearance ladder, redaction rules, verb-based write gating) in `services/atlas-map-api/SELF_DESCRIBE.md`. Writes through `/call` are opt-in per-deployment (`DESCRIBE_GATEWAY_WRITES=1`) and only reach capabilities your role can already see in `/describe` — it will refuse (403/501) rather than silently no-op.

### 2. `atlas-ai` CLI — day/task/journal operations

Run from `services/delta-kernel/`: `npm run atlas-ai -- <command> [args]`. Self-documenting — run `npm run atlas-ai -- capabilities` for the machine-readable schema, or `npm run atlas-ai -- help` for human text.

*From a terminal outside CC, `atlas <command>` (via the compiled `atlas.exe`, see the Human doors section above) is the same CLI without the `npm run` wrapper and without the cwd requirement — prefer that path.* Common commands either way:

| Command | Does |
|---|---|
| `state` | Full system snapshot |
| `next` | Recommended action given current mode/energy |
| `day create A\|B\|C` | Start a day plan |
| `day block <n>` / `day done` / `day goal` / `day rate` | Day-plan operations |
| `task add <text>` / `task done <id>` | Task management |
| `win <text>` | Log a momentum win |
| `journal add <text>` | Journal entry |
| `close <id>` / `archive <id>` | Close or archive a loop |
| `cognitive` / `directive` | Drift, compliance, mode, strategic directive |
| `morning` / `wrap` | Start-of-day / end-of-day compound routines |
| `agent --once\|--daemon [--dry-run]` | Run the agent work loop |

### 3. Direct REST — only when you already know the surface

`delta-kernel` (:3001) exposes `/api/work/{request,claim,complete,cancel,heartbeat,status,history,metrics}` as the machine job queue, and `/api/auth/token` to fetch the bearer key (open route; every other `/api/*` route requires `Authorization: Bearer <token>` once `.aegis-tenant-key` exists — dev mode with no key file skips auth entirely). Prefer options 1 or 2 above; drop to raw REST only for something neither the gateway nor the CLI covers yet.

## Known gap (updated 2026-07-06) — the loop is partially live now

`createPendingAction` (`delta-kernel/src/core/cockpit.ts:499`) now has its first caller: the governance daemon's Phase 3C wiring (`delta-kernel/src/governance/governance_daemon.ts:826`) turns prepared actions at `notify`/`confirm` risk tiers into pending actions each tick, with per-action isolation and dedup. Pending actions are served over `GET /api/actions/pending` and confirmed/cancelled via the routes around `delta-kernel/src/api/server.ts:2564-2719`. Optogon's signal emission is now enabled in `.claude/launch.json` (`OPTOGON_SIGNAL_EMIT=1` since 09d64fb), so the Optogon→cortex front half of the loop is wired but only active when Optogon is running. If you're asked to "check what Atlas recommends," the CLI (`next`, `directive`, `cognitive`) and the describe/call gateway remain the primary live signal; the pending-action queue is populated only for what the governance daemon prepares. As of Wave 1.1 (atlas-consolidation AC0002), the governance daemon only starts when `GOVERNANCE_DAEMON=1` is set (server.ts gates `daemon.start()`); `scripts/start_atlas.ps1` sets it, so fleet starts are unchanged, but a bare `npx tsx src/api/server.ts` now runs daemon-off.

## Two audiences, one backend

`apps/inpact/` (today.html, :3006) is the human worker-facing execution surface; Atlas/delta-kernel is the manager/operator view. They share the same backend state — don't build manager-only write paths for execution data, and don't restyle one to look like the other. (Claude's memory: `project_atlas_inpact_role_split`.)

## Aside: `/prune` is not an Atlas surface

`/prune` (`~/.claude/commands/prune.md`) is a global Claude Code housekeeping command, not part of this repo's front door. It deletes pending `continuous-learning-v2` "instincts" (auto-generated behavioral learnings) older than 30 days that were never reviewed or promoted, via `instinct-cli.py prune` (supports `--max-age` and `--dry-run`). It has nothing to do with delta-kernel, atlas-map, or any surface listed above — noted here only so it isn't mistaken for one.
