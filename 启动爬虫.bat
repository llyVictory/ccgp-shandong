@echo off
chcp 65001 >nul
title Shandong Procurement Spider System

echo ========================================
echo   Shandong Procurement Spider v1.0
echo ========================================
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run "First-Time Setup.bat" first
    echo.
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Check if activation succeeded
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)

echo [OK] Virtual environment activated
echo [OK] Starting server...
echo.
echo ----------------------------------------
echo  Web Console: http://localhost:8080
echo ----------------------------------------
echo.
echo Tips:
echo  - Browser will open automatically
echo  - Do NOT close this window
echo  - Press Ctrl+C to stop the server
echo.

:: Wait 2 seconds then open browser
timeout /t 2 /nobreak >nul
start http://localhost:8080

:: Start server
python server.py

pause
