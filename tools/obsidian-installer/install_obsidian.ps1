# Obsidian 自动安装脚本
# 用法：
#   1. 从 https://obsidian.md/download 下载 Windows 安装包（Obsidian-x.x.x.exe）
#   2. 把 .exe 文件放到本目录
#   3. 在 PowerShell 中运行：.\install_obsidian.ps1

$ErrorActionPreference = "Stop"

$installer = Get-ChildItem -Path $PSScriptRoot -Filter "Obsidian-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $installer) {
    Write-Host "未找到 Obsidian 安装包。" -ForegroundColor Red
    Write-Host "请从 https://obsidian.md/download 下载 Windows 安装包，" -ForegroundColor Yellow
    Write-Host "并将 .exe 文件放到以下目录：" -ForegroundColor Yellow
    Write-Host "  $PSScriptRoot" -ForegroundColor Cyan
    exit 1
}

Write-Host "找到安装包：$($installer.FullName)" -ForegroundColor Green
Write-Host "正在静默安装 Obsidian..." -ForegroundColor Cyan

& $installer.FullName /S

Write-Host "安装完成。" -ForegroundColor Green
Write-Host "如果桌面没有出现 Obsidian 图标，请检查 C:\Users\<用户名>\AppData\Local\Obsidian\" -ForegroundColor Yellow
