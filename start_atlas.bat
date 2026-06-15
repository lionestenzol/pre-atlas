@echo off
REM Atlas launcher — double-click this to bring up the standalone stack.
REM Wraps scripts\start_atlas.ps1 so Windows can run it from a click.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_atlas.ps1"
echo.
echo Press any key to close this window (services will keep running).
pause >nul
