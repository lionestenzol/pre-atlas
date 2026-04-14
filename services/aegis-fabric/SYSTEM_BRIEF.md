# Aegis Enterprise Fabric — System Brief

> Use this document to onboard any AI into the AEF system for discussion, extension, or integration.

---

## What Is This

Aegis Enterprise Fabric (AEF) is a **policy-gated, multi-tenant execution layer for AI agents**. It sits between AI models (Claude, OpenAI, custom) and the actions they want to take. Every agent action is:

1. **Normalized** — diverse LLM tool call formats converted to a canonical form
2. **Policy-checked** — evaluated against declarative JSON rules (ALLOW / DENY / REQUIRE_HUMAN)
3. **Executed or blocked** — allowed actions create hash-chained deltas; denied actions return reasons; human-required actions queue for approval
4. **Audited** — every decision is logged in an append-only audit trail

It is part of **Pre Atlas**, a personal behavioral governance system. AEF is the enterprise-grade layer that governs what AI agents can and cannot do.

---

## Architecture Overview

```
                         ┌─────────────────────────┐
                         │   AI Agents              │
                         │   (Claude, OpenAI, etc.) │
                         └────────────┬────────────┘
                                      │ HTTP POST
                         ┌────────────▼────────────┐
                         │   Agent Adapter          │
                         │   Normalizes tool call   │
                         │   formats → Canonical    │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │         API Gateway (Express)      │
                    │   Auth → Rate Limit → Route        │
                    └─────────────────┬──────────────────┘
                                      │
                    ┌─────────────────▼──────────────────┐
                    │         Policy Engine               │
                    │   Declarative JSON rules            │
                    │   First match wins, default ALLOW   │
                    └───┬─────────┬─────────┬────────────┘
                        │         │         │
                     ALLOW      DENY    REQUIRE_HUMAN
                        │         │         │
                    ┌───▼──┐  ┌──▼──┐  ┌───▼───────┐
                    │Exec  │  │403  │  │Approval   │
                    │Delta │  │+why │  │Queue      │
                    └───┬──┘  └─────┘  │(human     │
                        │              │ reviews)  │
                    ┌───▼──────────┐   └───────────┘
                    │ Hash-chained │
                    │ Delta Log    │
                    │ (RFC 6902)   │
                    └───┬──────────┘
                        │
                    ┌───▼──────────┐
                    │ Audit + Events│
                    │ + Webhooks   │
                    └──────────────┘
```

---

## Core Concepts

### Entities & Deltas
Every object is an **Entity** (UUID, type, version, SHA-256 hash). Every change is a **Delta** (RFC 6902 JSON Patch with hash chain). State is reconstructed by folding deltas. The hash chain is tamper-evident: `prev_hash → apply patch → new_hash`.

**8 entity types:** tenant, agent, task, policy, approval, webhook, usage_record, audit_entry

### Multi-Tenancy
Each tenant gets isolated file storage under `.aegis-data/tenants/{id}/`. Tenants have tiers (FREE / STARTER / ENTERPRISE) with quota limits on agents, actions/hr, entities, delta log size, and webhooks.

### Mode System
6 modes inherited from Pre Atlas: `RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE`. Modes are per-tenant and can be used in policy conditions.

### Agent Adapter
Normalizes three formats into `CanonicalAgentAction`:
- **Claude:** `{ type: "tool_use", name: "create_task", input: {...} }`
- **OpenAI:** `{ function: { name: "create_task", arguments: "{...}" } }`
- **Direct:** `{ action: "create_task", params: {...} }`

### Policy Engine
Declarative JSON rules with 9 operators (eq, neq, in, not_in, gt, lt, gte, lte, exists). Three effects: ALLOW, DENY, REQUIRE_HUMAN. Rules sorted by priority (lower = higher), first match wins. Default is ALLOW when no rules match.

**Addressable fields for conditions:**
```
tenant.tier, tenant.mode, agent.provider, agent.capabilities,
action, mode, params.*
```

