#!/usr/bin/env bash
# seed-mosaic.sh — Seed demo data into Mosaic Platform services.
# Run after `docker compose up -d` and all health checks pass.
set -euo pipefail

AEGIS_URL="${AEGIS_URL:-http://localhost:3002}"
AEGIS_KEY="${AEGIS_ADMIN_KEY:-change-me-to-a-real-key}"
ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:3005}"

echo "=== Mosaic Platform — Seeding Demo Data ==="
echo ""

# --- Aegis Fabric: Tenant + Agents + Policies ---
echo "[1/4] Seeding Aegis tenant..."
curl -s -X POST "$AEGIS_URL/api/v1/tenants" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $AEGIS_KEY" \
  -d '{"tenant_id": "mosaic-dev", "name": "Mosaic Development", "plan": "pro"}' \
  | head -c 200
echo ""

echo "[2/4] Seeding Aegis agents..."
for agent in orchestrator mirofish-swarm openclaw-gateway stall-detector; do
  curl -s -X POST "$AEGIS_URL/api/v1/agents" \
    -H "Content-Type: application/json" \
    -H "X-Admin-Key: $AEGIS_KEY" \
    -d "{\"agent_id\": \"$agent\", \"tenant_id\": \"mosaic-dev\", \"name\": \"$agent\", \"capabilities\": [\"execute\", \"notify\"]}" \
    | head -c 200
  echo ""
done

echo "[3/4] Seeding Aegis policies..."
curl -s -X POST "$AEGIS_URL/api/v1/policies" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $AEGIS_KEY" \
  -d '{"policy_id": "metering-limit", "tenant_id": "mosaic-dev", "rule": "DENY if ai_seconds > 3600", "priority": 100}' \
  | head -c 200
echo ""

curl -s -X POST "$AEGIS_URL/api/v1/policies" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $AEGIS_KEY" \
  -d '{"policy_id": "stall-alert", "tenant_id": "mosaic-dev", "rule": "ALLOW stall-detector notify", "priority": 50}' \
  | head -c 200
echo ""

# --- Orchestrator: Verify health ---
echo "[4/4] Verifying orchestrator health..."
curl -s "$ORCHESTRATOR_URL/api/v1/health" | python3 -m json.tool 2>/dev/null || echo "(orchestrator not yet ready)"

echo ""
echo "=== Seed complete ==="
echo "Dashboard: http://localhost:3000"
echo "Orchestrator: http://localhost:3005/api/v1/health"
