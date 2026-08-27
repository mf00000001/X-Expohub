#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../expohub-backend"
source ../.venv/bin/activate
echo "=== 启动 ExpoHub 后端 http://localhost:8002 ==="
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
