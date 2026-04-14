# Governor Daily Runner
# Called by Windows Task Scheduler at 7:00 AM
# Runs the full daily pipeline: refresh + governor brief

$ErrorActionPreference = "Stop"
$cogDir = "C:\Users\bruke\Pre Atlas\services\cognitive-sensor"
$logFile = "C:\Users\bruke\Pre Atlas\services\cognitive-sensor\governor_daily.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting daily governor pipeline" | Out-File -FilePath $logFile -Append

try {
    Set-Location $cogDir
    python run_daily.py 2>&1 | Out-File -FilePath $logFile -Append
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Daily governor pipeline completed successfully" | Out-File -FilePath $logFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $logFile -Append
    exit 1
}
