@echo off
rem Pay once (0.001 test USDC) to your deployed API, e.g. https://xxx.onrender.com
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please run run_tests.bat first to create .venv
    pause
    exit /b 1
)
set /p URL=Paste your Render URL (e.g. https://xxx.onrender.com) and press Enter:
set PYTHONUTF8=1
".venv\Scripts\python.exe" client.py %URL% > remote_log.txt 2>&1
type remote_log.txt
echo.
echo Saved to remote_log.txt
pause
