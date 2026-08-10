# ============================================
# Stage 1: 依赖安装
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装编译依赖（bcrypt 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: 运行环境
# ============================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# 安装运行时依赖（健康检查用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /root/.local /root/.local

# 复制应用代码
COPY src/ ./src/
COPY .env ./

# 设置 PATH 以包含用户安装的包
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 创建非 root 用户运行应用
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
