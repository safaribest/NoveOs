#!/bin/bash
# Novel-OS 一键开发启动脚本
# 同时启动后端 (FastAPI 8001) + 前端 (Vite 3000)
# Ctrl+C 一次终止两个进程

set -e

export PYTHONUTF8=1

BACKEND_DIR="d:/noveos/novel-os"
FRONTEND_DIR="d:/noveos/app"
PYTHON="E:/crewai-venv/Scripts/python.exe"
BACKEND_URL="http://127.0.0.1:8001"

echo "========================================"
echo "  Novel-OS 开发环境一键启动"
echo "========================================"

# 检查端口占用
echo "[1/4] 检查端口..."
if netstat -ano | grep -q "127.0.0.1:8001.*LISTENING"; then
    echo "  ⚠️  端口 8001 已被占用，尝试清理旧进程..."
    # 尝试杀掉占用 8001 的进程
    for pid in $(netstat -ano | grep "127.0.0.1:8001" | grep LISTENING | awk '{print $5}' | sort -u); do
        taskkill //F //PID "$pid" 2>/dev/null || true
    done
    sleep 1
fi

if netstat -ano | grep -q "\[::1\]:3000.*LISTENING"; then
    echo "  ⚠️  端口 3000 已被占用，尝试清理旧进程..."
    for pid in $(netstat -ano | grep "\[::1\]:3000" | grep LISTENING | awk '{print $5}' | sort -u); do
        taskkill //F //PID "$pid" 2>/dev/null || true
    done
    sleep 1
fi

# 启动后端
echo "[2/4] 启动后端 (FastAPI) → $BACKEND_URL ..."
cd "$BACKEND_DIR"
$PYTHON -m uvicorn api.main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!
echo "  ✓ 后端 PID: $BACKEND_PID"

# 等待后端就绪
echo "[3/4] 等待后端就绪..."
for i in {1..30}; do
    if curl -s "$BACKEND_URL/api/v1/projects" > /dev/null 2>&1; then
        echo "  ✓ 后端已就绪"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ✗ 后端启动超时，请检查日志"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 0.5
done

# 启动前端
echo "[4/4] 启动前端 (Vite) → http://localhost:3000 ..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "  ✓ 前端 PID: $FRONTEND_PID"

echo ""
echo "========================================"
echo "  🚀 全部启动完成！"
echo "  前端: http://localhost:3000"
echo "  后端: $BACKEND_URL"
echo "  API 文档: $BACKEND_URL/docs"
echo "========================================"
echo "  按 Ctrl+C 终止所有进程"
echo ""

# 捕获 Ctrl+C，优雅终止
cleanup() {
    echo ""
    echo "[stop] 正在终止进程..."
    kill $FRONTEND_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    sleep 1
    echo "[stop] 已清理完毕"
    exit 0
}
trap cleanup INT TERM

# 等待任意子进程结束
wait
