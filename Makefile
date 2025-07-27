# TestAgent Makefile
# 支持Linux和macOS的跨平台构建和管理

.PHONY: help install dev prod stop status logs clean test format lint build docker-build docker-push

# 默认目标
.DEFAULT_GOAL := help

# 颜色定义
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m # No Color

# 项目信息
PROJECT_NAME := testagent
VERSION := $(shell grep -E '^version' pyproject.toml | cut -d'"' -f2 2>/dev/null || echo "1.0.0")
PYTHON := python3
PIP := pip3

# 检测操作系统
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    OS := linux
endif
ifeq ($(UNAME_S),Darwin)
    OS := macos
endif

# 检测架构
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),x86_64)
    ARCH := amd64
endif
ifeq ($(UNAME_M),arm64)
    ARCH := arm64
endif
ifeq ($(UNAME_M),aarch64)
    ARCH := arm64
endif

help: ## 显示帮助信息
	@echo "$(GREEN)TestAgent Makefile - 可用命令:$(NC)"
	@echo ""
	@echo "$(BLUE)安装和设置:$(NC)"
	@echo "  make install     - 安装所有依赖"
	@echo "  make install-dev - 安装开发依赖"
	@echo ""
	@echo "$(BLUE)开发和运行:$(NC)"
	@echo "  make dev         - 启动开发环境"
	@echo "  make prod        - 启动生产环境"
	@echo "  make stop        - 停止所有服务"
	@echo "  make restart     - 重启服务"
	@echo ""
	@echo "$(BLUE)状态和日志:$(NC)"
	@echo "  make status      - 检查服务状态"
	@echo "  make logs        - 查看所有日志"
	@echo "  make logs-backend - 查看后端日志"
	@echo "  make logs-frontend - 查看前端日志"
	@echo "  make logs-docker - 查看Docker日志"
	@echo ""
	@echo "$(BLUE)测试和质量:$(NC)"
	@echo "  make test        - 运行所有测试"
	@echo "  make test-unit   - 运行单元测试"
	@echo "  make test-integration - 运行集成测试"
	@echo "  make format      - 格式化代码"
	@echo "  make lint        - 代码检查"
	@echo "  make type-check  - 类型检查"
	@echo ""
	@echo "$(BLUE)构建和部署:$(NC)"
	@echo "  make build       - 构建应用"
	@echo "  make docker-build - 构建Docker镜像"
	@echo "  make docker-push - 推送Docker镜像"
	@echo ""
	@echo "$(BLUE)清理和维护:$(NC)"
	@echo "  make clean       - 清理临时文件"
	@echo "  make clean-all   - 深度清理"
	@echo "  make update      - 更新依赖"
	@echo ""
	@echo "$(BLUE)系统信息:$(NC)"
	@echo "  操作系统: $(OS)"
	@echo "  架构: $(ARCH)"
	@echo "  版本: $(VERSION)"

# 检查依赖
check-deps:
	@echo "$(BLUE)检查系统依赖...$(NC)"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "$(RED)错误: Python3未安装$(NC)"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "$(RED)错误: Node.js未安装$(NC)"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "$(RED)错误: npm未安装$(NC)"; exit 1; }
	@echo "$(GREEN)依赖检查通过$(NC)"

# 安装依赖
install: check-deps ## 安装所有依赖
	@echo "$(BLUE)安装TestAgent依赖...$(NC)"
	@chmod +x scripts/install.sh
	@./scripts/install.sh
	@echo "$(GREEN)安装完成$(NC)"

install-dev: install ## 安装开发依赖
	@echo "$(BLUE)安装开发依赖...$(NC)"
	@source venv/bin/activate && $(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)开发依赖安装完成$(NC)"

# 创建虚拟环境
venv:
	@if [ ! -d "venv" ]; then \
		echo "$(BLUE)创建Python虚拟环境...$(NC)"; \
		$(PYTHON) -m venv venv; \
		echo "$(GREEN)虚拟环境创建完成$(NC)"; \
	fi

# 启动开发环境
dev: ## 启动开发环境
	@echo "$(BLUE)启动开发环境...$(NC)"
	@chmod +x scripts/start.sh
	@./scripts/start.sh dev

dev-bg: ## 后台启动开发环境
	@echo "$(BLUE)后台启动开发环境...$(NC)"
	@chmod +x scripts/start.sh
	@./scripts/start.sh dev --background

# 启动生产环境
prod: ## 启动生产环境
	@echo "$(BLUE)启动生产环境...$(NC)"
	@chmod +x scripts/start.sh
	@./scripts/start.sh prod

