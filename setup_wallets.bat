@echo off
rem Double-click to create two testnet wallets and write them into .env
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please run run_tests.bat first to create .venv
    pause
    exit /b 1
)
".venv\Scripts\python.exe" setup_wallets.py
echo.
pause
