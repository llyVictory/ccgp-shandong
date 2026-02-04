@echo off
title Shandong Procurement Spider Service

cd /d "%~dp0"

:: Check environment
if not exist venv (
    echo [ERROR] Virtual environment not found!
    echo Please run "setup_environment.bat" first.
    echo.
    pause
    exit /b
)

:: Activate environment
call venv\Scripts\activate.bat

echo ==========================================
echo    Shandong Procurement Spider Service
echo ==========================================
echo.
echo [INFO] 
echo  1. Browser will open http://localhost:8080 automatically.
echo  2. To stop the service, simply CLOSE THIS WINDOW.
echo.

:: Auto open browser
timeout /t 2 /nobreak >nul
start http://localhost:8080

:: Start Python service
echo [SYSTEM] Starting main program...
python server.py

pause
