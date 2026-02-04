@echo off
chcp 65001 >nul
title 一键生成迁移包

:: 生成带时间戳的文件夹名称
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "OUTPUT_DIR=迁移包_%TIMESTAMP%"

cd /d "%~dp0"

echo ==========================================
echo      正在整理核心文件到目录:
echo      [%OUTPUT_DIR%]
echo ==========================================
echo.

:: 创建目标文件夹
mkdir "%OUTPUT_DIR%"

:: 创建临时排除列表，避免复制垃圾文件
echo __pycache__ > "%OUTPUT_DIR%\exclude_temp.txt"
echo .git >> "%OUTPUT_DIR%\exclude_temp.txt"
echo venv >> "%OUTPUT_DIR%\exclude_temp.txt"
echo .vscode >> "%OUTPUT_DIR%\exclude_temp.txt"
echo .idea >> "%OUTPUT_DIR%\exclude_temp.txt"

echo [1/4] 复制核心代码目录...
:: /E 复制子目录(包括空) /I 假定目标是目录 /Y 覆盖不提示 /Exclude 使用排除列表
xcopy "spider" "%OUTPUT_DIR%\spider\" /E /I /Y /exclude:%OUTPUT_DIR%\exclude_temp.txt >nul
xcopy "static" "%OUTPUT_DIR%\static\" /E /I /Y /exclude:%OUTPUT_DIR%\exclude_temp.txt >nul

echo [2/4] 复制主程序与配置文件...
copy "server.py" "%OUTPUT_DIR%\" >nul
copy "requirements.txt" "%OUTPUT_DIR%\" >nul
:: 如果有已保存的定时任务，也一起通过带走
if exist "schedule_config.json" copy "schedule_config.json" "%OUTPUT_DIR%\" >nul

echo [3/4] 复制说明文档...
if exist "使用说明.md" copy "使用说明.md" "%OUTPUT_DIR%\" >nul
if exist "README.md" copy "README.md" "%OUTPUT_DIR%\" >nul

echo [4/4] 复制运行脚本...
copy "新电脑_一键配置.bat" "%OUTPUT_DIR%\" >nul
copy "新电脑_启动服务.bat" "%OUTPUT_DIR%\" >nul

:: 清理临时文件
del "%OUTPUT_DIR%\exclude_temp.txt"

echo.
echo ==========================================
echo      打包成功！ ( ^_^)v
echo ==========================================
echo.
echo 文件夹已生成：
echo   %~dp0%OUTPUT_DIR%
echo.
echo 请直接把这个文件夹复制到新电脑（U盘/网盘传输）。
echo.

:: 自动打开生成的文件夹
start "" "%OUTPUT_DIR%"
pause
