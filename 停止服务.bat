@echo off
chcp 65001 >nul
title 停止爬虫服务

echo ========================================
echo   停止爬虫服务
echo ========================================
echo.
echo 正在停止所有Python进程...
echo.

taskkill /F /IM python.exe /T 2>nul

if errorlevel 1 (
    echo [提示] 没有检测到运行中的Python进程
) else (
    echo [√] 服务已停止
)

echo.
pause
