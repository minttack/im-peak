@echo off
setlocal
cd /d "%~dp0"
echo BIE THRIVES Experience - Robinhood READ-ONLY connection
echo No buying, selling, options orders, or transfers are supported by this launcher.
echo Codex is NOT required. You will need to approve the Robinhood sign-in in your browser.
echo.
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher 'py' not found. Install Python 3.11+ and try again.
  pause
  exit /b 1
)
if not exist ".bie_runtime" mkdir ".bie_runtime"
if not exist ".bie_runtime\rh_mcp_env\Scripts\python.exe" (
  echo Preparing isolated Python environment, first use only...
  py -3 -m venv ".bie_runtime\rh_mcp_env"
  if errorlevel 1 goto failed
)
set "PYTHON=.bie_runtime\rh_mcp_env\Scripts\python.exe"
"%PYTHON%" -m pip install --disable-pip-version-check "mcp==1.23.0"
if errorlevel 1 goto failed
echo.
echo Robinhood will open in your browser. NEVER share login codes or tokens.
echo Keep this window open to refresh READ-ONLY price snapshots.
"%PYTHON%" "bie_robinhood_connect.py"
if errorlevel 1 goto failed
echo.
echo Finished. No trades were placed.
pause
exit /b 0
:failed
echo.
echo Setup or connection did not complete. Your existing BIE monitor is unchanged.
echo No trades were placed by this launcher.
pause
exit /b 1
