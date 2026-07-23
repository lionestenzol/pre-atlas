@echo off
REM Atlas — double-click to stop all standalone services.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_atlas.ps1"
echo.
pause >nul
