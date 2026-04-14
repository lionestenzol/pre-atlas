# Aegis Enterprise Fabric

Policy-gated execution layer for AI agents. Every agent action goes through one pipeline:

```
Agent sends action → Normalize → Evaluate policy → Execute/Block/Queue → Log everything
```

Three outcomes: **ALLOW**, **DENY**, or **REQUIRE_HUMAN**. No exceptions.

## Quick Start

```bash
npm install
npm start
```

Server starts on `http://localhost:3002`. Configure with env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGIS_PORT` | `3002` | API port |
| `AEGIS_DATA_DIR` | `.aegis-data/` | Tenant data directory |
| `AEGIS_ADMIN_KEY` | `aegis-admin-default-key` | Admin API key for tenant management |

## Core Concepts

- **Tenants** — Isolated environments (FREE/STARTER/ENTERPRISE tiers with quotas)
- **Agents** — AI models (Claude, GPT, custom) registered with specific capabilities
- **Policies** — Declarative rules: conditions + effect (ALLOW/DENY/REQUIRE_HUMAN)
- **Actions** — Canonical format: agent + action name + params → decision + audit
- **Approvals** — Human-in-the-loop queue (1hr expiry)
- **Deltas** — Hash-chained state log (tamper-proof)

## API Reference

### No Auth Required
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

### Admin Key Required (`X-API-Key: <admin_key>`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/tenants` | Create tenant (returns API key) |
| GET | `/api/v1/tenants` | List all tenants |

### Tenant Key Required (`X-API-Key: <tenant_api_key>`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agents` | Register agent |
| GET | `/api/v1/agents` | List agents |
| POST | `/api/v1/agent/action` | **Submit action** (main entry point) |
| GET | `/api/v1/policies` | List policy rules |
| POST | `/api/v1/policies` | Create/update policies |
| POST | `/api/v1/policies/simulate` | Dry-run policy evaluation |
| GET | `/api/v1/state/query` | Query entity state |
| GET | `/api/v1/approvals` | List pending approvals |
| POST | `/api/v1/approvals/:id` | Approve/reject action |
| POST | `/api/v1/webhooks/manage` | Manage webhook subscriptions |
| GET | `/api/v1/deltas` | List delta history |
| GET | `/api/v1/deltas/verify` | Verify hash chain integrity |
| GET | `/api/v1/metrics/usage` | Usage stats per tenant |
| GET | `/api/v1/audit` | Audit log entries |

## Example: Full Flow

```bash
# 1. Create a tenant
curl -X POST http://localhost:3002/api/v1/tenants \
  -H "Content-Type: application/json" \
  -H "X-API-Key: aegis-admin-default-key" \
  -d '{"name":"My Team","tier":"STARTER"}'
# Returns: { "tenant_id": "...", "api_key": "..." }

# 2. Register an agent
curl -X POST http://localhost:3002/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <tenant_api_key>" \
  -d '{"name":"Claude Planner","provider":"claude","version":"opus-4","capabilities":["create_task","complete_task"],"cost_center":"planning"}'

# 3. Create a policy
curl -X POST http://localhost:3002/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <tenant_api_key>" \
  -d '{"rules":[{"action":"create_task","effect":"ALLOW","conditions":[],"priority":100,"enabled":true}]}'

# 4. Submit an action
curl -X POST http://localhost:3002/api/v1/agent/action \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <tenant_api_key>" \
  -d '{"agent_id":"<agent_id>","action":"create_task","params":{"title":"Ship v1"}}'
# Returns: { "status": "executed", "policy_decision": { "effect": "ALLOW" }, ... }
```

## Valid Agent Capabilities

`create_task`, `update_task`, `complete_task`, `delete_task`, `query_state`, `propose_delta`, `route_decision`, `request_approval`, `get_policy_simulation`, `register_webhook`

## Policy Rule Format

```json
{
  "action": "complete_task",
  "effect": "ALLOW",
  "conditions": [
    {"field": "agent.provider", "operator": "eq", "value": "claude"},
    {"field": "mode", "operator": "in", "value": ["BUILD", "COMPOUND"]}
  ],
  "priority": 100,
  "enabled": true
}
```

**Operators:** `eq`, `neq`, `in`, `not_in`, `gt`, `lt`, `gte`, `lte`, `exists`
**Effects:** `ALLOW`, `DENY`, `REQUIRE_HUMAN`

## Tenant Tiers

| Tier | Agents | Actions/hr | Entities | Webhooks |
|------|--------|-----------|----------|----------|
| FREE | 2 | 100 | 1,000 | 2 |
| STARTER | 10 | 1,000 | 5,000 | 10 |
| ENTERPRISE | 100 | 10,000 | 100,000 | 100 |

## Architecture

```
src/
  api/server.ts              Express entry point
  api/routes/                 8 route modules
  agents/                     Agent registry + action processor
  policies/                   Policy engine + store + decision cache
  approval/                   Human-in-the-loop approval queue
  tenants/                    Multi-tenant CRUD + API key auth
  gateway/                    Auth middleware + rate limiter
  events/                     Event bus + webhook dispatcher + audit log
  cost/                       Usage tracking per tenant
  storage/                    File-based per-tenant JSON storage
  core/                       Types + delta (hash chain) + entity registry
  observability/              Logger + metrics + health
  ui/                         Dashboard HTML
  tests/                      Test suite
contracts/schemas/            7 JSON Schema contracts
```

## Stack

- Express 5 + TypeScript 5.3 (strict)
- File-based storage (`.aegis-data/` per-tenant directories)
- SHA256 hash-chained deltas (tamper-proof)
- Zero external services required (no Redis, no Postgres)

## Part of Pre Atlas

Lives at `services/aegis-fabric/` in the Pre Atlas monorepo. Zero coupling to other services.
