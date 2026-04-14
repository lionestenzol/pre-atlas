@echo off
echo Starting Aegis Enterprise Fabric...

REM Start API server with repo-local data dir
start "Aegis API" cmd /k "cd /d %~dp0 && set AEGIS_DATA_DIR=%~dp0.aegis-data && npm run api"

timeout /t 3 /nobreak >nul
echo   Aegis API: http://localhost:3002
echo   Health:    http://localhost:3002/health
echo   Metrics:   http://localhost:3002/metrics
