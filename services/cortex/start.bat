@echo off
echo Starting Cortex execution layer on :3009...
cd /d "%~dp0"
python -m uvicorn cortex.main:app --host 0.0.0.0 --port 3009
