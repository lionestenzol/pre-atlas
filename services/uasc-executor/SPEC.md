# UASC Executor — Protocol Specification

**Version:** 1.0
**Status:** Active
**Port:** 3008
**Role:** Command execution engine for Pre Atlas

---

## What This Is

UASC Executor is a command protocol — not a language, not an AI agent. It receives short tokens (`@WORK`, `@CLOSE_LOOP`), looks up a deterministic execution profile, and runs it step by step. It is the "hands" of the system.

It does not decide what to do. Delta-kernel (port 3001) decides. This service just does it.

## Architecture

```
Delta-Kernel (governance)         UASC Executor (execution)
┌─────────────────────┐          ┌─────────────────────┐
│ Mode Routing         │          │ Command Registry     │
│ Signal Bucketing     │          │ Profile Loader       │
│ PendingAction Gate   │──POST──▶│ Step Executor        │
│ Executor Bridge      │  /exec  │ Audit Logger         │
└─────────────────────┘          └─────────────────────┘
       :3001                            :3008
```

**Flow:**
1. Delta-kernel confirms a PendingAction
2. Executor bridge maps ActionType → command token
3. Bridge signs request (HMAC-SHA256) and POSTs to `/exec`
4. Executor loads profile JSON, runs steps sequentially
5. Result returns to bridge, logged to timeline

---

## Command Registry

7 commands, stored in SQLite `commands` table:

| Token | Profile | Purpose |
|-------|---------|---------|
| `@WORK` | WORK_v1 | Open editor, browser, set focus mode |
| `@BUILD` | BUILD_v1 | Detect package manager, install deps, build, test |
| `@DEPLOY` | DEPLOY_v1 | Pre-flight check, push artifacts, verify health |
| `@CLEAN` | CLEAN_v1 | Clear temp files, report disk space |
| `@WRAP` | WRAP_v1 | Git add/commit/push, end-of-day sync |
| `@CLOSE_LOOP` | CLOSE_LOOP_v1 | Mark task done via delta-kernel API |
| `@SEND_DRAFT` | SEND_DRAFT_v1 | Render template message, log send |

Commands are added by inserting rows into the `commands` table and placing a profile JSON in `profiles/`.

---

## API Endpoints

### `POST /exec`

Execute a command.

**Headers (required):**
```
X-UASC-Client: delta-kernel
X-UASC-Timestamp: 1712434500
X-UASC-Signature: <hmac-sha256-hex>
```

**Body:**
```json
{
  "cmd": "@CLOSE_LOOP",
  "task_id": "abc-123",
  "task_title": "Fix login bug"
}
```

All fields except `cmd` are passed as inputs to the profile.

**Response (200):**
```json
{
  "run_id": "uuid",
  "cmd": "@CLOSE_LOOP",
  "status": "success",
  "duration_ms": 142,
  "steps": [
    { "name": "mark_task_done", "status": "success", "duration_ms": 130 },
    { "name": "log_closure", "status": "success", "duration_ms": 0 }
  ],
  "outputs": {},
  "error": null
}
```

**Response (500 on step failure):**
```json
{
  "run_id": "uuid",
  "cmd": "@CLOSE_LOOP",
  "status": "failed",
  "error": "Step 'mark_task_done' failed: connection refused"
}
```

### `GET /commands`

List all registered commands.

### `GET /runs`

Recent execution history (last 20 runs).

### `GET /health`

Health check.

---

## Authentication

HMAC-SHA256 signature over `{timestamp}{body}`.

```
signature = HMAC-SHA256(secret, timestamp + body)
```

**Clients** are registered in the `clients` table:

| Client ID | Role | Purpose |
|-----------|------|---------|
| `delta-kernel` | admin | Bridge from governance engine |
| `cli-local` | admin | Manual testing via CLI |

**Replay protection:** Requests older than 5 minutes are rejected.

---

## Profile Format

Profiles are JSON files in `profiles/`. Structure:

```json
{
  "id": "PROFILE_NAME",
  "version": 1,
  "description": "What this profile does",
  "inputs": [
    {
      "name": "variable_name",
      "type": "string",
      "default": "fallback_value"
    }
  ],
  "steps": [],
  "on_success": { "type": "log", "message": "Done" },
  "on_failure": { "type": "log", "message": "Failed", "level": "error" }
}
```

### Step Types

**Shell** — Run a command:
```json
{
  "name": "step_name",
  "type": "shell",
  "cmd": "git status --porcelain",
  "timeout_seconds": 60,
  "continue_on_error": false,
  "platform": "windows",
  "condition": "variable == 'value'",
  "store_as": "output_var",
  "fail_if": "output_var != ''"
}
```

**HTTP** — Make a request:
```json
{
  "name": "step_name",
  "type": "http",
  "method": "PUT",
  "url": "http://localhost:3001/api/tasks/{task_id}",
  "body": { "status": "DONE" },
  "expected_status": 200,
  "retries": 2,
  "timeout_seconds": 30
}
```

