# SPEC · Atlas Goals API

**Goal:** `g-moagzwwb-atlas-integration-option-c` (shipped 2026-04-22)
**Status:** live in `services/delta-kernel/src/api/server.ts`

## 1 · Purpose

Move `/goal` state from `~/.claude/claude-goals.jsonl` into delta-kernel (`:3001`) as a first-class entity. Atlas becomes the single source of truth for goals, their criteria, and their closure audit trail.

## 2 · Entity

```
goal {
  goal_id       string    g-<base36 ts>-<slug>
  title         string
  deadline      epoch ms
  projects      string[]
  done_criteria [{ id, text, done, done_at }]
  status        active | done | partial | missed | abandoned
  closed_at     epoch ms | null
}
```

Stored via `storage.saveEntity('goal', ...)` + append to delta log.
`EntityType` includes `'goal'`; `SYNC_PRIORITY_MAP.goal = 8` (same class as task/project).

Type definitions: [types-core.ts](../src/core/types-core.ts) (`GoalData`, `GoalCriterion`, `GoalStatus`).

## 3 · API (Bearer auth, CORS-scoped)

| Method | Path | Body | Effect |
|---|---|---|---|
| GET  | `/api/goals?active=1` | — | list (optionally active only), sorted by deadline |
| GET  | `/api/goals/:id` | — | fetch one (id prefix match allowed) |
| POST | `/api/goals` | `{ title, deadline, projects?, criteria? }` | create; emits `delta_created` + unified state |
| POST | `/api/goals/:id/criteria/:cid/done` | — | mark criterion done; records `done_at` |
| POST | `/api/goals/:id/criteria/:cid/undo` | — | reopen criterion |
| POST | `/api/goals/:id/close` | `{ status? }` | close goal; auto-derives status if omitted |

Auto-derived close status: `done` if all criteria done, else `partial` if any done, else `missed`.

### Side effect on criterion done

CLI (`claude-goal.js`) additionally posts:

```
POST /api/law/close_loop
{
  loop_id: "<goal_id>:<cid>",
  title:   "<goal.title> :: <criterion.text>",
  outcome: "closed",
  status:  "DONE"
}
```

`loop_id` is deterministic and uniqueness-guarded by `/api/law/close_loop` itself (409 on duplicate).

## 4 · Client Layer

**File:** [`~/.claude/scripts/lib/atlas-client.js`](file:///C:/Users/bruke/.claude/scripts/lib/atlas-client.js)

Thin HTTP wrapper — zero deps, Node `http` only. Namespaces: `goals`, `law`, `state`, `tasks`.

Config:

- `ATLAS_URL` — default `http://127.0.0.1:3001` (v4 loopback to avoid Windows v6-first resolution)
- `ATLAS_API_KEY` — or walks up cwd for `.aegis-tenant-key`, or reads `~/.claude/atlas-tenant-key`
- `ATLAS_TIMEOUT_MS` — default 3000

Network errors throw; callers wrap with `safe(fn)` to degrade to `{ __network_error: true, ok: false }`.

## 5 · CLI

**File:** [`~/.claude/scripts/claude-goal.js`](file:///C:/Users/bruke/.claude/scripts/claude-goal.js)

```
new        --title --deadline [--projects] [--criteria]
list       [--active | --all]
show       <goal-id>
done       <goal-id> <criterion-id>
undo       <goal-id> <criterion-id>
close      <goal-id> [--status done|partial|missed|abandoned]
active                          # JSON for the SessionStart loader
migrate    [--file <path>]      # one-shot JSONL → Atlas import
```

Deadline accepts: `YYYY-MM-DD`, `today`, `tomorrow`, `monday`..`sunday`.
Criteria syntax for `new`: `"x|y|z"`.

**Offline policy:** hard-fail with exit code 3 and a hint to start the kernel. No local fallback.

## 6 · Hooks & Commands

### SessionStart loader — [`atlas-log-loader.js`](file:///C:/Users/bruke/.claude/scripts/hooks/atlas-log-loader.js)

Prepends a banner line pulled from `/api/state/unified`:

```
Atlas mode: CLOSURE · open_loops=1 · risk=HIGH
```

Mode source: `body.derived.mode` (computed by the governance daemon, not stored under `system_state`). Falls back to `"Atlas: offline at <url>"` if the kernel is unreachable — hook never blocks session start.

### `/status` — [`commands/status.md`](file:///C:/Users/bruke/.claude/commands/status.md)

Three sections: Atlas state, active goals (from Atlas), local milestone feed.

## 7 · Data flow

```
/goal done <id> <cid>
       │
       ▼
  claude-goal.js
       │
       ├──► POST /api/goals/:id/criteria/:cid/done
       │        └─► createDelta · saveEntity · SSE `delta_created` · unified state
       │
       └──► POST /api/law/close_loop
                └─► closures.json (stats, streak, idempotency guard)
```

## 8 · Deprecations

- `~/.claude/claude-goals.jsonl` — deleted. No writers remain.
- `~/.claude/claude-goals.jsonl.migrated` — deleted after one-shot migration.
- The legacy path string appears **only** in `claude-goal.js` inside the dormant `migrate` subcommand. Safe to remove once all environments have migrated.

## 9 · Files

Kernel:

- `services/delta-kernel/src/core/types-core.ts` — `GoalData`, `GoalCriterion`, `GoalStatus`; `'goal'` in `EntityType`; `'atlas-goal-cli'` in `Author`
- `services/delta-kernel/src/core/types-extended.ts` — `goal: GoalData` in `EntityDataMap`
- `services/delta-kernel/src/core/types-sync.ts` — `goal: 8` in `SYNC_PRIORITY_MAP`
- `services/delta-kernel/src/api/server.ts` — 6 routes (~170 LOC), section marker `=== GOALS ===`

Global scripts (`~/.claude/`):

- `scripts/lib/atlas-client.js` (new)
- `scripts/claude-goal.js` (rewritten)
- `scripts/hooks/atlas-log-loader.js` (banner added)
- `commands/status.md` (Atlas section)

## 10 · Risks & known limits

- **Hook key discovery across projects.** A hook fired from a non-Pre-Atlas cwd will not find `.aegis-tenant-key`. Fix: copy the key to `~/.claude/atlas-tenant-key` (already supported).
- **Migrate is not idempotent.** Guarded by renaming the source file to `.migrated` on success; second run exits with `no legacy file`.
- **Loop-id collisions.** Impossible by construction — migration mints a new `goal_id`, so all loop ids are new.
- **CRITICAL priority.** `POST /api/tasks` rejects `CRITICAL` priority (unchanged kernel constraint); goal criteria do not use this field.

## 11 · Verification (smoke)

Assumes `cd services/delta-kernel && npm run api` is running.

```bash
# reachable
node -e "require('~/.claude/scripts/lib/atlas-client.js').isAlive().then(console.log)"

# round-trip
node ~/.claude/scripts/claude-goal.js new --title "smoke" --deadline today --criteria "ping|pong"
node ~/.claude/scripts/claude-goal.js done <id> c1
node ~/.claude/scripts/claude-goal.js close <id> --status abandoned
node ~/.claude/scripts/claude-goal.js active

# loader
echo '{}' | node ~/.claude/scripts/hooks/atlas-log-loader.js
```

Expect `Atlas mode: ...` banner + criterion close appearing inside `/api/state/unified` as `"loop_id":"<goal>:c1"`.
