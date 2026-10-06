@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
py -3 scripts\verify-transfer.py
pause
