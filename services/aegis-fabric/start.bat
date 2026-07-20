@echo off
REM Rationalized (atlas-consolidation AC0002, wave1 task 04): no visible cmd /k terminals.
REM Defers to the canonical fleet starter - hidden windows, logs in .atlas-logs\.
REM See ~/.claude/rules/common/code-as-furniture.md - the old cmd /k spawn was the terminal-spam source.
echo Starting Aegis Enterprise Fabric via scripts\start_atlas.ps1 (hidden windows, logs in .atlas-logs\)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\start_atlas.ps1"
echo   Aegis API: http://localhost:3002
echo   Health:    http://localhost:3002/health
echo   Metrics:   http://localhost:3002/metrics