### Approval Workflow
When policy returns REQUIRE_HUMAN, the action is queued. Approvals are entities with lifecycle: PENDING → APPROVED / REJECTED / EXPIRED (1hr default). On approve, the original action is re-executed.

### 10 Agent Actions
```
create_task    — Create a new task entity
update_task    — Modify task fields via delta
complete_task  — Set task status to DONE
delete_task    — Archive a task (soft delete)
query_state    — Read entity or list by type
propose_delta  — Submit arbitrary state change
route_decision — Request routing guidance
request_approval — Explicitly request human review
get_policy_simulation — Test what policy would do
register_webhook — Subscribe to events
```

---

## API Surface

**Port 3002** | Express | JSON | Auth via `X-API-Key` header

| Route | Auth | Purpose |
|-------|------|---------|
| `GET /health` | none | Health check |
| `GET /metrics` | none | Prometheus metrics |
| `GET /ui/dashboard.html` | none | Web dashboard |
| `POST /api/v1/tenants` | admin key | Create tenant |
| `GET /api/v1/tenants` | admin key | List tenants |
| `POST /api/v1/agents` | tenant key | Register agent |
| `GET /api/v1/agents` | tenant key | List agents |
| `POST /api/v1/agent/action` | tenant key | Submit action (main endpoint) |
| `GET /api/v1/policies` | tenant key | Get policy rules |
| `POST /api/v1/policies/rules` | tenant key | Add policy rule |
| `DELETE /api/v1/policies/rules/:id` | tenant key | Remove rule |
| `POST /api/v1/policies/simulate` | tenant key | Test policy |
| `GET /api/v1/approvals` | tenant key | List pending approvals |
| `POST /api/v1/approvals/:id/approve` | tenant key | Approve action |
| `POST /api/v1/approvals/:id/reject` | tenant key | Reject action |
| `GET /api/v1/state/entities` | tenant key | List entities by type |
| `GET /api/v1/state/entities/:id` | tenant key | Get entity + state |
| `GET /api/v1/state/deltas` | tenant key | List deltas |
| `POST /api/v1/state/snapshots` | tenant key | Create snapshot |
| `POST /api/v1/webhooks` | tenant key | Register webhook |
| `GET /api/v1/audit` | tenant key | Audit trail |
| `GET /api/v1/usage` | tenant key | Usage per agent |

---

## Key Types

```typescript
// Tenant tiers and quotas
type TenantTier = 'FREE' | 'STARTER' | 'ENTERPRISE';
// FREE: 2 agents, 100 actions/hr, 500 entities
// STARTER: 10 agents, 1000 actions/hr, 5000 entities
// ENTERPRISE: 100 agents, 10000 actions/hr, 100000 entities

// Policy rule
interface PolicyRule {
  rule_id: UUID;
  name: string;
  priority: number;        // lower = higher priority
  conditions: Array<{
    field: string;         // dot-path: 'action', 'tenant.tier', 'agent.provider', 'mode'
    operator: 'eq'|'neq'|'in'|'not_in'|'gt'|'lt'|'gte'|'lte'|'exists';
    value: unknown;
  }>;
  effect: 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
  reason: string;
  enabled: boolean;
}

// Canonical action (what all agent formats normalize into)
interface CanonicalAgentAction {
  action_id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  action: AgentActionName;   // one of 10 actions
  params: Record<string, unknown>;
  metadata: {
    provider: 'claude' | 'openai' | 'local' | 'custom';
    model_id?: string;
    tokens_used?: number;
    cost_usd?: number;
  };
  timestamp: number;
}

// Action response
interface ActionResponse {
  status: 'executed' | 'denied' | 'pending_approval';
  action_id: UUID;
  result?: { entity_id: UUID; delta_id: UUID; state: unknown };
  policy_decision: {
    effect: 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN';
    matched_rule: string | null;
    reason: string;
    cached: boolean;
  };
  approval?: { approval_id: UUID; status: string; expires_at: number };
  usage?: { actions_remaining_this_hour: number };
}
```