**Log** — Print a message:
```json
{
  "name": "step_name",
  "type": "log",
  "message": "Completed: {task_title} at {timestamp}",
  "level": "info"
}
```

### Step Features

| Feature | Description |
|---------|-------------|
| `{variable}` | Interpolated from inputs or stored outputs |
| `condition` | Step runs only if condition is true |
| `store_as` | Capture step output into a variable |
| `fail_if` | Force failure if condition is met |
| `continue_on_error` | Don't abort profile on step failure |
| `platform` | Only run on `windows` or `unix` |
| `timeout_seconds` | Kill step after timeout |
| `retries` | Retry HTTP steps N times |

### Condition Syntax

Simple expressions only:
```
variable == 'value'
variable != 'value'
variable == ''
variable != ''
true
false
```

No complex expressions. No nesting. If you need real logic, put it in delta-kernel's routing — not here.

---

## Action-to-Token Bridge

Delta-kernel's executor bridge (`src/core/executor-bridge.ts`) maps action types to tokens:

| ActionType | Token | What Happens |
|------------|-------|--------------|
| `reply_message` | `@SEND_DRAFT` | Render template, log send |
| `complete_task` | `@CLOSE_LOOP` | PUT task status to DONE via API |
| `send_draft` | `@SEND_DRAFT` | Render template, log send |
| `apply_automation` | `@WORK` | Open tools, enter work state |
| `create_asset` | `@BUILD` | Detect deps, build, test |
| `delegate` | `@DEPLOY` | Format and log delegation |
| `rest_action` | *(none)* | No execution, log only |

---

## Delta-Kernel Integration

### Endpoints on delta-kernel (port 3001):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/actions/pending` | List pending actions |
| `POST` | `/api/actions/pending` | Create a pending action |
| `POST` | `/api/actions/confirm/:id` | Confirm → fires executor bridge |
| `POST` | `/api/actions/cancel/:id` | Cancel a pending action |
| `GET` | `/api/executor/health` | Check if executor is reachable |

### Confirm Flow

```
POST /api/actions/pending
  body: { action_type: "complete_task", target_entity_id: "task-uuid" }
  → returns: { id: "pending-uuid", status: "PENDING", expires_at: ... }

POST /api/actions/confirm/pending-uuid
  → bridge maps complete_task → @CLOSE_LOOP
  → POST localhost:3008/exec { cmd: "@CLOSE_LOOP", task_id: "task-uuid" }
  → returns: { status: "CONFIRMED", execution: { status: "success", run_id: "..." } }
```

PendingActions expire after 30 seconds if not confirmed.

---

## Storage

SQLite database at `storage/registry.db`. WAL mode.

**Tables:**

| Table | Purpose |
|-------|---------|
| `commands` | Token → profile mapping |
| `clients` | Authorized callers + secrets |
| `runs` | Execution audit log |
| `run_events` | Step-by-step execution trace |

All executions are logged. Nothing runs without an audit trail.

---

## Adding a New Command

1. Create `profiles/NEW_COMMAND_v1.json` with steps
2. Add to `storage/schema.sql`:
   ```sql
   INSERT OR IGNORE INTO commands (cmd, profile_id, version) VALUES ('@NEW_COMMAND', 'NEW_COMMAND_v1', 1);
   ```
3. Delete `storage/registry.db` and restart (or use SQLite to insert directly)
4. Add mapping in `executor-bridge.ts` if triggered from delta-kernel

---

## What This Is NOT

- **Not a language.** No parser, no grammar, no composition. Tokens are flat lookups.
- **Not an AI agent.** No LLM in the loop. All profiles are deterministic.
- **Not a task queue.** Commands execute synchronously. No scheduling, no retry queues.
- **Not a replacement for delta-kernel.** This service has no concept of modes, signals, or governance. It just runs what it's told.

---

## Origin

UASC-M2M (Ultra-Compressed High-Context Symbolic Encoding for Machine-to-Machine Communication) started as a research project exploring symbolic AI command languages. The original vision included stroke-based glyph encoding, neural network interpreters, and cross-domain symbolic composition.

The practical output was this: a clean command protocol that does one thing well — map a token to a profile and execute it. The research lives at `research/uasc-m2m/`. The working system lives here.

---

## File Map

```
services/uasc-executor/
├── server.py                 # HTTP server, registry, request handling
├── executor.py               # Profile execution engine
├── auth.py                   # HMAC-SHA256 authentication
├── start.bat                 # Launch script
├── SPEC.md                   # This file
├── storage/
│   ├── schema.sql            # Database schema + seed data
│   └── registry.db           # SQLite database (generated)
└── profiles/
    ├── WORK_v1.json           # Enter work state
    ├── BUILD_v1.json          # Build + test pipeline
    ├── DEPLOY_v1.json         # Deploy pipeline
    ├── CLEAN_v1.json          # System hygiene
    ├── WRAP_v1.json           # End-of-day wrap
    ├── CLOSE_LOOP_v1.json     # Close a task/loop
    └── SEND_DRAFT_v1.json     # Send a draft message
```
