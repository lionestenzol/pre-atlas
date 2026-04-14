#!/bin/bash
# Aegis Delta Fabric — Demo Data Seed Script
# Seeds the Pre Atlas Demo tenant with agents, policies, entities, deltas, approvals, webhooks

KERNEL="http://localhost:3001"
GW="http://localhost:3010"
DB="aegis_tnt_5d2af820b8e9"
H="-H Content-Type:application/json -H x-tenant-db:$DB"

echo "=== Registering Agents ==="

AGENT1=$(curl -s -X POST "$KERNEL/v1/agents" $H -d '{
  "name": "Claude Opus Planner",
  "provider": "claude",
  "version": "opus-4",
  "capabilities": ["create_task","update_task","complete_task","propose_delta"],
  "cost_center": "planning",
  "metadata": {"model_id":"claude-opus-4","team":"core"}
}')
echo "Agent 1: $AGENT1"
A1_ID=$(echo $AGENT1 | grep -o '"agent_id":"[^"]*"' | cut -d'"' -f4)

AGENT2=$(curl -s -X POST "$KERNEL/v1/agents" $H -d '{
  "name": "GPT-4o Analyzer",
  "provider": "openai",
  "version": "gpt-4o-2025",
  "capabilities": ["create_task","update_task","read_state"],
  "cost_center": "analysis",
  "metadata": {"model_id":"gpt-4o","team":"data"}
}')
echo "Agent 2: $AGENT2"
A2_ID=$(echo $AGENT2 | grep -o '"agent_id":"[^"]*"' | cut -d'"' -f4)

AGENT3=$(curl -s -X POST "$KERNEL/v1/agents" $H -d '{
  "name": "Local Executor",
  "provider": "local",
  "version": "1.2.0",
  "capabilities": ["complete_task","archive_entity","propose_delta"],
  "cost_center": "ops",
  "metadata": {"runtime":"node","team":"infra"}
}')
echo "Agent 3: $AGENT3"
A3_ID=$(echo $AGENT3 | grep -o '"agent_id":"[^"]*"' | cut -d'"' -f4)

AGENT4=$(curl -s -X POST "$KERNEL/v1/agents" $H -d '{
  "name": "Custom Governance Bot",
  "provider": "custom",
  "version": "0.9.1",
  "capabilities": ["propose_delta","create_task","read_state"],
  "cost_center": "governance",
  "metadata": {"engine":"rules-v2","team":"compliance"}
}')
echo "Agent 4: $AGENT4"
A4_ID=$(echo $AGENT4 | grep -o '"agent_id":"[^"]*"' | cut -d'"' -f4)

echo ""
echo "=== Creating Policy Rules ==="

curl -s -X POST "$KERNEL/v1/policies" $H -d '{
  "rules": [
    {
      "action": "create_task",
      "effect": "ALLOW",
      "conditions": [{"field":"agent.provider","operator":"eq","value":"claude"}],
      "priority": 100,
      "enabled": true
    },
    {
      "action": "propose_delta",
      "effect": "ALLOW",
      "conditions": [],
      "priority": 90,
      "enabled": true
    },
    {
      "action": "archive_entity",
      "effect": "REQUIRE_HUMAN",
      "conditions": [],
      "priority": 80,
      "enabled": true
    },
    {
      "action": "complete_task",
      "effect": "ALLOW",
      "conditions": [{"field":"mode","operator":"in","value":["BUILD","COMPOUND","SCALE"]}],
      "priority": 70,
      "enabled": true
    },
    {
      "action": "update_task",
      "effect": "DENY",
      "conditions": [{"field":"mode","operator":"eq","value":"RECOVER"}],
      "priority": 110,
      "enabled": true
    }
  ]
}'
echo ""

echo ""
echo "=== Creating Entities ==="

# We need to check entity-store create route — let's use the state routes
# Entities are created via delta append with entity_id, or directly
# Let me check if there's a direct entity create endpoint
# The state route only queries. Entities are created through delta/append.
# Let's use delta/append to create entities implicitly.

echo "=== Appending Deltas (creates entities + hash chain) ==="

