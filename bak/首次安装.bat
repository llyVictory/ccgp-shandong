@echo off
chcp 65001 >nul
title First-Time Setup - Shandong Procurement Spider

echo ========================================
echo   First-Time Setup Wizard
echo ========================================
echo.
echo This script will:
echo   - Check Python environment
echo   - Create virtual environment
echo   - Install dependencies
echo.
echo Estimated time: 3-5 minutes
echo.
pause

cd /d "%~dp0"

echo.
echo [Step 1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8 or higher:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>&1') do set PYVER=%%i
echo [OK] Python version: %PYVER%

echo.
echo [Step 2/3] Creating virtual environment...
if exist "venv" (
    echo [INFO] Existing virtual environment detected.
    echo Choose an option:
    echo   1 = Keep existing environment
    echo   2 = Delete and recreate
    set /p choice="Your choice (1/2): "
    if "!choice!"=="2" (
        echo Deleting old environment...
        rmdir /s /q venv
    )
)

if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Using existing environment
)

echo.
echo [Step 3/3] Installing dependencies...
echo This may take a few minutes, please wait...
echo.

call venv\Scripts\activate.bat

:: Upgrade pip
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

:: Install dependencies
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed!
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

:: Create downloads directory
if not exist "downloads" mkdir downloads

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Double-click "Run Spider.bat"
echo   2. Browser will open http://localhost:8080
echo   3. Start using!
echo.
echo ========================================
pause