# 停止服务
stop: ## 停止所有服务
	@echo "$(YELLOW)停止所有服务...$(NC)"
	@chmod +x scripts/start.sh
	@./scripts/start.sh stop

# 重启服务
restart: stop dev ## 重启服务

# 检查服务状态
status: ## 检查服务状态
	@echo "$(BLUE)检查服务状态...$(NC)"
	@chmod +x scripts/start.sh
	@./scripts/start.sh status

# 查看日志
logs: ## 查看所有日志
	@chmod +x scripts/start.sh
	@./scripts/start.sh logs

logs-backend: ## 查看后端日志
	@chmod +x scripts/start.sh
	@./scripts/start.sh logs backend

logs-frontend: ## 查看前端日志
	@chmod +x scripts/start.sh
	@./scripts/start.sh logs frontend

logs-docker: ## 查看Docker日志
	@chmod +x scripts/start.sh
	@./scripts/start.sh logs docker

# 运行测试
test: venv ## 运行所有测试
	@echo "$(BLUE)运行所有测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit: venv ## 运行单元测试
	@echo "$(BLUE)运行单元测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/unit/ -v

test-integration: venv ## 运行集成测试
	@echo "$(BLUE)运行集成测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/integration/ -v

test-watch: venv ## 监视模式运行测试
	@echo "$(BLUE)监视模式运行测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/ -v --watch

# 代码格式化
format: venv ## 格式化代码
	@echo "$(BLUE)格式化Python代码...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m black src/ tests/ --line-length=88
	@source venv/bin/activate && $(PYTHON) -m isort src/ tests/ --profile=black
	@echo "$(GREEN)代码格式化完成$(NC)"

# 代码检查
lint: venv ## 代码检查
	@echo "$(BLUE)Python代码检查...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503
	@source venv/bin/activate && $(PYTHON) -m pylint src/ --disable=C0114,C0115,C0116
	@echo "$(GREEN)代码检查完成$(NC)"

# 类型检查
type-check: venv ## 类型检查
	@echo "$(BLUE)Python类型检查...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m mypy src/ --ignore-missing-imports
	@echo "$(GREEN)类型检查完成$(NC)"

# 安全检查
security-check: venv ## 安全检查
	@echo "$(BLUE)安全检查...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m bandit -r src/ -f json -o security-report.json || true
	@source venv/bin/activate && $(PYTHON) -m safety check
	@echo "$(GREEN)安全检查完成$(NC)"

# 构建应用
build: venv ## 构建应用
	@echo "$(BLUE)构建应用...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m build
	@if [ -d "frontend" ]; then \
		echo "$(BLUE)构建前端...$(NC)"; \
		cd frontend && npm run build; \
	fi
	@echo "$(GREEN)构建完成$(NC)"

# Docker构建
docker-build: ## 构建Docker镜像
	@echo "$(BLUE)构建Docker镜像...$(NC)"
	@docker build -t $(PROJECT_NAME):$(VERSION) .
	@docker build -t $(PROJECT_NAME):latest .
	@echo "$(GREEN)Docker镜像构建完成$(NC)"

docker-build-multi: ## 构建多架构Docker镜像
	@echo "$(BLUE)构建多架构Docker镜像...$(NC)"
	@docker buildx build --platform linux/amd64,linux/arm64 -t $(PROJECT_NAME):$(VERSION) -t $(PROJECT_NAME):latest .
	@echo "$(GREEN)多架构Docker镜像构建完成$(NC)"

docker-push: docker-build ## 推送Docker镜像
	@echo "$(BLUE)推送Docker镜像...$(NC)"
	@docker push $(PROJECT_NAME):$(VERSION)
	@docker push $(PROJECT_NAME):latest
	@echo "$(GREEN)Docker镜像推送完成$(NC)"

# 清理
clean: ## 清理临时文件
	@echo "$(YELLOW)清理临时文件...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .coverage htmlcov/ .tox/
	@rm -f security-report.json
	@echo "$(GREEN)清理完成$(NC)"

