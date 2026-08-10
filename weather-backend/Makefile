# ============================================================
# 天气查询平台 - Makefile
# ============================================================

.PHONY: help install run dev docker-up docker-down migrate test lint clean

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── 开发环境 ──

install: ## 安装依赖
	pip install -r requirements.txt

run: ## 启动开发服务器
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev: ## 开发模式启动（含热重载）
	DEBUG=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# ── Docker ──

docker-up: ## 启动所有 Docker 服务
	docker compose up -d app db redis

docker-down: ## 停止所有 Docker 服务
	docker compose down

docker-build: ## 重新构建镜像
	docker compose build --no-cache

docker-logs: ## 查看日志
	docker compose logs -f app

# ── 数据库 ──

migrate-init: ## 初始化 Alembic
	alembic init -t async alembic

migrate-create: ## 创建迁移文件（需指定 message）
	alembic revision --autogenerate -m "$(message)"

migrate-up: ## 升级到最新版本
	alembic upgrade head

migrate-down: ## 回滚一个版本
	alembic downgrade -1

db-init: ## 初始化数据库（创建表 + 导入城市数据）
	@echo "初始化数据库..."
	@docker compose exec db psql -U weather -d weather_db -f /docker-entrypoint-initdb.d/01-init.sql

# ── 测试 ──

test: ## 运行所有测试
	pytest tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	pytest tests/ -v --cov=app --cov-report=html

# ── 代码质量 ──

lint: ## 代码检查
	ruff check app/

format: ## 代码格式化
	ruff format app/

# ── 清理 ──

clean: ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage
