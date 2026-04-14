"""Add aegis governance node to Morning Refresh workflow."""
import json, urllib.request

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
BASE = "http://localhost:5678/api/v1"
WF_ID = "y7Ko12Hbw9rXftcn"

# Read tenant key
with open("C:/Users/bruke/Pre Atlas/.aegis-tenant-key") as f:
    TENANT_KEY = f.read().strip()

CS = "C:\\\\Users\\\\bruke\\\\Pre Atlas\\\\services\\\\cognitive-sensor"

# Get current workflow
req = urllib.request.Request(f"{BASE}/workflows/{WF_ID}", headers={"X-N8N-API-KEY": KEY})
with urllib.request.urlopen(req) as r:
    wf = json.loads(r.read())

# Aegis governance code node
aegis_code = f"""
const {{ execSync }} = require('child_process');
const fs = require('fs');
const path = require('path');

const CS = '{CS}';
const TENANT_KEY = '{TENANT_KEY}';

// Read daily payload to get mode info
let daily_payload;
try {{
  daily_payload = JSON.parse(fs.readFileSync(path.join(CS, 'daily_payload.json'), 'utf8'));
}} catch(e) {{
  return [{{json:{{error:'Failed to read daily_payload.json', skip_aegis: true}}}}];
}}

// Read previous mode from delta-kernel state
let old_mode = 'BUILD';
try {{
  const stateResp = execSync('curl -s http://localhost:3001/api/state', {{timeout:5000, encoding:'utf8'}});
  const state = JSON.parse(stateResp);
  old_mode = state.mode || 'BUILD';
}} catch(e) {{
  // Default to BUILD if can't reach delta-kernel
}}

const new_mode = daily_payload.mode || 'BUILD';

// Build aegis action payload
const actionPayload = {{
  agent_id: 'cognitive-sensor',
  action: 'route_decision',
  params: {{
    new_mode,
    old_mode,
    closure_ratio: daily_payload.closure_ratio || 0,
    open_loops: daily_payload.open_loop_count || 0,
    reason: daily_payload.primary_action || 'Daily refresh mode routing'
  }}
}};

// POST to aegis
try {{
  const payload = JSON.stringify(actionPayload).replace(/'/g, "'\\\\''");
  const resp = execSync(
    `curl -s -X POST http://localhost:3002/api/v1/agent/action -H "Content-Type: application/json" -H "X-API-Key: ${{TENANT_KEY}}" -d '${{payload}}'`,
    {{timeout:15000, encoding:'utf8'}}
  );
  const result = JSON.parse(resp);
  return [{{json:{{
    aegis_status: result.status,
    new_mode,
    old_mode,
    mode_changed: new_mode !== old_mode,
    approval_id: result.approval ? result.approval.approval_id : null,
    policy_effect: result.policy_decision ? result.policy_decision.effect : null
  }}}}];
}} catch(e) {{
  return [{{json:{{error:'Aegis call failed: ' + e.message, new_mode, old_mode}}}}];
}}
""".strip()

# Build the 5-node workflow
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
        "parameters": {"jsCode": f'const {{ execSync }} = require("child_process");\nconst out = execSync("cd \\"{CS}\\" && python atlas_cli.py daily", {{timeout:120000, encoding:"utf8"}});\nreturn [{{json:{{output:out.slice(-500),status:"ok"}}}}];'}
    },
    {
        "id": "n2", "name": "Push to Delta-Kernel",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [750, 300],
        "parameters": {"jsCode": wf["nodes"][2]["parameters"]["jsCode"] if len(wf["nodes"]) > 2 else "return [{json:{skip:true}}];"}  # Keep existing ingest code
    },
    {
        "id": "n3", "name": "Route via Aegis",
        "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [1000, 300],
        "parameters": {"jsCode": aegis_code}
    },
    {
        "id": "n4", "name": "Trigger Delta Daemon",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": [1250, 300],
        "parameters": {"url": "http://localhost:3001/api/daemon/run", "method": "POST", "options": {"timeout": 30000}}
    }
]

wf["connections"] = {
    "Schedule": {"main": [[{"node": "Run Daily Pipeline", "type": "main", "index": 0}]]},
    "Run Daily Pipeline": {"main": [[{"node": "Push to Delta-Kernel", "type": "main", "index": 0}]]},
    "Push to Delta-Kernel": {"main": [[{"node": "Route via Aegis", "type": "main", "index": 0}]]},
    "Route via Aegis": {"main": [[{"node": "Trigger Delta Daemon", "type": "main", "index": 0}]]}
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
print("Flow: Schedule -> Run Daily -> Push to Delta-Kernel -> Route via Aegis -> Trigger Daemon")
