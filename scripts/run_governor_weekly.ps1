# Governor Weekly Runner
# Called by Windows Task Scheduler on Sunday at 8:00 AM
# Runs the full weekly pipeline: daily + agents + weekly packet

$ErrorActionPreference = "Stop"
$cogDir = "C:\Users\bruke\Pre Atlas\services\cognitive-sensor"
$logFile = "C:\Users\bruke\Pre Atlas\services\cognitive-sensor\governor_weekly.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting weekly governor pipeline" | Out-File -FilePath $logFile -Append

try {
    Set-Location $cogDir
    python run_weekly.py 2>&1 | Out-File -FilePath $logFile -Append
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] Weekly governor pipeline completed successfully" | Out-File -FilePath $logFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $logFile -Append
    exit 1
}
