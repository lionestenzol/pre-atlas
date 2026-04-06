# Pre Atlas - WebSocket Gateway Service (:3006)
$ErrorActionPreference = "Stop"
$ServiceDir = "C:\Users\bruke\Pre Atlas\services\ws-gateway"
$LogDir = "C:\Users\bruke\Pre Atlas\logs"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host "Starting WebSocket Gateway (:3006)..." -ForegroundColor Cyan

Set-Location $ServiceDir
npm start 2>&1 | Tee-Object -FilePath "$LogDir\ws-gateway.log"
