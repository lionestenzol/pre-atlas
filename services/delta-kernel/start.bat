@echo off
REM Rationalized (atlas-consolidation AC0002, wave1 task 04): no visible cmd /k terminals.
REM Defers to the canonical fleet starter - hidden windows, logs in .atlas-logs\.
REM See ~/.claude/rules/common/code-as-furniture.md - the old per-service cmd /k spawns were the terminal-spam source.
REM Not covered by start_atlas.ps1 (start manually if needed):
REM   delta-web dev UI (:5173)  - use .claude/launch.json "delta-web", or: cd web ^&^& npm run dev
REM   crucix OSINT   (:3117)  - cd ..\crucix ^&^& node server.mjs
echo Starting Delta-State Fabric via scripts\start_atlas.ps1 (hidden windows, logs in .atlas-logs\)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\start_atlas.ps1"
