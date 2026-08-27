#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
echo "=== 创建虚拟环境 .venv ==="
python3 -m venv .venv
echo "=== 激活并安装后端依赖 (固定版本) ==="
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r expohub-backend/requirements.txt
echo
echo "[OK] 环境搭建完成!"
echo "      启动后端: ./scripts/run_backend.sh"
echo "      或手动:   cd expohub-backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload"
