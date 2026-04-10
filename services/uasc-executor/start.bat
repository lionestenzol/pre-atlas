@echo off
echo Starting UASC Executor on port 3008...
cd /d "%~dp0"
python server.py --port 3008
