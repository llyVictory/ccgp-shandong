@echo off
REM Testing start
echo Environment Setup starting...

cd /d "%~dp0"
echo Current path: %~dp0

REM Check Python
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please ensure it is installed and "Add to PATH" is checked.
    pause
    exit /b
)

REM Delete old venv if exists
if exist venv (
    echo Deleting old venv...
    rmdir /s /q venv
)

REM Create venv
echo Creating venv...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv!
    pause
    exit /b
)

REM Activate and install
echo Activating...
call venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo ==========================================
echo    Setup Complete!
echo ==========================================
pause