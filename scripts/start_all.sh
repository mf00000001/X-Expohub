#!/usr/bin/env bash
# ============================================================
#  ExpoHub 一键启动（macOS / Linux）
#  用法：./start_all.sh            启动前后端并打开浏览器
#        ./start_all.sh --no-browser  不打开浏览器
#        ./start_all.sh --bind-host 0.0.0.0  允许局域网访问
#  Ctrl+C 同时停止前后端。
# ============================================================
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/expohub-backend"
FRONTEND_DIR="$ROOT/expo-hub-frontend"
VENV_DIR="$ROOT/.venv"
LOG_DIR="$ROOT/logs"

BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BIND_HOST="127.0.0.1"
OPEN_BROWSER=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-browser) OPEN_BROWSER=0 ;;
    --bind-host) shift; BIND_HOST="${1:-127.0.0.1}" ;;
    --backend-port) shift; BACKEND_PORT="${1:-8002}" ;;
    --frontend-port) shift; FRONTEND_PORT="${1:-5173}" ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
  shift
done

BACKEND_URL="http://127.0.0.1:$BACKEND_PORT/"
DOCS_URL="http://127.0.0.1:$BACKEND_PORT/docs"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT/"

ok()   { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
step() { printf '  \033[90m[..]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[!!]\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m[XX]\033[0m %s\n' "$1"; }

BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  echo
  step "正在停止服务 ..."
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  wait 2>/dev/null
  ok "已停止"
  exit 0
}
trap cleanup INT TERM

wait_http() {
  local url="$1" name="$2" i=0 timeout="${3:-120}"
  step "$name 启动中，等待 $url 就绪 ..."
  while [ "$i" -lt "$timeout" ]; do
    if curl -fsS -o /dev/null --max-time 3 "$url" 2>/dev/null; then return 0; fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

port_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
  fi
}

echo
echo "  ============================================================"
echo "    ExpoHub 展会撮合平台  ·  一键启动"
echo "  ============================================================"
echo

# ---------- 1/4 依赖 ----------
echo "  1/4 依赖检查"
command -v node >/dev/null 2>&1 || { fail "未找到 Node.js，请安装 Node.js 18+ 后重试"; exit 1; }
ok "Node.js: $(node --version)"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  PY="$(command -v python3 || command -v python || true)"
  [ -n "$PY" ] || { fail "未找到 Python 3，请安装 Python 3.12/3.13 后重试"; exit 1; }
  step "首次运行：创建虚拟环境 .venv（$PY）..."
  "$PY" -m venv "$VENV_DIR" || { fail "虚拟环境创建失败"; exit 1; }
  step "安装后端依赖（固定版本，首次约 1-3 分钟）..."
  "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
  "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$BACKEND_DIR/requirements.txt" \
    || { fail "后端依赖安装失败（pip install -r expohub-backend/requirements.txt）"; exit 1; }
  ok "后端虚拟环境创建完成"
else
  ok "后端虚拟环境已存在"
fi

if [ ! -d "$FRONTEND_DIR/node_modules/vite" ]; then
  step "首次运行：安装前端依赖 npm install ..."
  ( cd "$FRONTEND_DIR" && npm install --no-audit --no-fund ) || { fail "前端依赖安装失败"; exit 1; }
  ok "前端依赖安装完成"
else
  ok "前端依赖已就绪"
fi

# ---------- 2/4 端口 ----------
echo
echo "  2/4 端口检查"
if port_busy "$BACKEND_PORT"; then
  if curl -fsS -o /dev/null --max-time 3 "$BACKEND_URL" 2>/dev/null; then
    warn "后端端口 $BACKEND_PORT 已有 ExpoHub 在运行，直接复用"
    BACKEND_PID=""
    BACKEND_REUSE=1
  else
    fail "端口 $BACKEND_PORT 已被占用，请先运行 ./stop_all.sh 或指定 --backend-port"; exit 1
  fi
else
  BACKEND_REUSE=0
  ok "后端端口 $BACKEND_PORT 空闲"
fi

if port_busy "$FRONTEND_PORT"; then
  if curl -fsS -o /dev/null --max-time 3 "$FRONTEND_URL" 2>/dev/null; then
    warn "前端端口 $FRONTEND_PORT 已有服务在运行，直接复用"
    FRONTEND_REUSE=1
  else
    fail "端口 $FRONTEND_PORT 已被占用，请先运行 ./stop_all.sh 或指定 --frontend-port"; exit 1
  fi
else
  FRONTEND_REUSE=0
  ok "前端端口 $FRONTEND_PORT 空闲"
fi

# ---------- 3/4 启动 ----------
echo
echo "  3/4 启动服务"
mkdir -p "$LOG_DIR"

if [ "$BACKEND_REUSE" -eq 0 ]; then
  ( cd "$BACKEND_DIR" && exec "$VENV_DIR/bin/python" -m uvicorn app.main:app \
      --host "$BIND_HOST" --port "$BACKEND_PORT" ) >"$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
  if ! wait_http "$BACKEND_URL" "后端"; then
    fail "后端未能在 120 秒内就绪，请查看 logs/backend.log"; exit 1
  fi
  ok "后端已就绪  $BACKEND_URL"
else
  ok "后端沿用已在运行的实例"
fi

if [ "$FRONTEND_REUSE" -eq 0 ]; then
  ( cd "$FRONTEND_DIR" && exec npm run dev -- --host "$BIND_HOST" --port "$FRONTEND_PORT" --strictPort ) \
    >"$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  if ! wait_http "$FRONTEND_URL" "前端"; then
    fail "前端未能在 120 秒内就绪，请查看 logs/frontend.log"; exit 1
  fi
  ok "前端已就绪  $FRONTEND_URL"
else
  ok "前端沿用已在运行的实例"
fi

# ---------- 4/4 入口 ----------
echo
echo "  4/4 访问入口"
echo
echo "    前端页面   $FRONTEND_URL"
echo "    接口文档   $DOCS_URL"
echo "    接口根路径 $BACKEND_URL"
echo
echo "    测试账号（用户名 / 密码）"
echo "      admin / admin123            管理员"
echo "      exhibitor_huawei / exh123   展商"
echo "      buyer_li / buyer123         买家"
echo "      organizer_canton / org123   主办方"
echo
echo "    Ctrl+C 关闭服务；日志：logs/backend.log、logs/frontend.log"
echo

if [ "$OPEN_BROWSER" -eq 1 ]; then
  if command -v open >/dev/null 2>&1; then open "$FRONTEND_URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
fi

ok "启动完成，按 Ctrl+C 停止"
wait
