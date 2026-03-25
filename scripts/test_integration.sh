#!/usr/bin/env bash
# Integration smoke test: Python → JSON → TypeScript API → Unified State
# Validates the full pipeline works end-to-end.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CS_DIR="$REPO_ROOT/services/cognitive-sensor"
DK_DIR="$REPO_ROOT/services/delta-kernel"
API_PID=""

cleanup() {
  if [ -n "$API_PID" ]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

PASS=0
FAIL=0

check() {
  local label="$1"
  local result="$2"
  if [ "$result" = "ok" ]; then
    echo "  [PASS] $label"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $label — $result"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Pre Atlas Integration Smoke Test ==="
echo ""

# Step 1: Run cognitive refresh pipeline
echo "Step 1: Running cognitive refresh pipeline..."
cd "$CS_DIR"
if python refresh.py > /dev/null 2>&1; then
  check "refresh.py completes" "ok"
else
  check "refresh.py completes" "exit code $?"
fi

# Step 2: Verify cognitive_state.json
echo "Step 2: Verifying cognitive_state.json..."
CS_JSON="$CS_DIR/cognitive_state.json"
if [ -f "$CS_JSON" ]; then
  check "cognitive_state.json exists" "ok"
else
  check "cognitive_state.json exists" "file not found"
fi

if python -c "import json; json.load(open('$CS_JSON'))" 2>/dev/null; then
  check "cognitive_state.json is valid JSON" "ok"
else
  check "cognitive_state.json is valid JSON" "parse error"
fi

if python -c "import json; d=json.load(open('$CS_JSON')); assert 'closure' in d, 'missing closure'" 2>/dev/null; then
  check "cognitive_state.json has closure field" "ok"
else
  check "cognitive_state.json has closure field" "missing"
fi

# Step 3: Verify daily_payload.json
echo "Step 3: Verifying daily_payload.json..."
DP_JSON="$CS_DIR/daily_payload.json"
if [ -f "$DP_JSON" ]; then
  check "daily_payload.json exists" "ok"
else
  check "daily_payload.json exists" "file not found"
fi

if python -c "import json; d=json.load(open('$DP_JSON')); assert 'mode' in d; assert 'build_allowed' in d" 2>/dev/null; then
  check "daily_payload.json has mode and build_allowed" "ok"
else
  check "daily_payload.json has mode and build_allowed" "missing fields"
fi

# Step 4: Start delta-kernel API
echo "Step 4: Starting delta-kernel API..."
cd "$DK_DIR"
npx tsx src/api/server.ts > /dev/null 2>&1 &
API_PID=$!
sleep 4

# Step 5: Hit unified state endpoint
echo "Step 5: Checking /api/state/unified..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/api/state/unified 2>/dev/null || echo "000")
if [ "$RESPONSE" = "200" ]; then
  check "GET /api/state/unified returns 200" "ok"
else
  check "GET /api/state/unified returns 200" "got $RESPONSE"
fi

UNIFIED=$(curl -s http://localhost:3001/api/state/unified 2>/dev/null || echo "{}")
if echo "$UNIFIED" | python -c "import sys,json; d=json.load(sys.stdin); assert d.get('derived',{}).get('mode')" 2>/dev/null; then
  check "Unified state has derived.mode" "ok"
else
  check "Unified state has derived.mode" "missing"
fi

# Step 6: Verify mode consistency
echo "Step 6: Checking mode consistency..."
PY_MODE=$(python -c "import json; print(json.load(open('$DP_JSON'))['mode'])" 2>/dev/null || echo "UNKNOWN")
API_MODE=$(echo "$UNIFIED" | python -c "import sys,json; print(json.load(sys.stdin).get('derived',{}).get('mode','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
if [ "$PY_MODE" = "$API_MODE" ]; then
  check "Python mode ($PY_MODE) matches API mode ($API_MODE)" "ok"
else
  check "Python mode ($PY_MODE) matches API mode ($API_MODE)" "mismatch"
fi

# Summary
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
