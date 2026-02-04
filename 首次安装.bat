@echo off
chcp 65001 >nul
title 首次安装 - 山东政府采购爬虫系统

echo ========================================
echo   首次安装向导
echo ========================================
echo.
echo 此脚本将完成以下操作：
echo  1. 检查Python环境
echo  2. 创建虚拟环境
echo  3. 安装所需依赖包
echo.
echo 预计耗时：3-5分钟
echo.
pause

cd /d "%~dp0"

:: 1. 检查Python
echo.
echo [1/3] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python！
    echo.
    echo 请先安装Python 3.8或更高版本：
    echo https://www.python.org/downloads/
    echo.
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [√] Python版本: %PYVER%

:: 2. 创建虚拟环境
echo.
echo [2/3] 创建虚拟环境...
if exist "venv" (
    echo [提示] 检测到已存在的虚拟环境，是否删除重建？
    echo  1 = 保留现有环境
    echo  2 = 删除重建
    set /p choice="请选择 (1/2): "
    if "!choice!"=="2" (
        echo 正在删除旧环境...
        rmdir /s /q venv
    )
)

if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败！
        pause
        exit /b 1
    )
    echo [√] 虚拟环境创建成功
) else (
    echo [√] 使用现有虚拟环境
)

:: 3. 安装依赖
echo.
echo [3/3] 安装依赖包...
echo 这可能需要几分钟，请耐心等待...
echo.

call venv\Scripts\activate.bat

:: 升级pip
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败！
    echo 请检查网络连接后重试
    pause
    exit /b 1
)

:: 创建下载目录
if not exist "downloads" mkdir downloads

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 下一步：
echo  1. 双击运行"启动爬虫.bat"
echo  2. 浏览器自动打开 http://localhost:8080
echo  3. 开始使用！
echo.
echo ========================================
pause
