@echo off
chcp 65001 >nul
title 打包工具 - 创建便携版

echo ========================================
echo   便携版打包工具
echo ========================================
echo.
echo 此脚本将创建一个可直接复制到U盘的便携版本
echo.
pause

cd /d "%~dp0"

:: 设置输出目录
set OUTPUT_DIR=..\spider_portable
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%

echo.
echo [1/5] 准备打包目录...
if exist "%OUTPUT_DIR%" (
    echo 警告：目标目录已存在，将被覆盖！
    pause
    rmdir /s /q "%OUTPUT_DIR%"
)
mkdir "%OUTPUT_DIR%"
echo [√] 目录创建完成

:: 复制核心文件
echo.
echo [2/5] 复制核心文件...
xcopy /E /I /Y server.py "%OUTPUT_DIR%\" >nul
xcopy /E /I /Y requirements.txt "%OUTPUT_DIR%\" >nul
xcopy /E /I /Y spider "%OUTPUT_DIR%\spider\" >nul
xcopy /E /I /Y static "%OUTPUT_DIR%\static\" >nul
echo [√] 核心文件复制完成

:: 复制启动脚本
echo.
echo [3/5] 复制启动脚本...
copy /Y "启动爬虫.bat" "%OUTPUT_DIR%\" >nul
copy /Y "首次安装.bat" "%OUTPUT_DIR%\" >nul
copy /Y "使用说明.md" "%OUTPUT_DIR%\" >nul
echo [√] 启动脚本复制完成

:: 创建默认目录
echo.
echo [4/5] 创建必要目录...
mkdir "%OUTPUT_DIR%\downloads" 2>nul
echo [√] 目录创建完成

:: 清理不必要文件
echo.
echo [5/5] 清理临时文件...
if exist "%OUTPUT_DIR%\__pycache__" rmdir /s /q "%OUTPUT_DIR%\__pycache__"
if exist "%OUTPUT_DIR%\spider\__pycache__" rmdir /s /q "%OUTPUT_DIR%\spider\__pycache__"
if exist "%OUTPUT_DIR%\*.pyc" del /q "%OUTPUT_DIR%\*.pyc"
if exist "%OUTPUT_DIR%\schedule_config.json" del /q "%OUTPUT_DIR%\schedule_config.json"
echo [√] 清理完成

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo 输出目录: %OUTPUT_DIR%
echo.
echo 下一步操作：
echo 1. 打开上级目录查看 spider_portable 文件夹
echo 2. 将整个文件夹复制到U盘
echo 3. 在目标电脑上运行"首次安装.bat"
echo 4. 然后运行"启动爬虫.bat"
echo.
echo 建议：可以将 spider_portable 压缩为ZIP方便传输
echo.
pause

:: 打开输出目录
explorer "%OUTPUT_DIR%"
