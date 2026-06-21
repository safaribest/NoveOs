#!/usr/bin/env bash
set -euo pipefail

# DeepSeek 代理启动脚本（Git Bash / WSL）
# 用法：bash start-deepseek-proxy.sh

cd "$(dirname "$0")"

export DEEPSEEK_API_KEY="YOUR_DEEPSEEK_API_KEY_HERE"
export DEEPSEEK_PROXY_PORT="3456"

echo "[DeepSeek Proxy] Starting on port ${DEEPSEEK_PROXY_PORT}..."
echo "[DeepSeek Proxy] API Key: ${DEEPSEEK_API_KEY:0:8}****"

python tools/deepseek_proxy.py
