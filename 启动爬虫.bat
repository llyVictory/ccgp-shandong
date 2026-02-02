@echo off
chcp 65001 >nul
title 山东政府采购意向爬虫

echo ============================================
echo       山东政府采购意向爬虫 - 一键启动
echo ============================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo [提示] 首次运行，正在创建虚拟环境...
    python -m venv venv
    echo [提示] 正在安装依赖，请稍候...
    venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
)

echo [启动] 正在启动爬虫服务...
echo [提示] 请在浏览器中打开: http://localhost:8080
echo [提示] 按 Ctrl+C 停止服务
echo.

:: 启动服务
venv\Scripts\python.exe server.py

pause
