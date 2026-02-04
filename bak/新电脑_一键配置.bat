@echo off
chcp 65001 >nul
title 山东采购网爬虫 - 环境一键配置

cd /d "%~dp0"

echo ==========================================
echo      正在初始化环境，请稍候...
echo ==========================================
echo.

echo [1/4] 检测并创建虚拟环境...
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败！即将在3秒后退出...
        timeout /t 3 >nul
        exit /b 1
    )
) else (
    echo [提示] 虚拟环境已存在，跳过创建。
)

echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败！
    pause
    exit /b 1
)

echo [3/4] 升级 pip 工具...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [4/4] 安装依赖包...
echo - 安装 requirements.txt ...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo - 补充必要的缺失依赖 (webdriver-manager, ddddocr, Pillow)...
pip install webdriver-manager ddddocr Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo.
    echo [警告] 部分依赖安装可能失败，请检查网络 (推荐关闭VPN或使用手机热点)
    echo.
)

echo.
echo ==========================================
echo    配置完成！
echo    现在可以运行 "新电脑_启动服务.bat" 了
echo ==========================================
pause
