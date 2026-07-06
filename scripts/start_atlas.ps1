# Atlas — bring up every standalone service.
# Hidden windows · logs in .atlas-logs\ · browser opens to inPACT when ready.
# Usage: .\scripts\start_atlas.ps1   (or double-click start_atlas.bat at repo root)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot ".atlas-logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$HttpServer = "C:\Users\bruke\AppData\Roaming\npm\node_modules\http-server\bin\http-server"

# Services. Order: low-deps first.
# Skipped (need Docker): mirofish (Neo4j), ws-gateway (NATS).
# Retired 2026-07-06 (FA0001): mosaic-orchestrator:3005 -> superseded by optogon + cortex (task 01);
#   mosaic-dashboard:3000 -> retired with its backend (task 02). Archived to services/_retired/.
#   See festival finish-atlas-fleet-FA0001.
$services = @(
    @{ Name = "delta-kernel";     Port = 3001; Cwd = "$RepoRoot\services\delta-kernel";        Cmd = "`$env:DELTA_REPO_ROOT='$RepoRoot'; `$env:DELTA_DATA_DIR='$RepoRoot\.delta-fabric'; npx tsx src/api/server.ts" },
    @{ Name = "aegis-fabric";     Port = 3002; Cwd = "$RepoRoot\services\aegis-fabric";        Cmd = "node --env-file=.env --import tsx/esm src/api/server.ts" },
    @{ Name = "openclaw";         Port = 3004; Cwd = "$RepoRoot\services\openclaw";            Cmd = "`$env:PYTHONPATH='src'; python -m uvicorn openclaw.api:app --host 127.0.0.1 --port 3004" },
    @{ Name = "inpact";           Port = 3006; Cwd = "$RepoRoot\apps\inpact";                  Cmd = "node `"$HttpServer`" . -p 3006 -c-1 --cors" },
    @{ Name = "code-converter";   Port = 3007; Cwd = "$RepoRoot\apps\code-converter";          Cmd = "python server.py" },
    @{ Name = "uasc";             Port = 3008; Cwd = "$RepoRoot\services\uasc-executor";       Cmd = "python server.py --port 3008" },
    @{ Name = "cortex";           Port = 3009; Cwd = "$RepoRoot\services\cortex";              Cmd = "`$env:PYTHONPATH='src'; python -m uvicorn cortex.main:app --host 127.0.0.1 --port 3009" },
    @{ Name = "optogon";          Port = 3010; Cwd = "$RepoRoot\services\optogon";             Cmd = "`$env:PYTHONPATH='src'; python -m uvicorn optogon.main:app --host 127.0.0.1 --port 3010" },
    @{ Name = "blueprint-gen";    Port = 3030; Cwd = "$RepoRoot\apps\blueprint-generator";     Cmd = "npx next dev -p 3030" },
    @{ Name = "canvas-engine";    Port = 3050; Cwd = "$RepoRoot\services\canvas-engine";       Cmd = "npm run dev" },
    # atlas substrate (sibling repo, absolute Cwd): frontend over data the others produce, starts last.
    @{ Name = "atlas-substrate";  Port = 8887; Cwd = "C:\Users\bruke\atlas";                   Cmd = "python serve.py" }
)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ATLAS - starting $($services.Count) services" -ForegroundColor Cyan
Write-Host "Logs: $LogDir" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

foreach ($svc in $services) {
    $existing = Get-NetTCPConnection -State Listen -LocalPort $svc.Port -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  [skip ] $($svc.Name) :$($svc.Port) already running (PID $($existing.OwningProcess))" -ForegroundColor Yellow
        continue
    }
    if (-not (Test-Path $svc.Cwd)) {
        Write-Host "  [skip ] $($svc.Name) - cwd missing: $($svc.Cwd)" -ForegroundColor DarkYellow
        continue
    }

    Write-Host "  [start] $($svc.Name) :$($svc.Port)" -ForegroundColor White
    $logFile = Join-Path $LogDir "$($svc.Name).log"
    # Single -Command line: cd → seed log → run, redirecting all output to log
    $inner = "Set-Location '$($svc.Cwd)'; Set-Content -Path '$logFile' -Value '=== $($svc.Name) === $(Get-Date -Format o)'; $($svc.Cmd) 2>&1 | Add-Content -Path '$logFile'"
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $inner
    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "  Waiting up to 60s for services to bind ports ..." -ForegroundColor DarkGray

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    $allUp = $true
    foreach ($svc in $services) {
        if (-not (Get-NetTCPConnection -State Listen -LocalPort $svc.Port -ErrorAction SilentlyContinue)) {
            $allUp = $false; break
        }
    }
    if ($allUp) { break }
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "STATUS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$alive = 0
foreach ($svc in $services) {
    $listen = Get-NetTCPConnection -State Listen -LocalPort $svc.Port -ErrorAction SilentlyContinue
    if ($listen) {
        Write-Host ("  [OK  ] {0,-18} :{1,-5} PID {2}" -f $svc.Name, $svc.Port, $listen.OwningProcess) -ForegroundColor Green
        $alive++
    } else {
        $log = Join-Path $LogDir "$($svc.Name).log"
        Write-Host ("  [FAIL] {0,-18} :{1,-5} see {2}" -f $svc.Name, $svc.Port, $log) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "  $alive of $($services.Count) services up" -ForegroundColor $(if ($alive -eq $services.Count) {"Green"} else {"Yellow"})
Write-Host ""
Write-Host "  inPACT (your UI):  http://127.0.0.1:3006" -ForegroundColor White
Write-Host "  Cortex API:        http://127.0.0.1:3009/health" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Stop:    stop_atlas.bat" -ForegroundColor DarkGray
Write-Host "  Status:  .\scripts\status_atlas.ps1" -ForegroundColor DarkGray
Write-Host ""

# Open the two dashboards as pinned Chrome tabs (inPACT + atlas substrate).
$dashUrls = @("http://127.0.0.1:3006", "http://127.0.0.1:8887")
try {
    Start-Process chrome.exe -ArgumentList $dashUrls -ErrorAction Stop
} catch {
    # chrome.exe not on PATH: fall back to the standard install locations.
    $chromeExe = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chromeExe) {
        Start-Process $chromeExe -ArgumentList $dashUrls
    } else {
        Write-Host "  [warn] Chrome not found; open manually: $($dashUrls -join '  ')" -ForegroundColor Yellow
    }
}
