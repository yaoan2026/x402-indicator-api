@echo off
rem Double-click to run all tests on Windows. Output is also saved to test_log.txt.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_tests.ps1"
echo.
pause
