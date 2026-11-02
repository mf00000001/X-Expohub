#!/usr/bin/env bash
# ============================================================
#  ExpoHub 一键停止（macOS / Linux）
#  结束后端 :8002 与前端 :5173 上的 ExpoHub 进程
# ============================================================
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

ok()   { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
step() { printf '  \033[90m[..]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[!!]\033[0m %s\n' "$1"; }

echo
echo "  ExpoHub 一键停止"
echo

killed=0
kill_pattern() {
  local pattern="$1"
  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null | grep -v "^$$\$" || true)"
  for pid in $pids; do
    step "结束进程 $pid（匹配 $pattern）"
    kill "$pid" 2>/dev/null || true
    killed=$((killed + 1))
  done
}

kill_pattern "$ROOT/expohub-backend.*uvicorn|uvicorn.*app\.main:app"
kill_pattern "$ROOT/expo-hub-frontend.*vite|vite.*--port $FRONTEND_PORT"

if command -v lsof >/dev/null 2>&1; then
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    for pid in $pids; do
      step "结束占用端口 $port 的进程 $pid"
      kill "$pid" 2>/dev/null || true
      killed=$((killed + 1))
    done
  done
fi

sleep 1
if [ "$killed" -eq 0 ]; then
  warn "未发现运行中的 ExpoHub 服务（端口 $BACKEND_PORT / $FRONTEND_PORT 均无监听）"
else
  ok "已结束 $killed 个进程"
  ok "端口 $BACKEND_PORT / $FRONTEND_PORT 已释放"
fi
echo
