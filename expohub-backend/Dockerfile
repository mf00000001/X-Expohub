# ExpoHub 后端镜像（P7）—— 针对 expohub-backend（FastAPI + SQLAlchemy，py3.13）
# 与仓库根目录旧版 Dockerfile(app/ py3.12) 区分：此为当前产品代码的镜像

FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 安装运行依赖（固定版本，来源 expohub-backend/requirements.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app ./app
COPY pytest.ini ./

# 数据库文件目录（SQLite 数据持久化挂载点）
RUN mkdir -p /app/data

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8002/', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
