# refresh_atlas_map.ps1
# Campaign II (LIGHTS_ON, atlas-pivot-AP0001): the manifest regen chain that
# keeps audit/system-index.json + audit/system-map-data.js fresh, followed by
# an atlas-map-api reload so the live front door serves the new snapshot
# without a service restart. Before this script existed, nothing regenerated
# these files on a schedule (grep across scripts/ confirmed no caller) - the
# map could silently go stale (verified 13 days old, 2026-07-07).
# Usage: .\scripts\refresh_atlas_map.ps1   (called by the AtlasMapNightlyRefresh
#   scheduled task; also safe to run by hand any time)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot ".atlas-logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "refresh_atlas_map.log"

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = "python" }

function Write-Log($msg) {
    $line = "$(Get-Date -Format o)  $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

Write-Log "=== refresh_atlas_map starting ==="

Set-Location $RepoRoot

$steps = @(
    @{ Name = "refresh system-index"; Args = @("audit\imports\_refresh_system_index.py") },
    @{ Name = "rebuild import graph"; Args = @("audit\imports\_build_combined.py") },
    @{ Name = "rebuild system map";   Args = @("audit\imports\_build_map.py") }
)

$failed = $false
foreach ($step in $steps) {
    Write-Log "  [run] $($step.Name)"
    & $PythonExe @($step.Args) 2>&1 | ForEach-Object { Add-Content -Path $LogFile -Value "    $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "  [FAIL] $($step.Name) exited $LASTEXITCODE"
        $failed = $true
    }
}

# Tell the live atlas-map-api process (if running) to re-read the files it just
# regenerated, instead of waiting for a manual restart or MCP atlas_reload call.
# /admin/reload is a state-changing POST guarded by auth.py's shared-secret
# token (X-Atlas-Token) - without it this call 401s and gets misreported as
# "not reachable" even though the service is up. Token resolution mirrors
# auth.py's own ladder: ATLAS_WRITE_TOKEN env var, else the gitignored
# .atlas-write-token file at repo root.
$writeToken = $env:ATLAS_WRITE_TOKEN
if (-not $writeToken) {
    $tokenFile = Join-Path $RepoRoot ".atlas-write-token"
    if (Test-Path $tokenFile) { $writeToken = (Get-Content $tokenFile -Raw).Trim() }
}

try {
    if (-not $writeToken) { throw "no write token available (ATLAS_WRITE_TOKEN unset, .atlas-write-token missing)" }
    $null = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3072/admin/reload" -Headers @{ "X-Atlas-Token" = $writeToken } -TimeoutSec 10
    Write-Log "  [OK] atlas-map-api reloaded"
} catch {
    Write-Log "  [skip] atlas-map-api reload not completed: $($_.Exception.Message)"
}

Write-Log "=== refresh_atlas_map $(if ($failed) { 'FINISHED WITH ERRORS' } else { 'done' }) ==="
