# Aegis Enterprise Fabric v0 — Approval Workflow

**Status:** LOCKED
**Version:** 0.1.0

Human-in-the-loop approval for high-risk agent actions. When a policy rule returns `REQUIRE_HUMAN`, the action is queued instead of executed.

---

## DESIGN LAW

- Approval is triggered by policy, not by agents — agents cannot bypass
- Approvals are entities with their own delta history
- Approvals expire after 1 hour by default
- Only three terminal states: APPROVED, REJECTED, EXPIRED
- A PENDING approval can only transition once

---

## APPROVAL DATA

```typescript
ApprovalData {
  tenant_id: UUID
  action_id: UUID               // the action that triggered this
  agent_id: UUID                // the agent that submitted the action
  action: AgentActionName       // what the agent tried to do
  params: Record<string, unknown>  // action parameters for review
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED"
  requested_at: Timestamp
  decided_at: Timestamp | null
  decided_by: string | null     // human reviewer identifier
  reason: string | null         // reviewer's reason
  expires_at: Timestamp         // default: requested_at + 1 hour
}
```

---

## LIFECYCLE

```
    Policy returns REQUIRE_HUMAN
              │
    ┌─────────▼──────────┐
    │ Create approval     │
    │ entity (PENDING)    │
    │ expires_at = now()  │
    │ + 3,600,000ms       │
    └─────────┬──────────┘
              │
              │  API returns 202
              │  { status: "pending_approval",
              │    approval: { approval_id, status, expires_at } }
              │
    ┌─────────▼──────────┐
    │ PENDING             │
    │ (visible in         │
    │  dashboard +        │
    │  API list)          │
    └───┬────┬────┬──────┘
        │    │    │
        │    │    └── expires_at reached
        │    │        → status = EXPIRED
        │    │          decided_by = "system"
        │    │          reason = "Approval expired"
        │    │
        │    └── POST /api/v1/approvals/:id/reject
        │        { decided_by, reason }
        │        → status = REJECTED
        │
        └── POST /api/v1/approvals/:id/approve
            { decided_by, reason }
            → status = APPROVED
            → re-execute original action
```

---

## API ENDPOINTS

```
GET  /api/v1/approvals              List pending approvals for tenant
GET  /api/v1/approvals/:id          Get specific approval
POST /api/v1/approvals/:id/approve  Approve (body: { decided_by, reason? })
POST /api/v1/approvals/:id/reject   Reject  (body: { decided_by, reason? })
```

---

## RE-EXECUTION ON APPROVE

When an approval is APPROVED, the original `CanonicalAgentAction` (stored in the approval's `params` and `action` fields) is re-submitted to the `ActionProcessor`. The re-execution:

1. Skips policy evaluation (already approved)
2. Executes the action (creates entities/deltas)
3. Emits `approval.decided` event
4. Emits `action.completed` event

---

## EXPIRATION CHECK

`ApprovalQueue.checkExpirations(tenantId)` scans all PENDING approvals and marks expired ones. This is called:
- On each approval list request (lazy cleanup)
- Can be called on an interval by the server (not implemented in v0)

---

## WEBHOOK EVENTS

```
approval.requested  — fired when REQUIRE_HUMAN creates a new approval
approval.decided    — fired when approval is APPROVED, REJECTED, or EXPIRED
```

---

## ENFORCEMENT RULES

1. Only PENDING approvals can be approved or rejected
2. A decided approval (APPROVED/REJECTED/EXPIRED) is immutable
3. Expiration is checked lazily — approval may briefly outlive its `expires_at`
4. The `decided_by` field must be non-empty for APPROVED/REJECTED
5. Approval entity is stored under the tenant's isolation scope
6. Dashboard shows countdown timer based on `expires_at - now()`
