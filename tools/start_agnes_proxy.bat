@echo off
setlocal

cd /d "D:\noveos"

set AGNES_PROXY_PORT=8964
set AGNES_API_KEY=YOUR_AGNES_API_KEY_HERE

if not exist logs mkdir logs

taskkill /F /IM python3.exe 2>/dev/null
timeout /t 2 /nobreak >/dev/null

start /b "" python3 tools\agnes_proxy.py > logs\agnes_proxy.log 2>&1

echo Agnes proxy started on http://127.0.0.1:8964
