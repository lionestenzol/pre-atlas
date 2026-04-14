# Mosaic Orchestrator Service Wrapper (:3005)
# Runs as background task via Windows Task Scheduler

$RepoRoot = "C:\Users\bruke\Pre Atlas"
$ServiceDir = "$RepoRoot\services\mosaic-orchestrator"
$LogFile = "$RepoRoot\logs\orchestrator.log"

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null

$env:ORCHESTRATOR_PORT = "3005"
$env:DELTA_API_URL = "http://localhost:3001"
$env:OPENCLAW_API_URL = "http://localhost:3004"
$env:COGNITIVE_SENSOR_DIR = "$RepoRoot\services\cognitive-sensor"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting Mosaic Orchestrator on :3005" | Out-File -FilePath $LogFile -Append

try {
    Set-Location $ServiceDir
    python -m uvicorn mosaic.api:app --host 127.0.0.1 --port 3005 --app-dir src 2>&1 | Out-File -FilePath $LogFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $LogFile -Append
    exit 1
}
