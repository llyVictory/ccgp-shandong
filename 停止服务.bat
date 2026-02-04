@echo off
chcp 65001 >nul
title Stop Spider Service

echo ========================================
echo   Stop Spider Service
echo ========================================
echo.
echo Stopping all Python processes...
echo.

taskkill /F /IM python.exe /T 2>nul

if errorlevel 1 (
    echo [INFO] No Python processes running
) else (
    echo [OK] Service stopped
)

echo.
pause
