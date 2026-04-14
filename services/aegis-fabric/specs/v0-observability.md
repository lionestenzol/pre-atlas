# Aegis Enterprise Fabric v0 — Observability & Events

**Status:** LOCKED
**Version:** 0.1.0

Audit logging, event bus, webhook dispatch, usage tracking, and Prometheus-compatible metrics.

---

## DESIGN LAW

- Audit log is append-only JSONL — never modified, never deleted
- Events are fire-and-forget within the process (no message queue in v0)
- Webhooks retry once on failure, then mark as failed
- Usage is tracked per agent per day
- Metrics are exposed as Prometheus text format at `/metrics`

---

## AUDIT LOG

Append-only per-tenant audit trail stored as JSONL files.

```typescript
AuditEntry {
  audit_id: UUID
  tenant_id: UUID
  agent_id: UUID
  action: AgentActionName
  effect: PolicyEffect          // ALLOW, DENY, REQUIRE_HUMAN
  entity_ids_affected: UUID[]
  delta_id: UUID | null
  timestamp: Timestamp
  metadata: Record<string, unknown>
}
```

Storage path: `.aegis-data/audit/{tenant_id}/audit.jsonl`

### Audit API

```
GET /api/v1/audit?limit=20    Returns last N audit entries for authenticated tenant
```

---

## EVENT BUS

In-process pub/sub. Components emit events, listeners react.

### Event Types (8)

```
action.completed     — agent action executed successfully
action.denied        — policy denied an agent action
approval.requested   — REQUIRE_HUMAN created an approval
approval.decided     — approval was APPROVED, REJECTED, or EXPIRED
task.created         — new task entity created
task.completed       — task status changed to DONE
policy.violated      — reserved for future anomaly detection
tenant.mode_changed  — tenant mode transition
system.startup       — server started
```

---

## WEBHOOK DISPATCH

Webhooks subscribe to event types and receive HTTP POST notifications.

```typescript
WebhookData {
  tenant_id: UUID
  url: string                   // HTTPS endpoint
  events: WebhookEventType[]    // subscribed event types
  secret_hash: SHA256           // for HMAC signature verification
  enabled: boolean
  retry_count: number
  last_triggered_at: Timestamp | null
  failure_count: number
  created_at: Timestamp
}
```

### Webhook Payload

```json
{
  "event": "action.completed",
  "tenant_id": "...",
  "timestamp": 1708646400000,
  "data": { ... }
}
```

### Retry Policy (v0)
- 1 retry on failure (HTTP non-2xx or network error)
- Failure count incremented on each failure
- No exponential backoff in v0

---

## USAGE TRACKING

Per-agent daily usage records.

```typescript
UsageRecord {
  tenant_id: UUID
  agent_id: UUID
  period: string                // "YYYY-MM-DD"
  actions_count: number
  tokens_used: number
  cost_usd: number
  by_action: Partial<Record<AgentActionName, number>>
  updated_at: Timestamp
}
```

### Usage API

```
GET /api/v1/usage              Usage stats per agent for authenticated tenant
```

---

## PROMETHEUS METRICS

Exposed at `GET /metrics` (no auth required).

```
# HELP aegis_actions_total Total actions processed
# TYPE aegis_actions_total counter
aegis_actions_total{tenant="...",agent="...",action="...",effect="..."} N

# HELP aegis_action_duration_seconds Action processing duration
# TYPE aegis_action_duration_seconds histogram
aegis_action_duration_seconds{tenant="...",action="..."} N.NNN

# HELP aegis_active_tenants Number of loaded tenants
# TYPE aegis_active_tenants gauge
aegis_active_tenants N

# HELP aegis_active_agents Number of registered agents
# TYPE aegis_active_agents gauge
aegis_active_agents N
```

---

## REQUEST LOGGING

Every HTTP request/response is logged with:

```typescript
RequestLog {
  timestamp: Timestamp
  tenant_id: UUID | null
  agent_id: string | null
  method: string                // "GET", "POST", etc.
  path: string
  status_code: number
  duration_ms: number
  request_id: string
}
```

Storage path: `.aegis-data/logs/requests.jsonl`

---

## ENFORCEMENT RULES

1. Audit log files are never truncated or rotated in v0
2. Webhook URLs must be HTTPS in production (HTTP allowed for localhost in prototype)
3. Webhook secret is stored as SHA-256 hash — raw secret never persisted
4. Usage records are upserted (created or incremented) per `(tenant, agent, period)` key
5. Metrics endpoint is unauthenticated — restrict at network level in production
6. Request IDs are UUIDs attached at middleware layer for correlation
