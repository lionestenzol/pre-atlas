# OpenClaw Service Wrapper (:3004)
# Runs as background task via Windows Task Scheduler

$RepoRoot = "C:\Users\bruke\Pre Atlas"
$ServiceDir = "$RepoRoot\services\openclaw"
$LogFile = "$RepoRoot\logs\openclaw.log"

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null

$env:OPENCLAW_PORT = "3004"
$env:DELTA_API_URL = "http://localhost:3001"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting OpenClaw on :3004" | Out-File -FilePath $LogFile -Append

try {
    Set-Location $ServiceDir
    python -m uvicorn openclaw.api:app --host 127.0.0.1 --port 3004 --app-dir src 2>&1 | Out-File -FilePath $LogFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $LogFile -Append
    exit 1
}
