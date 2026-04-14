#!/bin/bash
# setup_n8n_workflows_v2.sh — Create 12 Pre Atlas n8n workflows using Code nodes
# The executeCommand node is not available, so we use Code nodes with child_process

N8N="http://localhost:5678/api/v1"
KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"

created=0
failed=0

create_workflow() {
    local name="$1"
    local json="$2"
    local resp
    resp=$(curl -s -X POST "$N8N/workflows" \
        -H "X-N8N-API-KEY: $KEY" \
        -H "Content-Type: application/json" \
        -d "$json")
    local id=$(echo "$resp" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    if [ -n "$id" ] && [ "$id" != "" ]; then
        echo "[OK] $name (id: $id)"
        # Try to activate scheduled workflows
        curl -s -X PUT "$N8N/workflows/$id" \
            -H "X-N8N-API-KEY: $KEY" \
            -H "Content-Type: application/json" \
            -d "$(echo "$resp" | python -c "import sys,json; d=json.load(sys.stdin); d['active']=True; json.dump(d,sys.stdout)" 2>/dev/null)" > /dev/null 2>&1
        ((created++))
    else
        echo "[FAIL] $name"
        echo "$resp" | head -c 200
        echo ""
        ((failed++))
    fi
}

echo ""
echo "=== Pre Atlas n8n Workflow Setup v2 (Code nodes) ==="
echo ""

# Helper: Code node that runs a shell command
# n8n Code nodes use JavaScript. We use execSync from child_process.
# The jsCode field contains the actual JS to run.

# 1. Morning Refresh
create_workflow "01 — Morning Refresh" '{
  "name":"01 — Morning Refresh",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 8 * * *"}]}}},
    {"id":"n1","name":"Run Daily Pipeline","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst out = execSync(\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\" && python atlas_cli.py daily\", {timeout:120000, encoding:\"utf8\"});\nreturn [{json:{output:out,status:\"ok\"}}];"}},
    {"id":"n2","name":"Trigger Delta Daemon","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[750,300],"parameters":{"url":"http://localhost:3001/api/daemon/run","method":"POST","options":{"timeout":30000}}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Daily Pipeline","type":"main","index":0}]]},"Run Daily Pipeline":{"main":[[{"node":"Trigger Delta Daemon","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 2. Service Health Check
create_workflow "02 — Service Health Check" '{
  "name":"02 — Service Health Check",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"*/15 * * * *"}]}}},
    {"id":"n1","name":"Check Delta","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,200],"parameters":{"url":"http://localhost:3001/api/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n2","name":"Check Mirofish","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,350],"parameters":{"url":"http://localhost:3003/api/v1/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n3","name":"Check OpenClaw","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,500],"parameters":{"url":"http://localhost:3004/api/v1/health","method":"GET","options":{"timeout":5000}}},
    {"id":"n4","name":"Check Orchestrator","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,650],"parameters":{"url":"http://localhost:3005/api/v1/health","method":"GET","options":{"timeout":5000}}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Check Delta","type":"main","index":0},{"node":"Check Mirofish","type":"main","index":0},{"node":"Check OpenClaw","type":"main","index":0},{"node":"Check Orchestrator","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 3. Git Commit Digest
create_workflow "03 — Git Commit Digest" '{
  "name":"03 — Git Commit Digest",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 7 * * *"}]}}},
    {"id":"n1","name":"Git Log","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\ntry {\n  const out = execSync(\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\" && git log --oneline --since=\\\"1 day ago\\\" --all\", {timeout:30000, encoding:\"utf8\"});\n  return [{json:{commits:out.trim().split(\"\\n\"),count:out.trim().split(\"\\n\").length}}];\n} catch(e) {\n  return [{json:{commits:[],count:0,note:\"No commits in last 24h\"}}];\n}"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Git Log","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 4. Test Runner
create_workflow "04 — Test Runner" '{
  "name":"04 — Test Runner",
  "nodes":[
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"test-runner","httpMethod":"POST"},"webhookId":"test-runner"},
    {"id":"n1","name":"Run Tests","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst results = {};\nconst services = [\n  {name:\"delta-kernel\",cmd:\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\delta-kernel\\\" && npm run test 2>&1\"},\n  {name:\"openclaw\",cmd:\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\openclaw\\\" && python -m pytest --tb=no -q 2>&1\"},\n  {name:\"aegis-fabric\",cmd:\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\aegis-fabric\\\" && npm run test 2>&1\"}\n];\nfor (const s of services) {\n  try {\n    const out = execSync(s.cmd, {timeout:120000, encoding:\"utf8\"});\n    results[s.name] = {status:\"PASS\",output:out.slice(-500)};\n  } catch(e) {\n    results[s.name] = {status:\"FAIL\",output:e.stdout ? e.stdout.slice(-500) : e.message};\n  }\n}\nreturn [{json:results}];"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Run Tests","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 5. Conversation Intake
create_workflow "05 — Conversation Intake" '{
  "name":"05 — Conversation Intake",
  "nodes":[
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"conversation-intake","httpMethod":"POST"},"webhookId":"conversation-intake"},
    {"id":"n1","name":"Run Idea Pipeline","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst cs = \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\";\nconst steps = [\"agent_excavator.py\",\"agent_deduplicator.py\",\"agent_classifier.py\",\"agent_orchestrator.py\",\"agent_reporter.py\"];\nconst log = [];\nfor (const s of steps) {\n  try {\n    execSync(`cd \"${cs}\" && python ${s}`, {timeout:180000, encoding:\"utf8\"});\n    log.push({step:s,status:\"ok\"});\n  } catch(e) {\n    log.push({step:s,status:\"fail\",error:e.message.slice(0,200)});\n  }\n}\nreturn [{json:{pipeline:\"complete\",steps:log}}];"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Run Idea Pipeline","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 6. Weekly Governor
create_workflow "06 — Weekly Governor" '{
  "name":"06 — Weekly Governor",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 9 * * 0"}]}}},
    {"id":"n1","name":"Run Weekly","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst out = execSync(\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\" && python atlas_cli.py weekly\", {timeout:300000, encoding:\"utf8\"});\nreturn [{json:{output:out,status:\"ok\"}}];"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Weekly","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 7. Book Pipeline
create_workflow "07 — Book Pipeline" '{
  "name":"07 — Book Pipeline",
  "nodes":[
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"book-pipeline","httpMethod":"POST"},"webhookId":"book-pipeline"},
    {"id":"n1","name":"Build PDF","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst out = execSync(\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\data\\\" && python build_book_pdf.py\", {timeout:120000, encoding:\"utf8\"});\nreturn [{json:{output:out,status:\"ok\"}}];"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Build PDF","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 8. Idea Triage
create_workflow "08 — Idea Triage" '{
  "name":"08 — Idea Triage",
  "nodes":[
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"idea-triage","httpMethod":"POST"},"webhookId":"idea-triage"},
    {"id":"n1","name":"Run Backlog","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst out = execSync(\"cd \\\"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\" && python atlas_cli.py backlog\", {timeout:180000, encoding:\"utf8\"});\nreturn [{json:{output:out,status:\"ok\"}}];"}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Run Backlog","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 9. Mosaic Heartbeat
create_workflow "09 — Mosaic Heartbeat" '{
  "name":"09 — Mosaic Heartbeat",
  "nodes":[
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
  "name":"10 — Festival Progress Sync",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"30 8 * * *"}]}}},
    {"id":"n1","name":"Fetch Progress","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\ntry {\n  const out = execSync(\"wsl -d Ubuntu -- bash -c \\\"cd /root/festival-project && fest progress 2>&1\\\"\", {timeout:30000, encoding:\"utf8\"});\n  return [{json:{progress:out,status:\"ok\"}}];\n} catch(e) {\n  return [{json:{progress:\"\",status:\"fail\",error:e.message.slice(0,200)}}];\n}"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Fetch Progress","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 11. Webhook Relay
create_workflow "11 — Webhook Relay" '{
  "name":"11 — Webhook Relay",
  "nodes":[
    {"id":"t1","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[250,300],"parameters":{"path":"relay","httpMethod":"POST"},"webhookId":"relay"},
    {"id":"n1","name":"Forward","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[500,300],"parameters":{"url":"={{ $json.body.target_url }}","method":"POST","sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify($json.body.payload) }}","options":{"timeout":30000}}}
  ],
  "connections":{"Webhook":{"main":[[{"node":"Forward","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

# 12. Scheduled Backup
create_workflow "12 — Scheduled Backup" '{
  "name":"12 — Scheduled Backup",
  "nodes":[
    {"id":"t1","name":"Schedule","type":"n8n-nodes-base.scheduleTrigger","typeVersion":1.2,"position":[250,300],"parameters":{"rule":{"interval":[{"field":"cronExpression","expression":"0 2 * * *"}]}}},
    {"id":"n1","name":"Run Backup","type":"n8n-nodes-base.code","typeVersion":2,"position":[500,300],"parameters":{"jsCode":"const { execSync } = require(\"child_process\");\nconst fs = require(\"fs\");\nconst path = require(\"path\");\nconst date = new Date().toISOString().slice(0,10);\nconst dir = `C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\backups\\\\${date}`;\nfs.mkdirSync(dir, {recursive:true});\nconst files = [\n  \"C:\\\\Users\\\\bruke\\\\.n8n\\\\database.sqlite\",\n  \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\\cognitive_state.json\",\n  \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\\governance_state.json\",\n  \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\\idea_registry.json\",\n  \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\\atlas_state.json\",\n  \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor\\\\daily_payload.json\"\n];\nlet copied = 0;\nfor (const f of files) {\n  try { fs.copyFileSync(f, path.join(dir, path.basename(f))); copied++; } catch(e) {}\n}\n// Clean old backups\nconst backupRoot = \"C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\backups\";\nfor (const d of fs.readdirSync(backupRoot)) {\n  const p = path.join(backupRoot, d);\n  const stat = fs.statSync(p);\n  if (stat.isDirectory() && (Date.now() - stat.mtimeMs) > 7*24*60*60*1000) {\n    fs.rmSync(p, {recursive:true, force:true});\n  }\n}\nreturn [{json:{date, dir, copied, status:\"ok\"}}];"}}
  ],
  "connections":{"Schedule":{"main":[[{"node":"Run Backup","type":"main","index":0}]]}},
  "settings":{"executionOrder":"v1"}
}'

echo ""
echo "=== Setup Complete ==="
echo "Created: $created / 12"
if [ "$failed" -gt 0 ]; then echo "Failed: $failed"; fi
echo ""
echo "View at: http://localhost:5678"
