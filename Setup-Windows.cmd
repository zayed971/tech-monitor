@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or newer from python.org, then run this file again.
  pause
  exit /b 1
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo Python 3.11 or newer is required. Update Python and try again.
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -e ".[browser,test]"
if errorlevel 1 (
  pause
  exit /b 1
)
echo Setup finished. Chrome must already be installed for Marketplace browsing.
echo Start-Monitor.cmd runs the retailer monitor. Start-Marketplace.cmd opens Chrome.
pause
