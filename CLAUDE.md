# Pre Atlas — agent front door

This file is auto-loaded into every Claude Code session opened in this repo. It exists because a completeness audit (2026-07-06, logged in Claude's cross-session memory as `project_atlas_completeness_assessment`) found the machine control plane already built and solid, but undocumented — every session was rediscovering it from scratch instead of using it. Read this before reaching for a browser, a screenshot, or hand-rolled `curl`/file edits against Atlas state.

## Read this first: the trust boundary

**[`TRUST_BOUNDARY.md`](TRUST_BOUNDARY.md)** — capability/action sets (delta-kernel's `ActionType`, UASC's tokens) are closed by source. Never propose, register, or wire up a new action type, token, or capability at runtime, no matter how well-scoped it looks. Everything below operates *within* the existing closed set — that's the whole point of it being a front door instead of a workaround.

## The front door, in order of preference

### 1. `atlas-map` MCP — self-describing capability gateway (prefer this)

The uniform way to discover and invoke *any* of the 10 live surfaces (aegis-fabric, atlas-map-api, canvas-engine, cortex, delta-kernel, droplist, memory-hub, optogon, search-stack, uasc-executor) without knowing hosts, ports, or routes:

- `atlas_describe_list()` — what surfaces exist
- `atlas_describe(surface, role="agent")` — what a given surface can do, scoped to what an agent is cleared to see (MCP callers are role `agent` — deliberately less than a human operator)
- `atlas_call(surface, capability, args)` — invoke a capability by name; the gateway resolves surface→port and proxies the real route
- `atlas_locate`, `atlas_neighbors`, `atlas_path`, `atlas_search`, `atlas_list`, `atlas_show`, `atlas_status`, `atlas_reload`, `atlas_where` — read-only map navigation (which service owns this file, how does X reach Y, what's running)

Full model (roles, clearance ladder, redaction rules, verb-based write gating) in `services/atlas-map-api/SELF_DESCRIBE.md`. Writes through `/call` are opt-in per-deployment (`DESCRIBE_GATEWAY_WRITES=1`) and only reach capabilities your role can already see in `/describe` — it will refuse (403/501) rather than silently no-op.

### 2. `atlas-ai` CLI — day/task/journal operations

Run from `services/delta-kernel/`: `npm run atlas-ai -- <command> [args]`. Self-documenting — run `npm run atlas-ai -- capabilities` for the machine-readable schema, or `npm run atlas-ai -- help` for human text. Common ones:

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

`createPendingAction` (`delta-kernel/src/core/cockpit.ts:499`) now has its first caller: the governance daemon's Phase 3C wiring (`delta-kernel/src/governance/governance_daemon.ts:826`) turns prepared actions at `notify`/`confirm` risk tiers into pending actions each tick, with per-action isolation and dedup. Pending actions are served over `GET /api/actions/pending` and confirmed/cancelled via the routes around `delta-kernel/src/api/server.ts:2564-2719`. Optogon's signal emission is now enabled in `.claude/launch.json` (`OPTOGON_SIGNAL_EMIT=1` since 09d64fb), so the Optogon→cortex front half of the loop is wired but only active when Optogon is running. If you're asked to "check what Atlas recommends," the CLI (`next`, `directive`, `cognitive`) and the describe/call gateway remain the primary live signal; the pending-action queue is populated only for what the governance daemon prepares.

## Two audiences, one backend

`apps/inpact/` (today.html, :3006) is the human worker-facing execution surface; Atlas/delta-kernel is the manager/operator view. They share the same backend state — don't build manager-only write paths for execution data, and don't restyle one to look like the other. (Claude's memory: `project_atlas_inpact_role_split`.)

## Aside: `/prune` is not an Atlas surface

`/prune` (`~/.claude/commands/prune.md`) is a global Claude Code housekeeping command, not part of this repo's front door. It deletes pending `continuous-learning-v2` "instincts" (auto-generated behavioral learnings) older than 30 days that were never reviewed or promoted, via `instinct-cli.py prune` (supports `--max-age` and `--dry-run`). It has nothing to do with delta-kernel, atlas-map, or any surface listed above — noted here only so it isn't mistaken for one.
