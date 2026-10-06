@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\run-local.py %*
pause
