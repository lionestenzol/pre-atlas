# Aegis Enterprise Fabric v0 — API Routes

**Status:** LOCKED
**Version:** 0.1.0

Complete HTTP API surface. Express server on port 3002.

---

## DESIGN LAW

- All data routes require `X-API-Key` header
- Admin routes (tenant management) use `AEGIS_ADMIN_KEY`
- Tenant routes use tenant-specific API keys
- Health and metrics endpoints are unauthenticated
- Dashboard UI is served as static files (no auth)
- All responses are JSON

---

## ROUTE MAP

```
PORT 3002
│
├── GET  /health                          [no auth]
├── GET  /metrics                         [no auth]
├── GET  /ui/*                            [no auth, static]
│
├── ADMIN ROUTES (X-API-Key = AEGIS_ADMIN_KEY)
│   ├── POST /api/v1/tenants             Create tenant
│   └── GET  /api/v1/tenants             List all tenants
│
├── TENANT ROUTES (X-API-Key = tenant key)
│   │
│   ├── AGENTS
│   │   ├── POST /api/v1/agents          Register agent
│   │   └── GET  /api/v1/agents          List agents
│   │
│   ├── ACTIONS
│   │   └── POST /api/v1/agent/action    Submit agent action
│   │
│   ├── POLICIES
│   │   ├── GET  /api/v1/policies        Get tenant policies
│   │   ├── POST /api/v1/policies/rules  Add policy rule
│   │   ├── DELETE /api/v1/policies/rules/:id  Remove rule
│   │   └── POST /api/v1/policies/simulate     Simulate policy
│   │
│   ├── APPROVALS
│   │   ├── GET  /api/v1/approvals              List pending
│   │   ├── GET  /api/v1/approvals/:id          Get approval
│   │   ├── POST /api/v1/approvals/:id/approve  Approve
│   │   └── POST /api/v1/approvals/:id/reject   Reject
│   │
│   ├── STATE
│   │   ├── GET  /api/v1/state/entities         List entities by type
│   │   ├── GET  /api/v1/state/entities/:id     Get entity + state
│   │   ├── GET  /api/v1/state/deltas           List deltas
│   │   ├── GET  /api/v1/state/deltas/:id       Get delta
│   │   ├── POST /api/v1/state/snapshots        Create snapshot
│   │   └── GET  /api/v1/state/snapshots        List snapshots
│   │
│   ├── WEBHOOKS
│   │   ├── POST /api/v1/webhooks               Register webhook
│   │   ├── GET  /api/v1/webhooks               List webhooks
│   │   └── DELETE /api/v1/webhooks/:id         Remove webhook
│   │
│   ├── AUDIT
│   │   └── GET  /api/v1/audit                  Recent audit entries
│   │
│   └── METRICS
│       └── GET  /api/v1/usage                  Usage stats per agent
│
└── MIDDLEWARE CHAIN
    1. CORS (all origins)
    2. JSON body parser
    3. Static file serving (/ui)
    4. Request ID + timestamp
    5. Response logging
    6. Authentication (X-API-Key)
    7. Rate limiting (token bucket)
```

---

## KEY ENDPOINTS DETAIL

### POST /api/v1/tenants (admin)

```
Request:  { name, tier?, mode?, isolation_model?, quotas? }
Response: { tenant_id, name, tier, mode, api_key, quotas }
          (api_key is returned ONCE on creation, stored as SHA-256 hash)
```

### POST /api/v1/agent/action (tenant)

```
Request:  Claude format:  { agent_id, type: "tool_use", name, input }
          OpenAI format:  { agent_id, function: { name, arguments } }
          Direct format:  { agent_id, action, params }

Response: { status, action_id, result?, policy_decision, approval?, usage? }
          status: "executed" (200) | "denied" (403) | "pending_approval" (202)
```

### POST /api/v1/policies/simulate (tenant)

```
Request:  { agent_id, action, params? }
Response: { decision, evaluated_rules: [{ rule, matched }] }
```

---

## HEALTH RESPONSE

```typescript
HealthResponse {
  status: "healthy" | "degraded" | "unhealthy"
  uptime_ms: number
  version: string               // "0.1.0"
  tenants_loaded: number
  storage_accessible: boolean
}
```

---

## ERROR FORMAT

All errors follow:
```json
{ "error": "Human-readable error message" }
```

HTTP status codes:
- 400 — Bad request (missing fields, invalid format)
- 401 — Missing or invalid API key
- 403 — Tenant disabled or policy DENY
- 404 — Resource not found
- 429 — Rate limit exceeded
- 500 — Internal server error

---

## ENFORCEMENT RULES

1. Static UI files are served before auth middleware (public access)
2. Admin key defaults to `aegis-admin-default-key` (override via `AEGIS_ADMIN_KEY` env)
3. Tenant API key is generated once on creation and never retrievable again
4. Rate limit response includes `remaining` and `retry_after_ms`
5. All request/response pairs are logged with timing in the request logger
6. CORS is permissive (all origins) for prototype — restrict in production
