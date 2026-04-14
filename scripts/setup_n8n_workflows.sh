#!/bin/bash
# setup_n8n_workflows.sh — Create all 12 Pre Atlas n8n workflows
# Usage: bash scripts/setup_n8n_workflows.sh

N8N="http://localhost:5678/api/v1"
KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
BASE="C:\\Users\\bruke\\Pre Atlas"
CS="$BASE\\services\\cognitive-sensor"

created=0
failed=0
ids=()

create_workflow() {
    local name="$1"
    local json="$2"
    local resp
    resp=$(curl -s -X POST "$N8N/workflows" \
        -H "X-N8N-API-KEY: $KEY" \
        -H "Content-Type: application/json" \
        -d "$json")
    local id=$(echo "$resp" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -n "$id" ]; then
        echo "[OK] $name (id: $id)"
        ids+=("$id")
        ((created++))
    else
        echo "[FAIL] $name — $resp"
        ((failed++))
    fi
}

activate_workflow() {
    local id="$1"
    curl -s -X POST "$N8N/workflows/$id/activate" \
        -H "X-N8N-API-KEY: $KEY" > /dev/null 2>&1
}

echo ""
echo "=== Pre Atlas n8n Workflow Setup ==="
echo "Target: $N8N"
echo ""

# 1. Morning Refresh
create_workflow "01 — Morning Refresh" '{
  "name": "01 — Morning Refresh",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 8 * * *"}]}}},
    {"id":"n1","name":"Run Daily Pipeline","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python atlas_cli.py daily"}},
    {"id":"n2","name":"Trigger Delta Daemon","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[750,300],"parameters":{"url":"http://localhost:3001/api/daemon/run","method":"POST","options":{"timeout":30000}}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Daily Pipeline","type":"main","index":0}]]},"Run Daily Pipeline":{"main":[[{"node":"Trigger Delta Daemon","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 2. Service Health Check
create_workflow "02 — Service Health Check" '{
  "name": "02 — Service Health Check",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"*/15 * * * *"}]}}},
    {"id":"n1","name":"Check Delta","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,200],"parameters":{"url":"http://localhost:3001/api/health","method":"GET","options":{"timeout":5000,"allowUnauthorizedCerts":true}}},
    {"id":"n2","name":"Check Mirofish","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,350],"parameters":{"url":"http://localhost:3003/api/v1/health","method":"GET","options":{"timeout":5000,"allowUnauthorizedCerts":true}}},
    {"id":"n3","name":"Check OpenClaw","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,500],"parameters":{"url":"http://localhost:3004/api/v1/health","method":"GET","options":{"timeout":5000,"allowUnauthorizedCerts":true}}},
    {"id":"n4","name":"Check Orchestrator","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,650],"parameters":{"url":"http://localhost:3005/api/v1/health","method":"GET","options":{"timeout":5000,"allowUnauthorizedCerts":true}}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Check Delta","type":"main","index":0},{"node":"Check Mirofish","type":"main","index":0},{"node":"Check OpenClaw","type":"main","index":0},{"node":"Check Orchestrator","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 3. Git Commit Digest
create_workflow "03 — Git Commit Digest" '{
  "name": "03 — Git Commit Digest",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 7 * * *"}]}}},
    {"id":"n1","name":"Git Log","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\" && git log --oneline --since=\"1 day ago\" --all 2>&1 || echo No commits in last 24h"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Git Log","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 4. Test Runner
create_workflow "04 — Test Runner" '{
  "name": "04 — Test Runner",
  "nodes": [
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"test-runner","httpMethod":"POST"},"webhookId":"test-runner"},
    {"id":"n1","name":"Delta Tests","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,200],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\delta-kernel\" && npm run test 2>&1 && echo PASS || echo FAIL"}},
    {"id":"n2","name":"OpenClaw Tests","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,350],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\openclaw\" && python -m pytest --tb=no -q 2>&1 && echo PASS || echo FAIL"}},
    {"id":"n3","name":"Aegis Tests","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,500],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\aegis-fabric\" && npm run test 2>&1 && echo PASS || echo FAIL"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Delta Tests","type":"main","index":0},{"node":"OpenClaw Tests","type":"main","index":0},{"node":"Aegis Tests","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 5. Conversation Intake
create_workflow "05 — Conversation Intake" '{
  "name": "05 — Conversation Intake",
  "nodes": [
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"conversation-intake","httpMethod":"POST"},"webhookId":"conversation-intake"},
    {"id":"n1","name":"Excavate","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[450,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python agent_excavator.py"}},
    {"id":"n2","name":"Deduplicate","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[650,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python agent_deduplicator.py"}},
    {"id":"n3","name":"Classify","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[850,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python agent_classifier.py"}},
    {"id":"n4","name":"Orchestrate","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[1050,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python agent_orchestrator.py"}},
    {"id":"n5","name":"Report","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[1250,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python agent_reporter.py"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Excavate","type":"main","index":0}]]},"Excavate":{"main":[[{"node":"Deduplicate","type":"main","index":0}]]},"Deduplicate":{"main":[[{"node":"Classify","type":"main","index":0}]]},"Classify":{"main":[[{"node":"Orchestrate","type":"main","index":0}]]},"Orchestrate":{"main":[[{"node":"Report","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 6. Weekly Governor
create_workflow "06 — Weekly Governor" '{
  "name": "06 — Weekly Governor",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 9 * * 0"}]}}},
    {"id":"n1","name":"Run Weekly","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python atlas_cli.py weekly"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Weekly","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 7. Book Pipeline
create_workflow "07 — Book Pipeline" '{
  "name": "07 — Book Pipeline",
  "nodes": [
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"book-pipeline","httpMethod":"POST"},"webhookId":"book-pipeline"},
    {"id":"n1","name":"Build PDF","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\data\" && python build_book_pdf.py"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Build PDF","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 8. Idea Triage
create_workflow "08 — Idea Triage" '{
  "name": "08 — Idea Triage",
  "nodes": [
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"idea-triage","httpMethod":"POST"},"webhookId":"idea-triage"},
    {"id":"n1","name":"Run Backlog","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"cd \"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\" && python atlas_cli.py backlog"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Run Backlog","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 9. Mosaic Heartbeat
create_workflow "09 — Mosaic Heartbeat" '{
  "name": "09 — Mosaic Heartbeat",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"*/5 * * * *"}]}}},
    {"id":"n1","name":"Check Delta","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,150],"parameters":{"url":"http://localhost:3001/api/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n2","name":"Check Aegis","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,300],"parameters":{"url":"http://localhost:3002/api/v1/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n3","name":"Check Mirofish","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,450],"parameters":{"url":"http://localhost:3003/api/v1/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n4","name":"Check OpenClaw","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,600],"parameters":{"url":"http://localhost:3004/api/v1/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n5","name":"Check Orchestrator","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,750],"parameters":{"url":"http://localhost:3005/api/v1/health","method":"GET","options":{"timeout":5000}}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Check Delta","type":"main","index":0},{"node":"Check Aegis","type":"main","index":0},{"node":"Check Mirofish","type":"main","index":0},{"node":"Check OpenClaw","type":"main","index":0},{"node":"Check Orchestrator","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 10. Festival Progress Sync
create_workflow "10 — Festival Progress Sync" '{
  "name": "10 — Festival Progress Sync",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"30 8 * * *"}]}}},
    {"id":"n1","name":"Fetch Progress","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"wsl -d Ubuntu -- bash -c \"cd /root/festival-project && fest progress 2>&1\""}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Fetch Progress","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 11. Webhook Relay
