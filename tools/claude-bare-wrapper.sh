#!/usr/bin/env bash
set -euo pipefail

# Claude Code --bare 启动包装器
# 作用：强制 Claude CLI 使用 ANTHROPIC_API_KEY 模式，跳过 OAuth/登录界面

DEFAULT_CLAUDE="/c/Users/z60063357/.vscode/extensions/anthropic.claude-code-2.1.181-win32-x64/resources/native-binary/claude.exe"
CLAUDE_EXE="$DEFAULT_CLAUDE"

# 如果第一个参数是原始的 claude.exe 路径，则使用它
if [[ -n "${1:-}" ]] && [[ "$1" == *"claude.exe" ]]; then
    CLAUDE_EXE="$1"
    shift
fi

exec "$CLAUDE_EXE" --bare "$@"
