"""Enable MCP access for all n8n workflows."""
import json, urllib.request

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
BASE = "http://localhost:5678/api/v1"

# Get all workflows
req = urllib.request.Request(f"{BASE}/workflows", headers={"X-N8N-API-KEY": KEY})
with urllib.request.urlopen(req) as r:
    workflows = json.loads(r.read())["data"]

for w in workflows:
    wid = w["id"]
    # Get full workflow
    req = urllib.request.Request(f"{BASE}/workflows/{wid}", headers={"X-N8N-API-KEY": KEY})
    with urllib.request.urlopen(req) as r:
        wf = json.loads(r.read())

    if wf.get("settings", {}).get("availableInMCP"):
        safe = wf['name'][:40].encode('ascii','replace').decode()
        print(f"  SKIP  {safe:40s} (already MCP-enabled)")
        continue

    wf.setdefault("settings", {})["availableInMCP"] = True
    payload = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf["settings"]}
    data = json.dumps(payload).encode()
    req2 = urllib.request.Request(f"{BASE}/workflows/{wid}", data=data, method="PUT",
                                  headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req2) as r2:
        resp = json.loads(r2.read())
    mcp = resp.get("settings", {}).get("availableInMCP")
    safe = resp['name'][:40].encode('ascii','replace').decode()
    print(f"  OK    {safe:40s} MCP={mcp}")

print("\nDone. All workflows now visible to MCP.")
