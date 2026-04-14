# Aegis Enterprise Fabric v0 — Agent Gateway

**Status:** LOCKED
**Version:** 0.1.0

The agent gateway normalizes multi-vendor LLM tool calls, authenticates via API keys, rate-limits per tenant, and processes actions through the policy-gated execution pipeline.

---

## DESIGN LAW

- All agent interactions enter through a single endpoint: `POST /api/v1/agent/action`
- Every action is normalized to `CanonicalAgentAction` regardless of source format
- Three provider formats supported: Claude (`tool_use`), OpenAI (`function`), direct/custom
- Authentication is API key only — `X-API-Key` header
- Rate limiting uses token bucket per tenant, with optional per-agent breakdown
- Every action is audited in append-only JSONL

---

## CANONICAL AGENT ACTION

The normalized form all providers map into:

```typescript
CanonicalAgentAction {
  action_id: UUID
  tenant_id: UUID
  agent_id: UUID
  agent_version: string
  action: AgentActionName           // one of 10 valid actions
  params: Record<string, unknown>
  metadata: {
    provider: AgentProvider
    model_id?: string
    raw_tool_call?: unknown         // original payload preserved
    tokens_used?: number
    cost_usd?: number
    latency_ms?: number
  }
  timestamp: Timestamp
  idempotency_key?: string
}
```

---

## ADAPTER FORMAT DETECTION

```
Input payload
    │
    ├── has type="tool_use" + name  ──→  Claude format
    │   { type: "tool_use", name: "create_task", input: { title: "..." } }
    │
    ├── has function object          ──→  OpenAI format
    │   { function: { name: "create_task", arguments: "{\"title\":\"...\"}" } }
    │
    ├── has action string            ──→  Direct/custom format
    │   { action: "create_task", params: { title: "..." } }
    │
    └── none of the above           ──→  400 error: Unrecognized format
```

---

## ACTION PROCESSING PIPELINE

```
    POST /api/v1/agent/action
              │
    ┌─────────▼──────────┐
    │ Auth middleware      │──→ 401 if missing/invalid key
    │ (X-API-Key header)  │──→ 403 if tenant disabled
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ Rate limit check    │──→ 429 if exceeded
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ Resolve agent       │──→ 404 if not found
    │ from agent_id       │──→ 400 if agent disabled
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ Normalize payload   │──→ 400 if format unrecognized
    │ (agent adapter)     │
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ Policy evaluation   │
    └───┬─────┬─────┬────┘
        │     │     │
     ALLOW  DENY  REQUIRE_HUMAN
        │     │     │
        │     │     └─→ 202 + approval queued
        │     └───────→ 403 + policy_decision
        │
    ┌───▼────────────────┐
    │ Execute action      │
    │ (create delta,      │
    │  mutate entity)     │
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │ Track usage         │
    │ Emit events         │
    │ Write audit log     │
    └─────────┬──────────┘
              │
          200 + ActionResponse
```

---

## ACTION RESPONSE

```typescript
ActionResponse {
  status: "executed" | "denied" | "pending_approval"
  action_id: UUID
  result?: {
    entity_id: UUID
    delta_id: UUID
    state: unknown
  }
  policy_decision: {
    effect: PolicyEffect
    matched_rule: string | null
    reason: string
    cached: boolean
  }
  approval?: {
    approval_id: UUID
    status: ApprovalWorkflowStatus
    expires_at: Timestamp
  }
  usage?: {
    actions_remaining_this_hour: number
  }
}
```

---

## AUTHENTICATION

```
Admin routes (/api/v1/tenants):
  X-API-Key must match AEGIS_ADMIN_KEY env var (default: "aegis-admin-default-key")

Tenant routes (all other /api/v1/*):
  X-API-Key is SHA-256 hashed and matched against tenant.api_key_hash

No-auth routes:
  GET /health
  GET /metrics
  GET /ui/*
```

---

## RATE LIMITING

Token bucket algorithm per tenant:
- Bucket size = `tenant.quotas.max_actions_per_hour`
- Refill rate = bucket size / 3600 tokens per second
- Optional per-agent breakdown
- 429 response includes `remaining` count and `retry_after_ms`

---

## ENFORCEMENT RULES

1. Every action must have a valid `agent_id` that resolves to a registered agent
2. Agent must have the submitted action in its `capabilities` array
3. Agent must be `enabled: true`
4. Tenant must be `enabled: true`
5. Rate limit is checked before policy evaluation (fail fast)
6. Original tool call payload is preserved in `metadata.raw_tool_call` for debugging
7. Idempotency key prevents duplicate processing of the same action
