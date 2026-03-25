# Pre Atlas - One-Command Morning Startup
# Usage: .\scripts\start.ps1
#
# 1. Starts Delta API in background
# 2. Runs daily cognitive pipeline
# 3. Opens control panel in browser
# 4. Prints today's directive

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DataDir = "$RepoRoot\.delta-fabric"
$CogDir = "$RepoRoot\services\cognitive-sensor"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "PRE ATLAS - Morning Boot" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Step 1: Start Delta API in background
Write-Host "`n[1/4] Starting Delta API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:DELTA_DATA_DIR='$DataDir'; `$env:DELTA_REPO_ROOT='$RepoRoot'; cd '$RepoRoot\services\delta-kernel'; npm run api" -WindowStyle Minimized

Start-Sleep -Seconds 3

# Step 2: Run daily cognitive pipeline
Write-Host "[2/4] Running daily pipeline..." -ForegroundColor Yellow
try {
    Set-Location $CogDir
    python refresh.py
    Write-Host "  Pipeline complete." -ForegroundColor Green
} catch {
    Write-Host "  Pipeline failed: $_" -ForegroundColor Red
}

# Step 3: Open control panel
Write-Host "[3/4] Opening control panel..." -ForegroundColor Yellow
Start-Process "http://localhost:3001"

# Step 4: Print today's directive
Write-Host "[4/4] Today's Orders:`n" -ForegroundColor Yellow
$DirectivePath = "$CogDir\daily_directive.txt"
if (Test-Path $DirectivePath) {
    $directive = Get-Content $DirectivePath -Raw
    Write-Host $directive -ForegroundColor White
} else {
    Write-Host "  No directive found. Run: python refresh.py" -ForegroundColor DarkGray
}

# Run notification if available
$NotifyPath = "$CogDir\notify.py"
if (Test-Path $NotifyPath) {
    python $NotifyPath 2>$null
}

Write-Host "`n" + "=" * 60 -ForegroundColor Green
Write-Host "SYSTEM ONLINE" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "Delta API:   http://localhost:3001" -ForegroundColor White
Write-Host "CycleBoard:  $CogDir\cycleboard\index.html" -ForegroundColor White
Write-Host "Dashboard:   $CogDir\dashboard.html" -ForegroundColor White
Write-Host ""

Set-Location $RepoRoot
