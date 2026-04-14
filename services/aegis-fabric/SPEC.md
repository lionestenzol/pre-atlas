# Aegis Enterprise Fabric — Project Specification

**Version:** 1.0.0 (Complete)
**Status:** Finished
**Port:** 3002

---

## The Problem

AI agents act autonomously. They call tools, create tasks, modify state, and make decisions — often without guardrails. When you give Claude or GPT access to your systems, nothing sits between the model's intent and execution. There is no policy layer, no audit trail, no approval gate, and no tenant isolation. Every agent has the same permissions. Every action goes through unchecked.

This is fine for a single user running a single agent on a side project. It is not fine when agents operate across teams, across projects, or at any real scale. The moment you have two agents, two users, or two contexts, you need governance.

---

## What Aegis Does

Aegis Enterprise Fabric is a policy-gated execution layer for AI agents. It sits between the agent and the action. Every request passes through the same pipeline:

```
Agent sends action → Normalize format → Evaluate policy → Execute or block → Log everything
```

Three outcomes are possible for every action:

- **ALLOW** — action executes, a hash-chained delta is created, audit is logged
- **DENY** — action is blocked, the agent receives the reason why
- **REQUIRE_HUMAN** — action is held in an approval queue until a human decides

There is no fourth option. Every action that enters Aegis exits through one of these three doors.

---

## Why You Need It

**Without Aegis**, an AI agent can:
- Delete production data with no record of who asked or why
- Execute expensive operations with no budget enforcement
- Bypass team-specific restrictions because there are no restrictions
- Act identically in recovery mode and build mode despite different risk profiles
- Run indefinitely with no usage tracking or rate limits

**With Aegis**, every agent action is:
- Authenticated to a specific tenant
- Evaluated against declarative policy rules
- Rate-limited per tenant tier
- Logged in an append-only audit trail
- Tracked for cost and usage per agent per day
- Optionally held for human approval before execution

Aegis does not replace your agents. It governs them.

---

## How It Works

### The Action Pipeline

An agent submits a request to `POST /api/v1/agent/action`. The request body can be in any of three formats — Claude's `tool_use`, OpenAI's `function` call, or a direct format. Aegis normalizes all three into a single canonical structure before anything else happens.

The normalized action then hits the policy engine. Rules are declarative JSON — no code, no AI judgment. Each rule has conditions (field + operator + value), a priority (lower number wins), and an effect (ALLOW/DENY/REQUIRE_HUMAN). Rules are evaluated in priority order. First match wins. If nothing matches, the default is ALLOW.

If the policy says ALLOW, the action executes. A new entity or delta is created, the event bus fires, webhooks dispatch, usage is tracked, and the audit log gets a new entry.

If the policy says DENY, execution stops. The agent receives a 403 with the rule name and reason.

If the policy says REQUIRE_HUMAN, the action is frozen in an approval queue. A human reviews it through the dashboard or API. They approve or reject. Approved actions re-enter the pipeline and execute. Rejected actions are logged and discarded. Unreviewed actions expire after one hour.

### Policy Rules

Rules are JSON objects. A rule that blocks all delete operations in RECOVER mode looks like this:

```json
{
  "name": "no-deletes-in-recovery",
  "priority": 10,
  "conditions": [
    { "field": "action", "operator": "eq", "value": "delete_task" },
    { "field": "tenant.mode", "operator": "eq", "value": "RECOVER" }
  ],
  "effect": "DENY",
  "reason": "Deletions are blocked during recovery mode"
}
```

A rule that requires human approval for any OpenAI agent action:

```json
{
  "name": "human-review-openai",
  "priority": 20,
  "conditions": [
    { "field": "agent.provider", "operator": "eq", "value": "openai" }
  ],
  "effect": "REQUIRE_HUMAN",
  "reason": "All OpenAI agent actions require human review"
}
```

Nine operators are available: `eq`, `neq`, `in`, `not_in`, `gt`, `lt`, `gte`, `lte`, `exists`. Conditions can target tenant tier, tenant mode, agent provider, agent capabilities, action name, and any parameter.

### Multi-Tenancy

Every API call is scoped to a tenant via the `X-API-Key` header. Tenants have tiers with enforced quotas:

| | FREE | STARTER | ENTERPRISE |
|---|---|---|---|
| Max Agents | 2 | 10 | 100 |
| Actions/Hour | 100 | 1,000 | 10,000 |
| Max Entities | 500 | 5,000 | 100,000 |
| Max Webhooks | 2 | 10 | 100 |

Storage is physically isolated — each tenant's entities and deltas live in their own directory. There is no cross-tenant data access.

### Delta Chain

Every state change is an RFC 6902 JSON Patch stored as a delta. Each delta includes a SHA-256 hash of the resulting state and a reference to the previous hash. This creates a tamper-evident chain — if any delta is modified after the fact, the hash chain breaks and verification fails.

State is never overwritten. It is always reconstructed by folding deltas in order. This means you get full version history, point-in-time snapshots, and auditability for free.

### The 10 Actions

Agents can request exactly these operations:

