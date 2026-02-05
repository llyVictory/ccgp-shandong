# 1. Create virtual environment
Write-Host "--- Creating environment ---" -ForegroundColor Cyan
if (Test-Path venv) {
    Remove-Item -Path venv -Recurse -Force
}
python -m venv venv

# 2. Activate environment
Write-Host "--- Activating ---" -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip and install requirements
Write-Host "--- Installing dependencies ---" -ForegroundColor Cyan
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

Write-Host "--- Done! ---" -ForegroundColor Green
Read-Host "Press Enter to exit"
