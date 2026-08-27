@echo off
REM ===== 启动 ExpoHub 后端 (http://localhost:8002) =====
cd /d "%~dp0..\expohub-backend"
call ..\.venv\Scripts\activate.bat
echo === 启动 ExpoHub 后端 http://localhost:8002 ===
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
