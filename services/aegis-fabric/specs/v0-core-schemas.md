# Aegis Enterprise Fabric v0 — Core Schemas

**Status:** LOCKED
**Version:** 0.1.0

These are the foundational types for the entire AEF system. All modules depend on these.

---

## DESIGN LAW

- No overwrites — all state changes are hash-chained deltas (RFC 6902 JSON Patch)
- Every object is an Entity with version history and tamper-evident hash chain
- Multi-tenancy is mandatory — every operation is scoped to a tenant
- Mode system mirrors delta-kernel: RECOVER | CLOSURE | MAINTENANCE | BUILD | COMPOUND | SCALE
- All timestamps are Unix epoch milliseconds

---

## PRIMITIVES

```
UUID    = string        // crypto.randomUUID()
Timestamp = number      // Date.now() — Unix epoch ms
SHA256  = string        // SHA-256 hex digest of entity state
```

---

## ENTITY

Every object in the system is an Entity.

```typescript
Entity {
  entity_id: UUID
  entity_type: AegisEntityType
  created_at: Timestamp
  current_version: number        // increments on each delta
  current_hash: SHA256           // SHA-256 of current state
  is_archived: boolean
}
```

### Entity Types (8)

```
aegis_tenant | aegis_agent | aegis_task | aegis_policy
aegis_approval | aegis_webhook | aegis_usage_record | aegis_audit_entry
```

---

## DELTA

Every change to an entity is a Delta. Chain is tamper-evident: `prev_hash → new_hash`.

```typescript
Delta {
  delta_id: UUID
  entity_id: UUID
  tenant_id: UUID
  timestamp: Timestamp
  author: "user" | "system" | "agent" | "policy-engine"
  patch: JsonPatch[]             // RFC 6902
  prev_hash: SHA256
  new_hash: SHA256
}
```

### JSON Patch

```typescript
JsonPatch {
  op: "add" | "replace" | "remove"
  path: string                   // JSON Pointer (e.g. "/status")
  value?: unknown
}
```

Reconstruction = fold deltas in order. Verify by recomputing hash chain.

---

## TENANT

```typescript
TenantData {
  name: string
  tier: "FREE" | "STARTER" | "ENTERPRISE"
  mode: Mode
  isolation_model: "SILOED" | "POOLED"
  quotas: TenantQuotas
  api_key_hash: SHA256
  capabilities: string[]
  enabled: boolean
  created_at: Timestamp
  updated_at: Timestamp
}
```

### Quotas (per tier)

```
                    FREE    STARTER   ENTERPRISE
max_agents            2        10         100
max_actions/hr      100     1,000      10,000
max_entities        500     5,000     100,000
max_delta_log     5,000    50,000     500,000
max_webhooks          2        10         100
```

---

## AGENT

```typescript
AgentData {
  tenant_id: UUID
  name: string
  provider: "claude" | "openai" | "local" | "custom"
  version: string
  capabilities: AgentActionName[]
  cost_center: string
  enabled: boolean
  metadata: Record<string, unknown>
  created_at: Timestamp
  last_active_at: Timestamp
}
```

### Agent Actions (10)

```
create_task | update_task | complete_task | delete_task
query_state | propose_delta | route_decision
request_approval | get_policy_simulation | register_webhook
```

---

## TASK

```typescript
AegisTaskData {
  tenant_id: UUID
  title: string
  description: string
  status: "OPEN" | "IN_PROGRESS" | "BLOCKED" | "DONE" | "ARCHIVED"
  priority: 1 | 2 | 3 | 4 | 5
  tags: string[]
  assignee: UUID | null
  approval_required: boolean
  approval_status: "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED"
  due_at: Timestamp | null
  linked_entities: UUID[]
  metadata: Record<string, unknown>
  created_by: UUID
  created_at: Timestamp
  updated_at: Timestamp
}
```

---

## SNAPSHOT

Point-in-time capture for fast reconstruction.

```typescript
Snapshot {
  snapshot_id: UUID
  tenant_id: UUID
  delta_count: number
  last_delta_id: UUID
  last_delta_hash: SHA256
  entities: Array<{ entity: Entity; state: unknown }>
  created_at: Timestamp
}
```

---

## ENFORCEMENT RULES

1. Entity `entity_id` is immutable after creation
2. Delta `prev_hash` must match entity `current_hash` before applying
3. Delta `new_hash` = SHA-256(applied state) — verified on read
4. All entities scoped to a tenant — cross-tenant access is forbidden
5. Entity version increments by exactly 1 per delta
6. Archived entities reject further deltas
7. Mode transitions follow: RECOVER → CLOSURE → MAINTENANCE → BUILD → COMPOUND → SCALE