create_workflow "11 — Webhook Relay" '{
  "name": "11 — Webhook Relay",
  "nodes": [
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"relay","httpMethod":"POST"},"webhookId":"relay"},
    {"id":"n1","name":"Forward","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,300],"parameters":{"url":"={{ $json.body.target_url }}","method":"POST","sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify($json.body.payload) }}","options":{"timeout":30000}}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Forward","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 12. Scheduled Backup
create_workflow "12 — Scheduled Backup" '{
  "name": "12 — Scheduled Backup",
  "nodes": [
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 2 * * *"}]}}},
    {"id":"n1","name":"Run Backup","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[500,300],"parameters":{"command":"powershell -Command \"$d=Get-Date -Format yyyy-MM-dd; $dir=\\\"C:\\Users\\bruke\\Pre Atlas\\backups\\$d\\\"; New-Item -ItemType Directory -Force -Path $dir | Out-Null; @(\\\"C:\\Users\\bruke\\.n8n\\database.sqlite\\\",\\\"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\\cognitive_state.json\\\",\\\"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\\governance_state.json\\\",\\\"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\\idea_registry.json\\\",\\\"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\\atlas_state.json\\\",\\\"C:\\Users\\bruke\\Pre Atlas\\services\\cognitive-sensor\\daily_payload.json\\\") | ForEach-Object { if(Test-Path $_){Copy-Item $_ -Destination $dir -Force} }; Get-ChildItem \\\"C:\\Users\\bruke\\Pre Atlas\\backups\\\" -Directory | Where-Object {$_.CreationTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Recurse -Force; Write-Output \\\"Backup complete: $dir\\\"\""}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Backup","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

echo ""
echo "=== Setup Complete ==="
echo "Created: $created / 12"
if [ "$failed" -gt 0 ]; then echo "Failed: $failed"; fi

# Activate scheduled workflows (1,2,3,6,9,10,12)
echo ""
echo "Activating scheduled workflows..."
for i in 0 1 2 5 8 9 11; do
    if [ -n "${ids[$i]}" ]; then
        activate_workflow "${ids[$i]}"
        echo "  Activated: ${ids[$i]}"
    fi
done

echo ""
echo "Scheduled (auto): Morning Refresh, Health Check, Git Digest, Weekly Governor, Heartbeat, Festival Sync, Backup"
echo "On-demand (webhook): Test Runner, Conversation Intake, Book Pipeline, Idea Triage, Webhook Relay"
echo ""
echo "View at: http://localhost:5678"
