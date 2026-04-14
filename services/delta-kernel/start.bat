@echo off
echo Starting Delta-State Fabric...

:: Start API server in new terminal with repo-local data dir
start "Delta API" cmd /k "cd /d %~dp0 && set DELTA_DATA_DIR=%~dp0..\.delta-fabric && npm run api"

:: Wait a moment for API to start
timeout /t 5 /nobreak >nul

:: Start web app in new terminal
start "Delta Web" cmd /k "cd /d %~dp0\web && npm run dev"

:: Start Crucix OSINT feed (7 sources, port 3117)
start "Crucix OSINT" cmd /k "cd /d %~dp0\..\crucix && node server.mjs"

echo.
echo Delta-State Fabric is starting...
echo   API Server:  http://localhost:3001
echo   Web App:     http://localhost:5173
echo   Crucix OSINT: http://localhost:3117
echo.
echo Close the terminal windows to stop the servers.
