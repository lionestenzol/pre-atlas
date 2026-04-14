# Delta-Kernel API Service Wrapper (:3001)
# Runs as background task via Windows Task Scheduler

$RepoRoot = "C:\Users\bruke\Pre Atlas"
$ServiceDir = "$RepoRoot\services\delta-kernel"
$LogFile = "$RepoRoot\logs\delta-kernel.log"

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null

$env:DELTA_DATA_DIR = "$RepoRoot\.delta-fabric"
$env:DELTA_REPO_ROOT = $RepoRoot

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] Starting Delta-Kernel API on :3001" | Out-File -FilePath $LogFile -Append

try {
    Set-Location $ServiceDir
    npx tsx src/api/server.ts 2>&1 | Out-File -FilePath $LogFile -Append
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] ERROR: $_" | Out-File -FilePath $LogFile -Append
    exit 1
}
