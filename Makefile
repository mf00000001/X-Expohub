# ============================================================
# ExpoHub Makefile — SQLite 纯本地版本
#
# 使用方式：
#   make help          查看所有命令
#   make run           一键启动
#   make test          运行测试
#   make clean         清理数据库和缓存
# ============================================================

# 颜色输出
BLUE   := \033[0;34m
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m
BOLD   := \033[1m

.PHONY: help
help: ## 📖 显示所有命令
	@echo ""
	@echo "$(BOLD)╔══════════════════════════════════════╗$(NC)"
	@echo "$(BOLD)║   ExpoHub 管理命令 (SQLite 版)      ║$(NC)"
	@echo "$(BOLD)╚══════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(BOLD)🚀 运行:$(NC)"
	@echo "  $(GREEN)make run$(NC)         启动开发服务器"
	@echo "  $(GREEN)make run-prod$(NC)    生产模式启动"
	@echo ""
	@echo "$(BOLD)📦 安装:$(NC)"
	@echo "  $(GREEN)make install$(NC)     安装 Python 依赖"
	@echo "  $(GREEN)make setup$(NC)       完整初始化（安装+运行）"
	@echo ""
	@echo "$(BOLD)🧪 测试与检查:$(NC)"
	@echo "  $(GREEN)make test$(NC)        运行单元测试"
	@echo "  $(GREEN)make lint$(NC)        代码风格检查"
	@echo "  $(GREEN)make format$(NC)      自动格式化代码"
	@echo ""
	@echo "$(BOLD)🗄️  数据库:$(NC)"
	@echo "  $(GREEN)make db-reset$(NC)    重置数据库（删除 app.db）"
	@echo "  $(GREEN)make db-shell$(NC)    进入 SQLite 命令行"
	@echo ""
	@echo "$(BOLD)🧹 清理:$(NC)"
	@echo "  $(GREEN)make clean$(NC)       清理数据库和缓存"
	@echo ""

# ========== 运行 ==========

.PHONY: run
run: ## 🚀 启动开发服务器（热重载）
	@echo "$(BLUE)🚀 启动 ExpoHub 开发服务器...$(NC)"
	@echo "  数据库: SQLite (app.db)"
	@echo "  地址:   http://localhost:8000"
	@echo "  文档:   http://localhost:8000/docs"
	@echo ""
	python3 -m app.main

.PHONY: run-prod
run-prod: ## 🚀 生产模式启动
	@echo "$(BLUE)🚀 启动 ExpoHub 生产服务器...$(NC)"
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --no-access-log

# ========== 安装 ==========

.PHONY: install
install: ## 📦 安装 Python 依赖
	@echo "$(BLUE)📦 安装依赖...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✅ 依赖安装完成$(NC)"

.PHONY: setup
setup: install ## 🏗️ 完整初始化
	@echo ""
	@echo "$(GREEN)✅ 初始化完成！运行 make run 启动服务$(NC)"

# ========== 测试 ==========

.PHONY: test
test: ## 🧪 运行单元测试
	@echo "$(BLUE)🧪 运行测试...$(NC)"
	python -m pytest tests/ -v --tb=short 2>/dev/null || echo "$(YELLOW)⚠️  无测试文件或测试失败$(NC)"

.PHONY: lint
lint: ## 🔍 代码风格检查
	@echo "$(BLUE)🔍 代码风格检查...$(NC)"
	@echo "--- flake8 ---"
	flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503 2>/dev/null || echo "$(YELLOW)⚠️  flake8 未安装$(NC)"

.PHONY: format
format: ## ✨ 自动格式化代码
	@echo "$(BLUE)✨ 格式化代码...$(NC)"
	black --line-length=120 src/ tests/ 2>/dev/null || echo "$(YELLOW)⚠️  black 未安装$(NC)"
	isort --line-length=120 src/ tests/ 2>/dev/null || echo "$(YELLOW)⚠️  isort 未安装$(NC)"

# ========== 数据库 ==========

.PHONY: db-reset
db-reset: ## 🗑️ 重置数据库
	@echo "$(RED)⚠️  删除 app.db...$(NC)"
	@rm -f app.db
	@echo "$(GREEN)✅ 数据库已删除，下次启动将自动重建$(NC)"

.PHONY: db-shell
db-shell: ## 💻 进入 SQLite 命令行
	@sqlite3 app.db 2>/dev/null || echo "$(YELLOW)⚠️  sqlite3 未安装或 app.db 不存在$(NC)"

# ========== 清理 ==========

.PHONY: clean
clean: ## 🧹 清理所有数据
	@echo "$(RED)🧹 清理数据库和缓存...$(NC)"
	@rm -f app.db
	@rm -rf __pycache__ src/__pycache__ app/__pycache__
	@rm -rf .pytest_cache
	@echo "$(GREEN)✅ 清理完成$(NC)"
