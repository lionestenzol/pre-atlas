#!/usr/bin/env bash
# installer.sh — One-command Mosaic Platform setup.
# Detects OS, checks prerequisites, builds, and starts all services.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    Mosaic Platform — Installer       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- Step 1: Detect OS ---
OS="unknown"
case "$(uname -s)" in
  Linux*)   OS="linux";;
  Darwin*)  OS="macos";;
  MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac
log "Detected OS: $OS"

# --- Step 2: Check Docker ---
if ! command -v docker &>/dev/null; then
  fail "Docker not found. Install from https://docs.docker.com/get-docker/"
fi
log "Docker found: $(docker --version | head -c 40)"

if ! docker compose version &>/dev/null; then
  fail "Docker Compose V2 not found. Update Docker or install docker-compose-plugin."
fi
log "Docker Compose found: $(docker compose version --short)"

# --- Step 3: Check Docker daemon ---
if ! docker info &>/dev/null; then
  fail "Docker daemon not running. Start Docker Desktop or 'sudo systemctl start docker'."
fi
log "Docker daemon is running"

# --- Step 4: Environment file ---
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    warn "Created .env from .env.example — edit it to add your ANTHROPIC_API_KEY"
  else
    fail ".env.example not found. Are you in the project root?"
  fi
else
  log ".env already exists"
fi

# --- Step 5: Build and start ---
log "Building all services (this may take a few minutes)..."
docker compose build --parallel 2>&1 | tail -5

log "Starting services..."
docker compose up -d

# --- Step 6: Wait for health ---
log "Waiting for services to become healthy..."
MAX_WAIT=120
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
  HEALTHY=$(docker compose ps --format json 2>/dev/null | python3 -c "
import sys, json
healthy = 0
total = 0
for line in sys.stdin:
    try:
        svc = json.loads(line)
        total += 1
        if svc.get('Health', '') == 'healthy' or svc.get('State', '') == 'running':
            healthy += 1
    except: pass
print(f'{healthy}/{total}')
" 2>/dev/null || echo "0/0")

  echo -ne "\r  Services healthy: $HEALTHY (${ELAPSED}s / ${MAX_WAIT}s)"

  # Check if all app services are up
  if curl -sf http://localhost:3005/api/v1/health &>/dev/null; then
    echo ""
    log "Orchestrator is healthy"
    break
  fi

  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  warn "Timeout waiting for services. Check: docker compose ps"
fi

# --- Step 7: Seed data ---
if [ -f seed-mosaic.sh ]; then
  log "Seeding demo data..."
  bash seed-mosaic.sh 2>&1 | tail -3
fi

# --- Done ---
echo ""
echo "╔══════════════════════════════════════╗"
echo "║    Mosaic Platform — Ready!          ║"
echo "╠══════════════════════════════════════╣"
echo "║  Dashboard:    http://localhost:3000 ║"
echo "║  Orchestrator: http://localhost:3005 ║"
echo "║  Delta Kernel: http://localhost:3001 ║"
echo "║  Aegis Fabric: http://localhost:3002 ║"
echo "║  MiroFish:     http://localhost:3003 ║"
echo "║  OpenClaw:     http://localhost:3004 ║"
echo "╚══════════════════════════════════════╝"
echo ""
