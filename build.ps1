# 构建 BUGList.exe（PyInstaller onefile，无控制台窗口）
# 用法：powershell -ExecutionPolicy Bypass -File build.ps1 [-SkipInstall]

param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path "assets\buglist.ico")) { throw "缺少 assets\buglist.ico" }

if (-not $SkipInstall) {
    python -m pip install --upgrade --disable-pip-version-check pyinstaller
}

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name BUGList `
    --icon "assets\buglist.ico" `
    --add-data "assets\buglist.ico;." `
    buglist.py

Write-Host ""
Write-Host "已生成: $root\dist\BUGList.exe"
Write-Host "发布时把 dist\BUGList.exe、install.ps1、README.md、LICENSE 打成一个 zip。"
