# Pre Atlas - Start All Services
# Launches delta-kernel (:3001), OpenClaw (:3004), Orchestrator (:3005)
# Then runs cognitive pipeline and opens dashboard.
#
# Usage: .\scripts\start_all_services.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\bruke\Pre Atlas"
$ScriptDir = "$RepoRoot\scripts"
$CogDir = "$RepoRoot\services\cognitive-sensor"

# Ensure log directory
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "PRE ATLAS - Full Stack Boot" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# ── Step 0: Ensure NATS is running (event bus) ──
Write-Host "`n[0/7] Checking NATS event bus (:4222)..." -ForegroundColor Yellow
try {
    $natsCheck = Invoke-WebRequest -Uri "http://localhost:8222/healthz" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    Write-Host "  NATS already running." -ForegroundColor Green
} catch {
    Write-Host "  Starting NATS via docker compose..." -ForegroundColor DarkYellow
    docker compose -f "$RepoRoot\docker-compose.yml" up -d nats 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}

# ── Step 0.5: Start WebSocket Gateway (:3006) ──
Write-Host "[0.5/7] Starting WebSocket Gateway (:3006)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$ScriptDir\svc_ws_gateway.ps1" -WindowStyle Minimized
Start-Sleep -Seconds 2

# ── Step 1: Start Delta-Kernel API (:3001) ──
Write-Host "`n[1/7] Starting Delta-Kernel API (:3001)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$ScriptDir\svc_delta_kernel.ps1" -WindowStyle Minimized
Start-Sleep -Seconds 3

# ── Step 2: Start OpenClaw (:3004) ──
Write-Host "[2/6] Starting OpenClaw (:3004)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$ScriptDir\svc_openclaw.ps1" -WindowStyle Minimized
Start-Sleep -Seconds 2

# ── Step 3: Start Mosaic Orchestrator (:3005) ──
Write-Host "[3/6] Starting Mosaic Orchestrator (:3005)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$ScriptDir\svc_orchestrator.ps1" -WindowStyle Minimized
Start-Sleep -Seconds 2

# ── Step 4: Run cognitive pipeline ──
Write-Host "[4/6] Running cognitive pipeline..." -ForegroundColor Yellow
try {
    Set-Location $CogDir
    python refresh.py 2>&1 | Out-Null
    python governor_daily.py 2>&1 | Out-Null
    Write-Host "  Pipeline + Governor complete." -ForegroundColor Green
} catch {
    Write-Host "  Pipeline warning: $_" -ForegroundColor DarkYellow
}

# ── Step 5: Health check ──
Write-Host "[5/6] Checking services..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$services = @(
    @{Name="NATS"; URL="http://localhost:8222/healthz"; Port=4222},
    @{Name="WS-Gateway"; URL="http://localhost:3006"; Port=3006},
    @{Name="Delta-Kernel"; URL="http://localhost:3001/api/state"; Port=3001},
    @{Name="OpenClaw"; URL="http://localhost:3004/api/v1/health"; Port=3004},
    @{Name="Orchestrator"; URL="http://localhost:3005/api/v1/health"; Port=3005}
)

foreach ($svc in $services) {
    try {
        $response = Invoke-WebRequest -Uri $svc.URL -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host "  $($svc.Name) (:$($svc.Port)) - ONLINE" -ForegroundColor Green
    } catch {
        Write-Host "  $($svc.Name) (:$($svc.Port)) - OFFLINE (check logs\)" -ForegroundColor Red
    }
}

# ── Step 6: Open dashboard ──
Write-Host "[6/6] Opening dashboard..." -ForegroundColor Yellow
Start-Process "$RepoRoot\atlas_boot.html"

# ── Print directive ──
Write-Host "`n" -NoNewline
$DirectivePath = "$CogDir\daily_directive.txt"
if (Test-Path $DirectivePath) {
    Write-Host (Get-Content $DirectivePath -Raw) -ForegroundColor White
}

Write-Host "=" * 60 -ForegroundColor Green
Write-Host "SYSTEM ONLINE" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "  NATS:           nats://localhost:4222" -ForegroundColor White
Write-Host "  WS-Gateway:     ws://localhost:3006" -ForegroundColor White
Write-Host "  Delta-Kernel:   http://localhost:3001" -ForegroundColor White
Write-Host "  OpenClaw:       http://localhost:3004" -ForegroundColor White
Write-Host "  Orchestrator:   http://localhost:3005" -ForegroundColor White
Write-Host "  Dashboard:      atlas_boot.html (opened)" -ForegroundColor White
Write-Host "  Logs:           $RepoRoot\logs\" -ForegroundColor DarkGray
Write-Host ""

Set-Location $RepoRoot
