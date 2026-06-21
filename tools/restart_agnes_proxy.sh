#!/usr/bin/env bash
set -e

cd /d/noveos

# �رվɴ��������ݴ��ڱ���/������ƥ�䣩
OLD_PIDS=$(ps aux | grep "python3 tools/agnes_proxy.py" | grep -v grep | awk '{print $1}' || true)
if [ -n "$OLD_PIDS" ]; then
    for pid in $OLD_PIDS; do
        echo "Killing old proxy PID=$pid"
        kill "$pid" 2>/dev/null || true
    done
    sleep 2
fi

export AGNES_PROXY_PORT=8964
export AGNES_API_KEY=YOUR_AGNES_API_KEY_HERE

mkdir -p logs
nohup python3 tools/agnes_proxy.py > logs/agnes_proxy.log 2>&1 &
NEW_PID=$!
echo "Started new proxy PID=$NEW_PID"
sleep 2
ps -p "$NEW_PID" && echo "Proxy is running" || echo "Proxy failed to start"
