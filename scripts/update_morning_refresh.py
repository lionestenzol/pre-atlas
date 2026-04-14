"""Update n8n Morning Refresh workflow to push cognitive state to delta-kernel."""
import json, urllib.request

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
BASE = "http://localhost:5678/api/v1"
WF_ID = "y7Ko12Hbw9rXftcn"  # 01 — Morning Refresh

# Get current workflow
req = urllib.request.Request(f"{BASE}/workflows/{WF_ID}", headers={"X-N8N-API-KEY": KEY})
with urllib.request.urlopen(req) as r:
    wf = json.loads(r.read())

# New workflow definition with 4 nodes:
# Schedule -> Run Daily Pipeline -> Push to Delta-Kernel -> Trigger Delta Daemon
CS = "C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor"

ingest_code = """
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CS = 'C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor';
const run_id = new Date().toISOString().replace(/[:.]/g, '-') + '-cognitive';

// Read cognitive state and daily payload
let cognitive_state, daily_payload;
try {
  cognitive_state = JSON.parse(fs.readFileSync(path.join(CS, 'cognitive_state.json'), 'utf8'));
} catch(e) { return [{json:{error:'Failed to read cognitive_state.json: ' + e.message}}]; }

try {
  daily_payload = JSON.parse(fs.readFileSync(path.join(CS, 'daily_payload.json'), 'utf8'));
} catch(e) { return [{json:{error:'Failed to read daily_payload.json: ' + e.message}}]; }

// Build ingestion payload matching delta-kernel's expected shape
const payload = {
  run_id,
  cognitive: {
    state: cognitive_state.state || {},
    loops: cognitive_state.loops || [],
    drift: cognitive_state.drift || {},
    closure: cognitive_state.closure || { open: 0, closed: 0, ratio: 0 }
  },
  directive: {
    mode: daily_payload.mode || 'RECOVER',
    mode_source: daily_payload.mode_source || 'cognitive-sensor',
    build_allowed: daily_payload.build_allowed || false,
    primary_action: daily_payload.primary_action || '',
    open_loops: daily_payload.open_loops || [],
    open_loop_count: daily_payload.open_loop_count || 0,
    closure_ratio: daily_payload.closure_ratio || 0,
    risk: daily_payload.risk || 'MEDIUM',
    schema_version: daily_payload.schema_version || '1.0.0'
  }
};

// POST to delta-kernel with retries
let lastError = null;
for (let attempt = 0; attempt < 3; attempt++) {
  try {
    const resp = execSync(
      `curl -s -X POST http://localhost:3001/api/ingest/cognitive -H "Content-Type: application/json" -d '${JSON.stringify(payload).replace(/'/g, "'\\''")}'`,
      {timeout: 15000, encoding: 'utf8'}
    );
    const result = JSON.parse(resp);
    return [{json:{...result, run_id, attempt: attempt + 1}}];
  } catch(e) {
    lastError = e.message;
    if (attempt < 2) {
      // Exponential backoff: 1s, 2s
      execSync(`sleep ${Math.pow(2, attempt)}`, {timeout: 5000});
    }
  }
}
return [{json:{error: 'Failed after 3 attempts: ' + lastError, run_id}}];
"""

wf["nodes"] = [
    {
        "id": "t1", "name": "Schedule",
        "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
        "position": [250, 300],
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * *"}]}}
    },
    {
        "id": "n1", "name": "Run Daily Pipeline",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [500, 300],
        "parameters": {"jsCode": f'const {{ execSync }} = require("child_process");\nconst out = execSync("cd \\"{CS}\\" && python atlas_cli.py daily", {{timeout:120000, encoding:"utf8"}});\nreturn [{{json:{{output:out,status:"ok"}}}}];'}
    },
    {
        "id": "n2", "name": "Push to Delta-Kernel",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [750, 300],
        "parameters": {"jsCode": ingest_code.strip()}
    },
    {
        "id": "n3", "name": "Trigger Delta Daemon",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [1000, 300],
        "parameters": {"url": "http://localhost:3001/api/daemon/run", "method": "POST", "options": {"timeout": 30000}}
    }
]

wf["connections"] = {
    "Schedule": {"main": [[{"node": "Run Daily Pipeline", "type": "main", "index": 0}]]},
    "Run Daily Pipeline": {"main": [[{"node": "Push to Delta-Kernel", "type": "main", "index": 0}]]},
    "Push to Delta-Kernel": {"main": [[{"node": "Trigger Delta Daemon", "type": "main", "index": 0}]]}
}

# PUT the updated workflow
payload = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf.get("settings", {})}
data = json.dumps(payload).encode()
req2 = urllib.request.Request(f"{BASE}/workflows/{WF_ID}", data=data, method="PUT",
                              headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
with urllib.request.urlopen(req2) as r2:
    resp = json.loads(r2.read())

name = resp.get('name', '?').encode('ascii', 'replace').decode()
print(f"Updated: {name} (id: {resp.get('id')})")
print(f"Nodes: {len(resp.get('nodes', []))}")
print("Flow: Schedule -> Run Daily Pipeline -> Push to Delta-Kernel -> Trigger Delta Daemon")
