@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (py -3 bie_safety.py stop) else (python bie_safety.py stop)
echo.
echo Stop is latched for this proposed safety gate. This does NOT cancel or stop any other external agent or Robinhood orders. Disconnect or pause other agents separately.
pause
