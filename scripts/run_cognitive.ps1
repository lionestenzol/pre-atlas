# Run Cognitive Sensor (refresh pipeline)
# Usage: .\scripts\run_cognitive.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "Running Cognitive Sensor..." -ForegroundColor Cyan
python "$RepoRoot\services\cognitive-sensor\refresh.py"

Write-Host "`nOutputs:" -ForegroundColor Green
Write-Host "  Dashboard: $RepoRoot\services\cognitive-sensor\dashboard.html"
Write-Host "  Directive: $RepoRoot\services\cognitive-sensor\daily_directive.txt"
Write-Host "  Payload:   $RepoRoot\services\cognitive-sensor\cycleboard\brain\daily_payload.json"
