@echo off
setlocal
cd /d "%~dp0"
echo BIE THRIVES - H140 preserved, Robinhood quotes READ ONLY
echo Live orders, transfers, permission changes, and brokerage account reads are disabled.
echo.
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 or newer is required.
  pause
  exit /b 1
)
py -3 -m unittest discover -s tests -p "test_*.py" -q
if errorlevel 1 goto failed
py -3 bie_safety.py status
if errorlevel 1 goto failed
echo.
echo Starting the existing read-only Robinhood quote monitor.
call CONNECT_BIE_ROBINHOOD_READONLY.bat
exit /b %errorlevel%
:failed
echo Safety checks failed. The Robinhood connector was not started.
pause
exit /b 1
