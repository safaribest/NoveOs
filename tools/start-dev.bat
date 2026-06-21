@echo off
chcp 65001 >nul
set PYTHONUTF8=1
setlocal EnableDelayedExpansion

echo ========================================
echo   Novel-OS 开发环境一键启动
echo ========================================

set BACKEND_DIR=D:\noveos\novel-os
set FRONTEND_DIR=D:\noveos\app
set PYTHON=E:\crewai-venv\Scripts\python.exe
set BACKEND_URL=http://127.0.0.1:8001

echo [1/4] 检查端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8001" ^| findstr "LISTENING"') do (
    echo   端口 8001 被占用，清理 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":::3000" ^| findstr "LISTENING"') do (
    echo   端口 3000 被占用，清理 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [2/4] 启动后端 FastAPI...
cd /d "%BACKEND_DIR%"
start "Novel-OS Backend" cmd /c "%PYTHON% -m uvicorn api.main:app --host 127.0.0.1 --port 8001"

echo [3/4] 等待后端就绪...
for /l %%i in (1,1,30) do (
    curl -s "%BACKEND_URL%/api/v1/projects" >nul 2>&1
    if !errorlevel! == 0 (
        echo   后端已就绪
        goto backend_ready
    )
    timeout /t 1 /nobreak >nul
)
echo   后端启动超时
goto end

:backend_ready
echo [4/4] 启动前端 Vite...
cd /d "%FRONTEND_DIR%"
start "Novel-OS Frontend" cmd /c "npm run dev"

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   全部启动完成！
echo   前端: http://localhost:3000
echo   后端: %BACKEND_URL%
echo   API 文档: %BACKEND_URL%/docs
echo ========================================
echo   关闭本窗口即可终止所有进程
echo.

:end
pause
