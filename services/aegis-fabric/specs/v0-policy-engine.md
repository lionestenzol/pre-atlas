# Aegis Enterprise Fabric v0 — Policy Engine

**Status:** LOCKED
**Version:** 0.1.0

Declarative, JSON-based policy evaluation. Every agent action passes through the policy engine before execution.

---

## DESIGN LAW

- Policy evaluation is synchronous and deterministic
- First matching rule wins (sorted by priority, lower number = higher priority)
- Default is ALLOW when no rules match (permissive prototype default)
- All conditions in a rule use AND logic
- Decision cache avoids redundant evaluation (60s TTL)
- Simulation mode evaluates without caching or side effects

---

## POLICY RULE

```typescript
PolicyRule {
  rule_id: UUID
  name: string
  description: string
  priority: number              // lower = higher priority, first match wins
  conditions: PolicyCondition[] // AND logic — all must match
  effect: "ALLOW" | "DENY" | "REQUIRE_HUMAN"
  reason: string                // human-readable explanation
  enabled: boolean
  created_at: Timestamp
  updated_at: Timestamp
}
```

---

## POLICY CONDITION

```typescript
PolicyCondition {
  field: string                 // dot-path into evaluation context
  operator: PolicyOperator
  value: unknown
}
```

### Operators (9)

```
eq       — exact match
neq      — not equal
in       — field value is in array
not_in   — field value is not in array
gt       — greater than (numeric)
lt       — less than (numeric)
gte      — greater than or equal (numeric)
lte      — less than or equal (numeric)
exists   — field exists (value=true) or doesn't (value=false)
```

### Addressable Fields

```
tenant.id           UUID
tenant.tier         "FREE" | "STARTER" | "ENTERPRISE"
tenant.mode         Mode
agent.id            UUID
agent.provider      "claude" | "openai" | "local" | "custom"
agent.capabilities  AgentActionName[]
action              AgentActionName
mode                Mode
params.*            (any param field)
```

---

## EVALUATION CONTEXT

Built from the incoming action, the resolved tenant, and the resolved agent.

```typescript
PolicyEvaluationContext {
  tenant: { id: UUID; tier: TenantTier; mode: Mode }
  agent: { id: UUID; provider: AgentProvider; capabilities: AgentActionName[] }
  action: AgentActionName
  params: Record<string, unknown>
  mode: Mode
}
```

---

## POLICY DECISION

```typescript
PolicyDecision {
  decision_id: UUID
  tenant_id: UUID
  agent_id: UUID
  action: AgentActionName
  effect: "ALLOW" | "DENY" | "REQUIRE_HUMAN"
  matched_rule_id: UUID | null     // null = default allow
  reason: string
  context: {
    mode: Mode
    tenant_tier: TenantTier
    agent_provider: AgentProvider
  }
  cached: boolean
  evaluated_at: Timestamp
  cache_ttl_ms: number             // 60,000ms default
}
```

---

## EVALUATION FLOW

```
                    ┌──────────────────┐
                    │  Agent submits    │
                    │  action           │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Check cache      │──── HIT ──→ return cached decision
                    └────────┬─────────┘
                             │ MISS
                    ┌────────▼─────────┐
                    │  Load rules for   │
                    │  tenant (sorted   │
                    │  by priority)     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  For each rule:   │
                    │  evaluate all     │
                    │  conditions (AND) │
                    │                   │
                    │  First match wins │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
          ┌─────▼────┐ ┌────▼─────┐ ┌────▼──────┐
          │  ALLOW   │ │  DENY    │ │ REQUIRE   │
          │          │ │          │ │ _HUMAN    │
          └──────────┘ └──────────┘ └───────────┘
                             │
                    No match → default ALLOW
```

---

## SIMULATION

`PolicyEngine.simulate(context)` returns:
- The decision (same as `evaluate`)
- An array of `{ rule, matched }` for every rule evaluated

Used by the dashboard Policy tab to test rules before actions are submitted.

---

## ENFORCEMENT RULES

1. Rules are stored per tenant — tenant A cannot see tenant B's rules
2. Priority must be a positive integer; ties resolved by insertion order
3. A rule with `enabled: false` is skipped during evaluation
4. Cache is keyed on `(tenant_id, agent_id, action, mode)` — mode changes invalidate
5. `invalidateCache(tenantId)` clears all cached decisions for a tenant (called on rule add/remove)
6. Simulation never writes to cache
7. Default ALLOW is an explicit design decision — production deployments should seed deny-by-default rules