clean-all: clean stop ## 深度清理
	@echo "$(YELLOW)深度清理...$(NC)"
	@rm -rf venv/
	@rm -rf node_modules/
	@rm -rf frontend/node_modules/
	@rm -rf frontend/dist/
	@rm -rf data/vectordb/*
	@rm -rf data/cache/*
	@rm -rf logs/*.log
	@docker system prune -f 2>/dev/null || true
	@echo "$(GREEN)深度清理完成$(NC)"

# 更新依赖
update: venv ## 更新依赖
	@echo "$(BLUE)更新Python依赖...$(NC)"
	@source venv/bin/activate && $(PIP) install --upgrade pip
	@source venv/bin/activate && $(PIP) install --upgrade -r requirements.txt
	@if [ -f "requirements-dev.txt" ]; then \
		source venv/bin/activate && $(PIP) install --upgrade -r requirements-dev.txt; \
	fi
	@if [ -d "frontend" ]; then \
		echo "$(BLUE)更新前端依赖...$(NC)"; \
		cd frontend && npm update; \
	fi
	@echo "$(GREEN)依赖更新完成$(NC)"

# 健康检查
health-check: ## 健康检查
	@echo "$(BLUE)执行健康检查...$(NC)"
	@curl -f http://localhost:8000/health || { echo "$(RED)后端服务健康检查失败$(NC)"; exit 1; }
	@curl -f http://localhost:3000 >/dev/null 2>&1 || echo "$(YELLOW)前端服务未运行$(NC)"
	@echo "$(GREEN)健康检查完成$(NC)"

# 性能测试
perf-test: ## 性能测试
	@echo "$(BLUE)执行性能测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/performance/ -v
	@echo "$(GREEN)性能测试完成$(NC)"

# 生成文档
docs: venv ## 生成文档
	@echo "$(BLUE)生成API文档...$(NC)"
	@source venv/bin/activate && $(PYTHON) -c "import uvicorn; uvicorn.run('src.server.main:app', host='0.0.0.0', port=8000)" &
	@sleep 5
	@curl http://localhost:8000/docs > docs/api.html
	@pkill -f uvicorn
	@echo "$(GREEN)文档生成完成$(NC)"

# 备份数据
backup: ## 备份数据
	@echo "$(BLUE)备份数据...$(NC)"
	@mkdir -p backups
	@tar -czf backups/backup-$(shell date +%Y%m%d-%H%M%S).tar.gz data/ config/ logs/
	@echo "$(GREEN)数据备份完成$(NC)"

# 恢复数据
restore: ## 恢复数据 (需要指定备份文件: make restore BACKUP=backup-file.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)错误: 请指定备份文件 make restore BACKUP=backup-file.tar.gz$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)恢复数据...$(NC)"
	@tar -xzf backups/$(BACKUP)
	@echo "$(GREEN)数据恢复完成$(NC)"

# 监控
monitor: ## 启动监控
	@echo "$(BLUE)启动监控服务...$(NC)"
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose -f monitoring/docker-compose.yml up -d; \
	else \
		echo "$(YELLOW)Docker Compose不可用，跳过监控启动$(NC)"; \
	fi

# 基准测试
benchmark: venv ## 运行基准测试
	@echo "$(BLUE)运行基准测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/benchmark/ -v --benchmark-only
	@echo "$(GREEN)基准测试完成$(NC)"

# 代码覆盖率报告
coverage: test ## 生成代码覆盖率报告
	@echo "$(BLUE)生成代码覆盖率报告...$(NC)"
	@source venv/bin/activate && coverage html
	@echo "$(GREEN)覆盖率报告已生成到 htmlcov/index.html$(NC)"

# 依赖检查
deps-check: venv ## 检查依赖安全性
	@echo "$(BLUE)检查依赖安全性...$(NC)"
	@source venv/bin/activate && $(PIP) list --outdated
	@source venv/bin/activate && $(PIP) audit
	@echo "$(GREEN)依赖检查完成$(NC)"

# 快速开始
quick-start: install dev ## 快速开始 (安装+启动开发环境)

# CI/CD相关
ci-test: venv ## CI环境测试
	@echo "$(BLUE)CI环境测试...$(NC)"
	@source venv/bin/activate && $(PYTHON) -m pytest tests/ -v --junitxml=test-results.xml --cov=src --cov-report=xml

ci-build: ## CI环境构建
	@echo "$(BLUE)CI环境构建...$(NC)"
	@$(MAKE) format lint type-check security-check test build

# 显示项目信息
info: ## 显示项目信息
	@echo "$(GREEN)TestAgent 项目信息:$(NC)"
	@echo "  项目名称: $(PROJECT_NAME)"
	@echo "  版本: $(VERSION)"
	@echo "  操作系统: $(OS)"
	@echo "  架构: $(ARCH)"
	@echo "  Python: $(shell $(PYTHON) --version 2>/dev/null || echo '未安装')"
	@echo "  Node.js: $(shell node --version 2>/dev/null || echo '未安装')"
	@echo "  Docker: $(shell docker --version 2>/dev/null || echo '未安装')"