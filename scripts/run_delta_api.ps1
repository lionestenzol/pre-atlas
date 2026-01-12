# Run Delta Kernel API Server
# Usage: .\scripts\run_delta_api.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DataDir = "$RepoRoot\.delta-fabric"

Write-Host "Starting Delta Kernel API on http://localhost:3001..." -ForegroundColor Cyan
Write-Host "Data directory: $DataDir" -ForegroundColor DarkGray
Set-Location "$RepoRoot\services\delta-kernel"

# Set env var for API server (doesn't take --data arg)
$env:DELTA_DATA_DIR = $DataDir
npm run api
