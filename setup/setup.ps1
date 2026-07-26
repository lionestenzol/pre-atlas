# Atlas turnkey setup — start the system, then fan out the behavioral profile.
# Usage:
#   pwsh setup/setup.ps1            # start services + apply active profile
#   pwsh setup/setup.ps1 -Reset     # start services + blank-canvas the behavioral state
#   pwsh setup/setup.ps1 -Profile setup/atlas_profile.template.json
param(
    [switch]$Reset,
    [string]$Profile = "",
    [string]$Api = "http://127.0.0.1:3001"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot   # setup/ -> repo root
$startScript = Join-Path $repoRoot "scripts\start_atlas.ps1"

Write-Host "[setup] 1/2 starting Atlas services..." -ForegroundColor Cyan
if (Test-Path $startScript) {
    & $startScript
} else {
    Write-Warning "start_atlas.ps1 not found at $startScript — skipping service start. Apply will still run if delta-kernel is already up."
}

# Give delta-kernel a moment to bind :3001 if it was just started.
$deadline = (Get-Date).AddSeconds(30)
do {
    try {
        $null = Invoke-WebRequest -Uri "$Api/api/auth/token" -TimeoutSec 3 -UseBasicParsing
        $up = $true
    } catch {
        $up = $false
        Start-Sleep -Milliseconds 1500
    }
} until ($up -or (Get-Date) -gt $deadline)

if (-not $up) {
    Write-Error "[setup] delta-kernel never came up at $Api — cannot apply profile."
    exit 2
}

Write-Host "[setup] 2/2 applying behavioral profile..." -ForegroundColor Cyan
$applyArgs = @((Join-Path $PSScriptRoot "apply.py"), "--api", $Api)
if ($Profile) { $applyArgs += @("--profile", $Profile) }
if ($Reset)   { $applyArgs += "--reset" }

python @applyArgs
exit $LASTEXITCODE
