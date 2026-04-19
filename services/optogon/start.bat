@echo off
echo Starting Optogon on :3010...
cd /d "%~dp0"
python -m uvicorn optogon.main:app --host 0.0.0.0 --port 3010 --reload
