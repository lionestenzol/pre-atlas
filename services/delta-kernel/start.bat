@echo off
echo Starting Delta-State Fabric...

:: Start API server in new terminal
start "Delta API" cmd /k "cd /d %~dp0 && npm run api"

:: Wait a moment for API to start
timeout /t 2 /nobreak >nul

:: Start web app in new terminal
start "Delta Web" cmd /k "cd /d %~dp0\web && npm run dev"

echo.
echo Delta-State Fabric is starting...
echo   API Server: http://localhost:3001
echo   Web App:    http://localhost:5173
echo.
echo Close the terminal windows to stop the servers.
