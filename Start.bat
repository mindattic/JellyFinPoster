@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"

echo.
echo Done.
pause
