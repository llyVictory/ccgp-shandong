@echo off
chcp 65001 >nul
title 山东政府采购爬虫系统

echo ========================================
echo   山东政府采购爬虫系统 v1.0
echo ========================================
echo.

cd /d "%~dp0"

:: 检查虚拟环境是否存在
if not exist "venv\Scripts\python.exe" (
    echo [错误] 未检测到虚拟环境！
    echo 请先运行"首次安装.bat"进行初始化
    echo.
    pause
    exit /b 1
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 检查是否成功激活
if errorlevel 1 (
    echo [错误] 虚拟环境激活失败！
    pause
    exit /b 1
)

echo [√] 虚拟环境已激活
echo [√] 正在启动服务器...
echo.
echo ----------------------------------------
echo  Web控制台地址: http://localhost:8080
echo ----------------------------------------
echo.
echo 提示：
echo - 服务启动后会自动打开浏览器
echo - 不要关闭此窗口，否则服务会停止
echo - 按 Ctrl+C 可以停止服务
echo.

:: 等待2秒后自动打开浏览器
timeout /t 2 /nobreak >nul
start http://localhost:8080

:: 启动服务
python server.py

pause
