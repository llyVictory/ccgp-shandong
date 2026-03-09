@echo off
title Environment Setup Installer
cd /d "%~dp0"

echo [System] Starting PowerShell installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "./setup_environment.ps1"

pause
