@echo off
echo [Spider Cleaner] 正在清理所有相关后台进程...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *spider*" 2>nul
taskkill /f /im chrome.exe /fi "USERNAME eq %USERNAME%" /t 2>nul
taskkill /f /im chromedriver.exe /t 2>nul
echo [Spider Cleaner] 清理完毕！
pause
