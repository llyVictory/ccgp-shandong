@echo off
title One-Click Migration Package Generator

:: Generate timestamped folder name
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "OUTPUT_DIR=migration_package_%TIMESTAMP%"

cd /d "%~dp0"

echo ==========================================
echo      Packaging core files to:
echo      [%OUTPUT_DIR%]
echo ==========================================
echo.

:: Create target directory
mkdir "%OUTPUT_DIR%"

:: Create temp exclude list
echo __pycache__ > "%OUTPUT_DIR%\exclude_temp.txt"
echo .git >> "%OUTPUT_DIR%\exclude_temp.txt"
echo venv >> "%OUTPUT_DIR%\exclude_temp.txt"
echo .vscode >> "%OUTPUT_DIR%\exclude_temp.txt"
echo .idea >> "%OUTPUT_DIR%\exclude_temp.txt"
echo migration_package_* >> "%OUTPUT_DIR%\exclude_temp.txt"

echo [1/4] Copying core code directories...
xcopy "spider" "%OUTPUT_DIR%\spider\" /E /I /Y /exclude:%OUTPUT_DIR%\exclude_temp.txt >nul
xcopy "static" "%OUTPUT_DIR%\static\" /E /I /Y /exclude:%OUTPUT_DIR%\exclude_temp.txt >nul

echo [2/4] Copying main program and config...
copy "server.py" "%OUTPUT_DIR%\" >nul
copy "requirements.txt" "%OUTPUT_DIR%\" >nul
if exist "schedule_config.json" copy "schedule_config.json" "%OUTPUT_DIR%\" >nul

echo [3/4] Copying documentation...
if exist "README.md" copy "README.md" "%OUTPUT_DIR%\" >nul

echo [4/4] Copying run scripts...
copy "setup_environment.bat" "%OUTPUT_DIR%\" >nul
copy "start_service.bat" "%OUTPUT_DIR%\" >nul

:: Clean up
del "%OUTPUT_DIR%\exclude_temp.txt"

echo.
echo ==========================================
echo      Package Created Successfully!
echo ==========================================
echo.
echo Folder location:
echo   %~dp0%OUTPUT_DIR%
echo.
echo Please copy this entire folder to the new computer.
echo.

:: Open the folder
start "" "%OUTPUT_DIR%"
pause
