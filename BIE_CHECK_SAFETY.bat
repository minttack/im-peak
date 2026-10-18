@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (py -3 bie_safety.py status) else (python bie_safety.py status)
echo.
echo Research-only. This check does NOT start trading or connect Robinhood.
pause
