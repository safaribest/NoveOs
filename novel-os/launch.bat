@echo off
chcp 65001 >nul
setlocal

REM Novel-OS 启动脚本（Windows）
REM 使用 crewai-venv 虚拟环境

set NOVEL_BASE_PATH=D:\noveos\books
set CREWAI_STUDIO_PATH=D:\noveos\crewai
REM SiliconFlow 硅基流动 API（注册送 2000万 Tokens）
REM 获取 Key: https://cloud.siliconflow.cn → 账户管理 → API 密钥
REM 请设置 OPENAI_API_KEY 环境变量，或使用 .env 文件
set OPENAI_API_KEY=%OPENAI_API_KEY%
set OPENAI_API_BASE=https://api.siliconflow.cn/v1
set PYTHONIOENCODING=utf-8

set PYTHON=E:\crewai-venv\Scripts\python.exe

echo ==========================================
echo Novel-OS V1.0 - DeepSeek-v4-pro 写作流水线
echo ==========================================
echo.

if "%1"=="" (
    echo 用法:
    echo   launch.bat init           初始化状态库
    echo   launch.bat init-outline   从大纲初始化
    echo   launch.bat write 1        写第1章
    echo   launch.bat write-range 1 5 --resume   写1-5章（断点续传）
    echo   launch.bat state          导出状态
    goto :eof
)

if "%1"=="init" (
    %PYTHON% cli.py --book book.yaml init
    goto :eof
)

if "%1"=="init-outline" (
    %PYTHON% cli.py --book book.yaml init --outline outline.example.json
    goto :eof
)

if "%1"=="write" (
    if "%2"=="" (
        echo 请指定章节号: launch.bat write 1
        goto :eof
    )
    %PYTHON% cli.py --book book.yaml write --chapter %2
    goto :eof
)

if "%1"=="write-range" (
    if "%2"=="" (
        echo 请指定范围: launch.bat write-range 1 5
        goto :eof
    )
    if "%3"=="" (
        echo 请指定结束章节: launch.bat write-range 1 5
        goto :eof
    )
    %PYTHON% cli.py --book book.yaml write --range %2:%3 --resume
    goto :eof
)

if "%1"=="state" (
    %PYTHON% cli.py --book book.yaml state --export world_view.json
    goto :eof
)

echo 未知命令: %1
