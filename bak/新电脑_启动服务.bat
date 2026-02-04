@echo off
chcp 65001 >nul
title 山东采购网爬虫服务

cd /d "%~dp0"

:: 检查环境
if not exist venv (
    echo [错误] 未检测到虚拟环境！
    echo 请先双击运行 "新电脑_一键配置.bat"
    echo.
    pause
    exit /b
)

:: 激活环境
call venv\Scripts\activate.bat

echo ==========================================
echo         山东采购网爬虫服务已启动
echo ==========================================
echo.
echo [提示] 
echo  1. 浏览器将自动打开 http://localhost:8080
echo  2. 如果要停止服务，直接【关闭此黑色窗口】即可
echo.

:: 自动打开浏览器
timeout /t 2 /nobreak >nul
start http://localhost:8080

:: 启动Python服务
echo [系统] 正在启动主程序...
python server.py

pause
