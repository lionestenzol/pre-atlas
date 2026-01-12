# Run Delta Kernel CLI
# Usage: .\scripts\run_delta_cli.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DataDir = "$RepoRoot\.delta-fabric"

Write-Host "Starting Delta Kernel CLI..." -ForegroundColor Cyan
Write-Host "Data directory: $DataDir" -ForegroundColor DarkGray
Set-Location "$RepoRoot\services\delta-kernel"
npm run start -- --data "$DataDir"
