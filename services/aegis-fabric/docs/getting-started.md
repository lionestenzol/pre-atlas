# Getting Started with Aegis Fabric

This guide walks you through setting up Aegis to govern your AI agents in 5 minutes.

## Prerequisites

- Node.js 20+
- npm

## 1. Install & Start

```bash
git clone https://github.com/your-org/pre-atlas.git
cd pre-atlas/services/aegis-fabric
npm install
npm start
```

Server starts at `http://localhost:3002`. Verify:

```bash
curl http://localhost:3002/health
# {"status":"healthy","uptime":...}
```

## 2. Create a Tenant

Tenants are isolated environments. Each gets its own API key, agents, policies, and data.

```bash
curl -X POST http://localhost:3002/api/v1/tenants \
  -H "Content-Type: application/json" \
  -H "X-API-Key: aegis-admin-default-key" \
  -d '{"name": "My Company", "tier": "STARTER"}'
```

Response:
```json
{
  "tenant_id": "t_abc123",
  "api_key": "ak_xxxxxxxxxxxxxxxx",
  "name": "My Company",
  "tier": "STARTER"
}
```

Save the `api_key` — you'll use it for all subsequent calls.

## 3. Register an Agent

Tell Aegis about the AI agents you want to govern.

```bash
curl -X POST http://localhost:3002/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_xxxxxxxxxxxxxxxx" \
  -d '{
    "name": "Task Planner",
    "provider": "claude",
    "version": "opus-4",
    "capabilities": ["create_task", "complete_task", "delete_task"]
  }'
```

Response:
```json
{
  "agent_id": "ag_def456",
  "name": "Task Planner",
  "status": "active"
}
```

**Valid capabilities:** `create_task`, `update_task`, `complete_task`, `delete_task`, `query_state`, `propose_delta`, `route_decision`, `request_approval`, `get_policy_simulation`, `register_webhook`

## 4. Create a Policy

Policies are declarative rules that control what agents can do. Each rule has:
- **action**: What action it applies to
- **effect**: `ALLOW`, `DENY`, or `REQUIRE_HUMAN`
- **conditions**: Optional filters (agent, mode, context fields)
- **priority**: Higher priority rules are evaluated first

```bash
# Allow task creation, but require human approval for deletion
curl -X POST http://localhost:3002/api/v1/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_xxxxxxxxxxxxxxxx" \
  -d '{
    "rules": [
      {
        "action": "create_task",
        "effect": "ALLOW",
        "conditions": [],
        "priority": 100,
        "enabled": true
      },
      {
        "action": "delete_task",
        "effect": "REQUIRE_HUMAN",
        "conditions": [],
        "priority": 100,
        "enabled": true
      }
    ]
  }'
```

### Condition Examples

```json
// Only allow Claude agents to create tasks
{
  "action": "create_task",
  "effect": "ALLOW",
  "conditions": [
    {"field": "agent.provider", "operator": "eq", "value": "claude"}
  ]
}

// Deny all actions when in CLOSURE mode
{
  "action": "*",
  "effect": "DENY",
  "conditions": [
    {"field": "mode", "operator": "eq", "value": "CLOSURE"}
  ]
}
```

**Operators:** `eq`, `neq`, `in`, `not_in`, `gt`, `lt`, `gte`, `lte`, `exists`

## 5. Submit an Action

This is the main integration point. Before your agent acts, ask Aegis.

```bash
curl -X POST http://localhost:3002/api/v1/agent/action \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_xxxxxxxxxxxxxxxx" \
  -d '{
    "agent_id": "ag_def456",
    "action": "create_task",
    "params": {"title": "Ship v1", "priority": "high"}
  }'
```

Response (allowed):
```json
{
  "status": "executed",
  "policy_decision": {
    "effect": "ALLOW",
    "matched_rule": "create_task"
  }
}
```

Response (denied):
```json
{
  "status": "blocked",
  "policy_decision": {
    "effect": "DENIED",
    "reason": "Policy 'no-delete-in-prod' denied this action"
  }
}
```

Response (needs approval):
```json
{
  "status": "pending_approval",
  "approval_id": "apr_xyz789",
  "expires_at": "2024-01-15T12:00:00Z"
}
```

## 6. Check the Audit Log

Every action is logged immutably.

```bash
curl http://localhost:3002/api/v1/audit \
  -H "X-API-Key: ak_xxxxxxxxxxxxxxxx"
```

## Integration Pattern

In your agent code:

```typescript
async function governedAction(agentId: string, action: string, params: any) {
  const res = await fetch('http://localhost:3002/api/v1/agent/action', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': process.env.AEGIS_API_KEY,
    },
    body: JSON.stringify({ agent_id: agentId, action, params }),
  });

  const decision = await res.json();

  if (decision.status === 'blocked') {
    throw new Error(`Action denied: ${decision.policy_decision.reason}`);
  }

  if (decision.status === 'pending_approval') {
    // Wait for human approval or timeout
    return { pending: true, approval_id: decision.approval_id };
  }

  // Action was allowed — proceed
  return decision;
}
```

## Next Steps

- **Simulate policies** before deploying: `POST /api/v1/policies/simulate`
- **Set up webhooks** for real-time notifications: `POST /api/v1/webhooks/manage`
- **Verify integrity** of the audit trail: `GET /api/v1/deltas/verify`
- **Monitor usage** per tenant: `GET /api/v1/metrics/usage`
