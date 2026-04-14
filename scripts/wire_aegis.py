"""
wire_aegis.py — Idempotent setup of aegis tenant, agent, and governance policies.
Registers cognitive-sensor as an agent and creates mode transition policies.

Usage: python scripts/wire_aegis.py
Requires: aegis-fabric running on port 3002
"""
import json
import os
import urllib.request
import urllib.error

AEGIS = os.environ.get("AEGIS_URL", "http://localhost:3002")
ADMIN_KEY = os.environ.get("AEGIS_ADMIN_KEY", "aegis-admin-default-key")
TENANT_NAME = "pre-atlas"

def api(method, path, body=None, key=None):
    """Make an aegis API call."""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{AEGIS}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", "replace")
        try:
            return json.loads(body_text), e.code
        except json.JSONDecodeError:
            return {"error": body_text}, e.code
    except urllib.error.URLError as e:
        return {"error": str(e)}, 0


def main():
    print("=== Aegis Integration Setup ===\n")

    # Step 1: Check aegis is running
    resp, code = api("GET", "/health")
    if code == 0:
        print("[FAIL] Aegis not running at", AEGIS)
        print("Start it with: cd services/aegis-fabric && npm run api")
        return
    print(f"[OK] Aegis is running ({AEGIS})")

    # Step 2: Check if tenant exists
    resp, code = api("GET", "/api/v1/tenants", key=ADMIN_KEY)
    tenants = resp.get("tenants", [])
    tenant_key = None
    tenant_id = None

    for t in tenants:
        data = t.get("data", t)
        name = data.get("name") or t.get("name", "")
        tid = t.get("id") or data.get("id", "")
        if name == TENANT_NAME:
            tenant_id = tid
            print(f"[OK] Tenant '{TENANT_NAME}' exists (id: {str(tenant_id)[:16]}...)")
            break

    if not tenant_id:
        # Create tenant
        resp, code = api("POST", "/api/v1/tenants", {
            "name": TENANT_NAME,
            "tier": "ENTERPRISE",
            "mode": "BUILD",
            "isolation_model": "POOLED",
        }, key=ADMIN_KEY)
        if code in (200, 201):
            tenant_id = resp.get("tenant", {}).get("id") or resp.get("id")
            tenant_key = resp.get("apiKey") or resp.get("api_key")
            print(f"[OK] Created tenant '{TENANT_NAME}' (id: {tenant_id})")
            print(f"     API Key: {tenant_key}")
            # Save key for later use
            with open("C:/Users/bruke/Pre Atlas/.aegis-tenant-key", "w") as f:
                f.write(tenant_key)
            print(f"     Saved to .aegis-tenant-key")
        else:
            print(f"[FAIL] Could not create tenant: {resp}")
            return
    else:
        # Try to load saved key
        key_path = "C:/Users/bruke/Pre Atlas/.aegis-tenant-key"
        if os.path.exists(key_path):
            with open(key_path) as f:
                tenant_key = f.read().strip()
            print(f"[OK] Loaded tenant API key from .aegis-tenant-key")
        else:
            print("[WARN] Tenant exists but no saved API key found.")
            print("       You may need to create a new tenant or manually set the key.")
            print("       Set AEGIS_TENANT_KEY env var or recreate.")
            return

    # Step 3: Register cognitive-sensor agent (idempotent)
    resp, code = api("GET", "/api/v1/agents", key=tenant_key)
    agents = resp.get("agents", [])
    agent_exists = any(
        (a.get("data", a).get("name") == "cognitive-sensor")
        for a in agents
    )

    if agent_exists:
        print("[OK] Agent 'cognitive-sensor' already registered")
    else:
        resp, code = api("POST", "/api/v1/agents", {
            "name": "cognitive-sensor",
            "provider": "custom",
            "version": "1.0.0",
            "capabilities": ["route_decision", "propose_delta"],
            "cost_center": "cognitive-sensor",
            "metadata": {
                "description": "Behavioral analysis pipeline that computes operating mode",
                "source": "services/cognitive-sensor/atlas_cli.py"
            }
        }, key=tenant_key)
        if code in (200, 201):
            agent_id = resp.get("agentId") or resp.get("agent_id") or resp.get("id")
            print(f"[OK] Registered agent 'cognitive-sensor' (id: {agent_id})")
        else:
            print(f"[FAIL] Could not register agent: {resp}")
            return

    # Step 4: Create governance policies (idempotent)
    resp, code = api("GET", "/api/v1/policies", key=tenant_key)
    existing_rules = resp.get("rules", [])
    has_mode_change_policy = any(
        r.get("name") == "mode-transition-requires-approval"
        for r in existing_rules
    )
    has_routine_policy = any(
        r.get("name") == "routine-refresh-auto-allow"
        for r in existing_rules
    )

    if has_mode_change_policy and has_routine_policy:
        print("[OK] Governance policies already exist")
    else:
        rules = []
        if not has_routine_policy:
            rules.append({
                "name": "routine-refresh-auto-allow",
                "description": "Auto-allow when mode hasn't changed (routine refresh)",
                "conditions": [
                    {"field": "action", "op": "eq", "value": "route_decision"},
                    {"field": "params.new_mode", "op": "eq", "value": "{{params.old_mode}}"}
                ],
                "effect": "ALLOW",
                "priority": 10
            })
        if not has_mode_change_policy:
            rules.append({
                "name": "mode-transition-requires-approval",
                "description": "Mode transitions require human approval via dashboard",
                "conditions": [
                    {"field": "action", "op": "eq", "value": "route_decision"}
                ],
                "effect": "REQUIRE_HUMAN",
                "priority": 20
            })

        if rules:
            resp, code = api("POST", "/api/v1/policies", {"rules": rules}, key=tenant_key)
            if code in (200, 201):
                count = resp.get("count") or resp.get("created") or len(rules)
                print(f"[OK] Created {count} governance policies:")
                for r in rules:
                    print(f"     - {r['name']} (priority {r['priority']}, effect {r['effect']})")
            else:
                print(f"[FAIL] Could not create policies: {resp}")
                return

    print("\n=== Setup Complete ===")
    print(f"Tenant:  {TENANT_NAME} ({tenant_id})")
    print(f"Agent:   cognitive-sensor")
    print(f"Policies:")
    print(f"  1. routine-refresh-auto-allow (priority 10) -> ALLOW")
    print(f"  2. mode-transition-requires-approval (priority 20) -> REQUIRE_HUMAN")
    print(f"\nThe cognitive-sensor can now route mode decisions through aegis.")
    print(f"Mode changes will require human approval via the dashboard.")


if __name__ == "__main__":
    main()
