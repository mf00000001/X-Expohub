@echo off
REM ===== ExpoHub 后端虚拟环境一键搭建 (Windows) =====
cd /d "%~dp0.."
echo === 创建虚拟环境 .venv ===
python -m venv .venv
echo === 安装后端依赖 (固定版本) ===
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r expohub-backend\requirements.txt
echo.
echo [OK] 环境搭建完成!
echo      启动后端: scripts\run_backend.bat
echo      或手动:   cd expohub-backend ^&^& python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
pause
