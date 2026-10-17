@echo off
setlocal
cd /d "%~dp0"
echo BIE THRIVES Experience: OFFLINE RESEARCH ONLY. No brokerage access or trades.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 run_bie.py
) else (
  python run_bie.py
)
echo.
if errorlevel 1 echo Tests were incomplete or failed. Read the messages above.
pause
