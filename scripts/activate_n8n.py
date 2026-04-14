"""Activate remaining n8n scheduled workflows."""
import json, urllib.request

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGVlZjQxMC0yZDJjLTRmNGItOWM0OS1hODA2MzhlZTEwNDkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjVhODZiN2MtYTBhMC00ZjMyLWJkZTQtMzI1N2UwNzAyOGQ5IiwiaWF0IjoxNzc0ODkyMTM3LCJleHAiOjE3Nzc0MzUyMDB9.Yejuah8A-lZ8WhQo5AW4LnFZn7bySP8HNJSbPoegrS0"
BASE = "http://localhost:5678/api/v1"
ACTIVATE = ["M95HcMisHQ9Wt5Od", "yes7s9al6eUDKcn2", "JxgCOURB4vCRJRq1", "uEVhJCJK8VZXwIpe"]

for wid in ACTIVATE:
    req = urllib.request.Request(f"{BASE}/workflows/{wid}", headers={"X-N8N-API-KEY": KEY})
    with urllib.request.urlopen(req) as r:
        wf = json.loads(r.read())
    name = wf.get("name", "?").encode("ascii", "replace").decode()
    # Only keep fields n8n expects for PUT
    payload = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
               "settings": wf.get("settings", {}), "active": True, "staticData": wf.get("staticData")}
    data = json.dumps(payload).encode()
    req2 = urllib.request.Request(f"{BASE}/workflows/{wid}", data=data, method="PUT",
                                  headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req2) as r2:
            resp = json.loads(r2.read())
        print(f"{name:40s} -> active={resp.get('active')}")
    except Exception as e:
        err_body = e.read().decode("utf-8", "replace") if hasattr(e, "read") else str(e)
        print(f"{name:40s} -> ERROR: {err_body[:200]}")
