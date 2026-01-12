# Run All Services
# Usage: .\scripts\run_all.ps1
#
# Starts Delta API in background, runs cognitive refresh, prints output locations.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DataDir = "$RepoRoot\.delta-fabric"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "PRE ATLAS - Full Stack Launcher" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Start Delta API in new window with repo-local data dir
Write-Host "`n[1/4] Starting Delta API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:DELTA_DATA_DIR='$DataDir'; cd '$RepoRoot\services\delta-kernel'; npm run api"

# Wait for API to initialize
Start-Sleep -Seconds 3

# Run cognitive refresh
Write-Host "[2/4] Running Cognitive Sensor..." -ForegroundColor Yellow
python "$RepoRoot\services\cognitive-sensor\refresh.py"

# Build daily projection
Write-Host "[3/4] Building Daily Projection..." -ForegroundColor Yellow
python "$RepoRoot\services\cognitive-sensor\build_projection.py"

# Push to Delta
Write-Host "[4/4] Pushing to Delta..." -ForegroundColor Yellow
python "$RepoRoot\services\cognitive-sensor\push_to_delta.py"

Write-Host "`n" + "=" * 60 -ForegroundColor Green
Write-Host "SERVICES RUNNING" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "Delta API:        http://localhost:3001" -ForegroundColor White
Write-Host "Delta Data:       $DataDir" -ForegroundColor White
Write-Host ""
Write-Host "Daily Projection: $RepoRoot\data\projections\today.json" -ForegroundColor White
Write-Host "Cognitive State:  $RepoRoot\services\cognitive-sensor\cognitive_state.json" -ForegroundColor White
Write-Host "Dashboard:        $RepoRoot\services\cognitive-sensor\dashboard.html" -ForegroundColor White
Write-Host "CycleBoard:       $RepoRoot\services\cognitive-sensor\cycleboard_app3.html" -ForegroundColor White
Write-Host "Daily Payload:    $RepoRoot\services\cognitive-sensor\cycleboard\brain\daily_payload.json" -ForegroundColor White
Write-Host ""
Write-Host "Close the Delta API terminal window to stop that service." -ForegroundColor DarkGray
