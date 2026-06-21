@echo off
setlocal

REM Claude Code --bare 启动包装器
REM 作用：强制 Claude CLI 使用 ANTHROPIC_API_KEY 模式，跳过 OAuth/登录界面

set "DEFAULT_CLAUDE=C:\Users\z60063357\.vscode\extensions\anthropic.claude-code-2.1.181-win32-x64\resources\native-binary\claude.exe"
set "CLAUDE_EXE=%DEFAULT_CLAUDE%"

REM 诊断日志
set "WRAPPER_LOG=E:\1\NoveOs-master\NoveOs-master\tools\claude-wrapper.log"
echo [%date% %time%] wrapper called with args: %* >> "%WRAPPER_LOG%"

REM 如果扩展把原始 claude.exe 路径作为第一个参数传入，则使用它
if not "%~1"=="" (
    if /I "%~nx1"=="claude.exe" (
        if exist "%~1" (
            set "CLAUDE_EXE=%~1"
            shift
            echo [%date% %time%] using provided claude.exe: %~1 >> "%WRAPPER_LOG%"
        )
    )
)

echo [%date% %time%] launching: "%CLAUDE_EXE%" --bare %* >> "%WRAPPER_LOG%"
"%CLAUDE_EXE%" --bare %*