| Action | What It Does |
|---|---|
| `create_task` | Create a new task entity |
| `update_task` | Modify task fields via delta |
| `complete_task` | Mark task status as DONE |
| `delete_task` | Archive a task (soft delete) |
| `query_state` | Read an entity or list entities by type |
| `propose_delta` | Submit an arbitrary state change |
| `route_decision` | Request routing guidance for current mode |
| `request_approval` | Explicitly request human review |
| `get_policy_simulation` | Dry-run: test what policy would decide |
| `register_webhook` | Subscribe to system events |

### Agent Format Support

Three agent formats are supported natively:

**Claude:**
```json
{ "agent_id": "...", "type": "tool_use", "name": "create_task", "input": { "title": "..." } }
```

**OpenAI:**
```json
{ "agent_id": "...", "function": { "name": "create_task", "arguments": "{\"title\":\"...\"}" } }
```

**Direct:**
```json
{ "agent_id": "...", "action": "create_task", "params": { "title": "..." } }
```

All three normalize to the same canonical form before policy evaluation. The agent does not need to know which format Aegis expects — it auto-detects.

---

## What Ships

### API (Port 3002)

22 endpoints covering tenants, agents, actions, policies, approvals, state, webhooks, audit, usage, metrics, and health. Full CRUD where applicable. Auth via `X-API-Key` header. Admin key for tenant management, tenant key for everything else.

### Dashboard

A single-page web UI at `/ui/dashboard.html` with 8 tabs: Overview, Agents, Policies, Approvals, State, Metrics, Calendar, Delta Log. Connects with admin + tenant keys. Real-time health indicator. Auto-refreshes every 5 seconds.

### Policy Engine

Declarative JSON rules with caching (60-second TTL). Simulation endpoint for dry-run testing. No code execution — rules are data, not logic.

### Approval Queue

Human-in-the-loop workflow. Actions requiring approval are held with a 1-hour TTL. Approve or reject via dashboard or API. Approved actions re-execute automatically.

### Audit Trail

Append-only JSONL log per tenant. Every action, every policy decision, every approval — recorded with timestamps, agent IDs, entity IDs, and delta references.

### Event System

In-process event bus with 8 event types. Webhook dispatcher with HMAC signing and retry logic. Subscribe to any combination of events per tenant.

### Observability

Structured logging. Prometheus-compatible metrics at `/metrics`. Health check at `/health`. Per-agent usage tracking with cost aggregation.

### Test Suite

31 tests across 6 modules: delta operations, policy engine, agent adapter, approval queue, snapshots, and end-to-end integration. All passing.

### Monorepo Packages

Three additional packages for scaling beyond the prototype:
- `@aegis/shared` — shared types, hashing, patching
- `@aegis/kernel` — Fastify + PostgreSQL backend
- `@aegis/gateway` — Fastify + Redis gateway with rate limiting and idempotency

---

## Running It

```bash
npm install
npm run test          # 31/31 tests
npm run api           # Start on port 3002
npm run build         # TypeScript compilation
npm run build:all     # Build all monorepo packages
```

Open `http://localhost:3002/ui/dashboard.html` to access the dashboard.

Environment variables:
- `AEGIS_PORT` — server port (default: 3002)
- `AEGIS_DATA_DIR` — storage directory (default: .aegis-data)
- `AEGIS_ADMIN_KEY` — admin API key (default: aegis-admin-default-key)

---

## Architecture

```
services/aegis-fabric/
├── src/
│   ├── core/            Types, delta engine, entity registry
│   ├── storage/         File-based persistence, snapshots
│   ├── tenants/         Tenant registry, isolation enforcement
│   ├── agents/          Agent registry, format adapter, action processor
│   ├── policies/        Policy engine, rule store, decision cache
│   ├── approval/        Approval queue and lifecycle
│   ├── events/          Event bus, webhook dispatcher, audit log
│   ├── gateway/         Auth middleware, rate limiter, request logger
│   ├── observability/   Logger, metrics, health check
│   ├── cost/            Usage tracker
│   ├── api/             Express server + 8 route modules
│   ├── ui/              Dashboard
│   └── tests/           6 test modules
├── specs/               6 locked specification documents
├── contracts/schemas/   7 JSON Schema (draft-07) contracts
└── packages/            Monorepo scaling packages (shared, kernel, gateway)
```

42 TypeScript source files. ~4,600 lines of code. Zero external runtime dependencies beyond Express and CORS.

---

## Design Principles

1. **No overwrites.** Every change is a hash-chained delta. State is reconstructed, never mutated in place.
2. **Policy is data.** Rules are declarative JSON, not code. No AI in the governance loop.
3. **Tenant isolation is mandatory.** Storage, auth, rate limits, and audit are all per-tenant.
4. **Three doors only.** Every action exits as ALLOW, DENY, or REQUIRE_HUMAN. No ambiguity.
5. **Audit everything.** Every decision is logged. The append-only trail cannot be edited.
6. **Format agnostic.** Claude, OpenAI, or custom — the agent format does not matter. Aegis normalizes before evaluating.