# Delta 1: Create a task entity
D1=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A1_ID\",\"source\":\"claude\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Implement hash chain verification\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"open\"},{\"op\":\"add\",\"path\":\"/priority\",\"value\":\"high\"},{\"op\":\"add\",\"path\":\"/assignee\",\"value\":\"Claude Opus\"}],
  \"meta\": {\"reason\":\"Sprint planning — core infrastructure task\"}
}")
echo "Delta 1: $D1"
D1_HASH=$(echo $D1 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 2: Create another task
D2=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A2_ID\",\"source\":\"openai\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Analyze delta throughput metrics\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"in_progress\"},{\"op\":\"add\",\"path\":\"/priority\",\"value\":\"medium\"},{\"op\":\"add\",\"path\":\"/category\",\"value\":\"analytics\"}],
  \"hash_prev\": \"$D1_HASH\",
  \"meta\": {\"reason\":\"Performance analysis sprint\"}
}")
echo "Delta 2: $D2"
D2_HASH=$(echo $D2 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 3: Update first task
D3=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A1_ID\",\"source\":\"claude\"},
  \"patch\": [{\"op\":\"replace\",\"path\":\"/status\",\"value\":\"in_progress\"},{\"op\":\"add\",\"path\":\"/started_at\",\"value\":\"2026-02-22T10:00:00Z\"}],
  \"hash_prev\": \"$D2_HASH\",
  \"meta\": {\"reason\":\"Started implementation\"}
}")
echo "Delta 3: $D3"
D3_HASH=$(echo $D3 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 4: Governance action
D4=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A4_ID\",\"source\":\"custom\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Policy audit — Q1 compliance review\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"open\"},{\"op\":\"add\",\"path\":\"/type\",\"value\":\"governance\"},{\"op\":\"add\",\"path\":\"/urgency\",\"value\":\"critical\"}],
  \"hash_prev\": \"$D3_HASH\",
  \"meta\": {\"reason\":\"Quarterly compliance requirement\"}
}")
echo "Delta 4: $D4"
D4_HASH=$(echo $D4 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 5: Local executor completes a task
D5=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A3_ID\",\"source\":\"local\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Deploy Redis cluster config\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"completed\"},{\"op\":\"add\",\"path\":\"/completed_at\",\"value\":\"2026-02-22T14:30:00Z\"}],
  \"hash_prev\": \"$D4_HASH\",
  \"meta\": {\"reason\":\"Infrastructure deployment\"}
}")
echo "Delta 5: $D5"
D5_HASH=$(echo $D5 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 6: Another update
D6=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A2_ID\",\"source\":\"openai\"},
  \"patch\": [{\"op\":\"replace\",\"path\":\"/status\",\"value\":\"completed\"},{\"op\":\"add\",\"path\":\"/result\",\"value\":\"Throughput baseline: 1200 ops/sec\"},{\"op\":\"add\",\"path\":\"/completed_at\",\"value\":\"2026-02-22T16:00:00Z\"}],
  \"hash_prev\": \"$D5_HASH\",
  \"meta\": {\"reason\":\"Analysis complete\"}
}")
echo "Delta 6: $D6"
D6_HASH=$(echo $D6 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 7: Claude creates entity
D7=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"agent\",\"id\":\"$A1_ID\",\"source\":\"claude\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Implement snapshot pruning\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"open\"},{\"op\":\"add\",\"path\":\"/priority\",\"value\":\"low\"},{\"op\":\"add\",\"path\":\"/estimated_hours\",\"value\":4}],
  \"hash_prev\": \"$D6_HASH\",
  \"meta\": {\"reason\":\"Backlog grooming\"}
}")
echo "Delta 7: $D7"
D7_HASH=$(echo $D7 | grep -o '"hash":"[^"]*"' | head -1 | cut -d'"' -f4)

# Delta 8
D8=$(curl -s -X POST "$KERNEL/v1/delta/append" $H -d "{
  \"author\": {\"type\":\"human\",\"id\":\"bruke\",\"source\":\"dashboard\"},
  \"patch\": [{\"op\":\"add\",\"path\":\"/title\",\"value\":\"Review governance policies\"},{\"op\":\"add\",\"path\":\"/status\",\"value\":\"in_progress\"},{\"op\":\"add\",\"path\":\"/reviewer\",\"value\":\"bruke\"}],
  \"hash_prev\": \"$D7_HASH\",
  \"meta\": {\"reason\":\"Manual review initiated from dashboard\"}
}")
echo "Delta 8: $D8"

echo ""
echo "=== Creating Approvals ==="

# Create pending approvals
curl -s -X POST "$KERNEL/v1/approvals" $H -d "{
  \"action\": \"archive_entity\",
  \"agent_id\": \"$A3_ID\",
  \"entity_id\": \"entity-old-config\",
  \"reason\": \"Archiving deprecated config entity — requested by Local Executor\",
  \"expires_in_ms\": 86400000
}" 2>&1
echo ""

curl -s -X POST "$KERNEL/v1/approvals" $H -d "{
  \"action\": \"propose_delta\",
  \"agent_id\": \"$A4_ID\",
  \"entity_id\": \"entity-governance\",
  \"reason\": \"Governance bot wants to modify compliance rules — requires human sign-off\",
  \"expires_in_ms\": 172800000
}" 2>&1
echo ""

curl -s -X POST "$KERNEL/v1/approvals" $H -d "{
  \"action\": \"complete_task\",
  \"agent_id\": \"$A1_ID\",
  \"entity_id\": \"entity-critical-task\",
  \"reason\": \"Claude wants to mark critical infrastructure task as complete\",
  \"expires_in_ms\": 43200000
}" 2>&1
echo ""

echo ""
echo "=== Creating Webhooks ==="

curl -s -X POST "$GW/v1/webhooks" -H "Content-Type: application/json" -H "x-tenant-db: $DB" -d '{
  "url": "https://hooks.slack.com/services/T00000/B00000/XXXX",
  "events": ["action.submitted","action.completed","action.denied"],
  "secret": "whsec_demo_slack_secret"
}' 2>&1
echo ""

curl -s -X POST "$GW/v1/webhooks" -H "Content-Type: application/json" -H "x-tenant-db: $DB" -d '{
  "url": "https://api.pagerduty.com/webhooks/aegis",
  "events": ["approval.requested","approval.decided"],
  "secret": "whsec_demo_pagerduty"
}' 2>&1
echo ""

curl -s -X POST "$GW/v1/webhooks" -H "Content-Type: application/json" -H "x-tenant-db: $DB" -d '{
  "url": "https://internal.preatlas.dev/audit-sink",
  "events": ["action.submitted","action.completed","action.denied","approval.requested","approval.decided","policy.updated"]
}' 2>&1
echo ""

echo ""
echo "=== Verifying Hash Chain ==="
curl -s "$KERNEL/v1/delta/verify" -H "x-tenant-db: $DB" 2>&1
echo ""

echo ""
echo "=== Done! Demo data seeded. ==="
echo "Tenants: 2, Agents: 4, Deltas: 8, Policies: 5 rules, Approvals: 3, Webhooks: 3"