---

## Storage Model

```
.aegis-data/
├── tenants/
│   └── {tenant_id}/
│       ├── entities.json      — Map<entity_id, { entity, state }>
│       └── deltas.json        — Delta[]
├── audit/
│   └── {tenant_id}/
│       └── audit.jsonl        — append-only audit entries
├── logs/
│   └── requests.jsonl         — HTTP request/response log
├── tenants.json               — global tenant registry
├── policies.json              — global policy store
└── webhooks.json              — global webhook registry
```

All storage is file-based JSON. No database required. Each tenant's data is fully isolated.

---

## Observability

- **Audit log:** Append-only JSONL per tenant — every action + policy decision
- **Event bus:** In-process pub/sub (8 event types: action.completed, action.denied, approval.requested, approval.decided, task.created, task.completed, policy.violated, tenant.mode_changed)
- **Webhooks:** HTTP POST notifications on subscribed events
- **Usage tracking:** Per-agent daily action counts with cost tracking
- **Prometheus metrics:** `/metrics` endpoint with counters and histograms

---

## File Structure

```
services/aegis-fabric/
├── package.json                    (express, cors, tsx, typescript)
├── tsconfig.json
├── start.bat
├── specs/                          (6 locked spec documents)
│   ├── v0-core-schemas.md
│   ├── v0-policy-engine.md
│   ├── v0-agent-gateway.md
│   ├── v0-approval-workflow.md
│   ├── v0-api-routes.md
│   └── v0-observability.md
├── contracts/schemas/              (7 JSON Schema draft-07 contracts)
│   ├── AegisTenant.v1.json
│   ├── AegisAgent.v1.json
│   ├── AegisPolicy.v1.json
│   ├── AegisAgentAction.v1.json
│   ├── AegisApproval.v1.json
│   ├── AegisWebhook.v1.json
│   └── AegisPolicyDecision.v1.json
└── src/
    ├── core/                       (types.ts, delta.ts, entity-registry.ts)
    ├── storage/                    (aegis-storage.ts, snapshot-manager.ts)
    ├── tenants/                    (tenant-registry.ts, tenant-isolation.ts)
    ├── gateway/                    (api-middleware.ts, rate-limiter.ts, request-logger.ts)
    ├── agents/                     (agent-registry.ts, agent-adapter.ts, action-processor.ts)
    ├── policies/                   (policy-engine.ts, policy-store.ts, decision-cache.ts)
    ├── approval/                   (approval-queue.ts)
    ├── events/                     (event-bus.ts, webhook-dispatcher.ts, audit-log.ts)
    ├── observability/              (logger.ts, metrics.ts, health.ts)
    ├── cost/                       (usage-tracker.ts)
    ├── api/                        (server.ts + 7 route modules)
    ├── ui/                         (dashboard.html)
    └── tests/                      (6 test files, 31 passing tests)
```

---

## Current State

- **Version:** 0.1.0 (prototype)
- **Tests:** 31/31 passing
- **Default policy:** Permissive (ALLOW everything when no rules exist)
- **Dashboard:** Fully functional 6-tab UI at `/ui/dashboard.html`
- **No default rules seeded** — the policy engine works but starts empty per tenant

---

## What You Can Discuss / Extend

1. **Default policy rules** — what should be denied or require human approval by default per mode?
2. **Production hardening** — rate limit tuning, HTTPS-only webhooks, admin key rotation
3. **Agent integration** — how to connect a real Claude or OpenAI agent to submit actions
4. **Policy design patterns** — mode-aware rules, tier-based restrictions, capability-gated access
5. **Event-driven workflows** — webhook consumers, approval notification channels
6. **State model extensions** — new entity types, custom metadata schemas
7. **Scaling** — database backend, event queue, horizontal scaling
8. **Cost governance** — per-agent budgets, token limits, cost alerts
