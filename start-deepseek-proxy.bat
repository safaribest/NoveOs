@echo off
setlocal

REM DeepSeek 代理启动脚本（Windows）
REM 用法：双击运行，或在终端执行 start-deepseek-proxy.bat

cd /d "%~dp0"

set "DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY_HERE"
set "DEEPSEEK_PROXY_PORT=3456"

echo [DeepSeek Proxy] Starting on port %DEEPSEEK_PROXY_PORT%...
echo [DeepSeek Proxy] API Key: %DEEPSEEK_API_KEY:~0,8%****

python tools\deepseek_proxy.py

pause
