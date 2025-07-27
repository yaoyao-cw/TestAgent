#!/bin/bash
# TestAgent Linux/macOS 安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示横幅
show_banner() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}    TestAgent Linux/macOS 安装脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 检测系统信息
detect_system() {
    OS=$(uname -s)
    ARCH=$(uname -m)
    
    case $OS in
        Linux*)
            PLATFORM="Linux"
            ;;
        Darwin*)
            PLATFORM="macOS"
            ;;
        *)
            PLATFORM="Unknown"
            ;;
    esac
    
    log_info "操作系统: $PLATFORM"
    log_info "系统架构: $ARCH"
    
    # 检测Linux发行版
    if [ "$PLATFORM" = "Linux" ]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            DISTRO=$NAME
            log_info "Linux发行版: $DISTRO"
        fi
    fi
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    local missing_deps=()
    
    # 检查Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_success "Python版本: $PYTHON_VERSION"
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
        if [[ $PYTHON_VERSION == 3.* ]]; then
            log_success "Python版本: $PYTHON_VERSION"
            PYTHON_CMD="python"
        else
            log_error "Python版本过低: $PYTHON_VERSION，需要Python 3.9+"
            missing_deps+=("python3")
        fi
    else
        log_error "Python未安装，需要Python 3.9+"
        missing_deps+=("python3")
    fi
    
    # 检查pip
    if command -v pip3 &> /dev/null; then
        PIP_CMD="pip3"
    elif command -v pip &> /dev/null; then
        PIP_CMD="pip"
    else
        log_error "pip未安装"
        missing_deps+=("python3-pip")
    fi
    
    # 检查Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        log_success "Node.js版本: $NODE_VERSION"
    else
        log_error "Node.js未安装，需要Node.js 18+"
        missing_deps+=("nodejs")
    fi
    
    # 检查npm
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        log_success "npm版本: $NPM_VERSION"
    else
        log_error "npm未安装"
        missing_deps+=("npm")
    fi
    
    # 检查Git (可选)
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version)
        log_success "Git版本: $GIT_VERSION"
    else
        log_warning "Git未安装，建议安装以获得更好的开发体验"
    fi
    
    # 检查Docker (可选)
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        log_success "Docker版本: $DOCKER_VERSION"
        DOCKER_AVAILABLE=true
    else
        log_warning "Docker未安装，将使用本地模式"
        DOCKER_AVAILABLE=false
    fi
    
    # 检查docker-compose (可选)
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        log_success "Docker Compose版本: $COMPOSE_VERSION"
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version)
        log_success "Docker Compose版本: $COMPOSE_VERSION"
    else
        if [ "$DOCKER_AVAILABLE" = true ]; then
            log_warning "Docker Compose未安装"
        fi
    fi
    
    # 如果有缺失的依赖，提供安装建议
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "缺失以下依赖: ${missing_deps[*]}"
        echo
        log_info "安装建议:"
        
        if [ "$PLATFORM" = "Linux" ]; then
            if command -v apt-get &> /dev/null; then
                echo "  sudo apt-get update && sudo apt-get install ${missing_deps[*]}"
            elif command -v yum &> /dev/null; then
                echo "  sudo yum install ${missing_deps[*]}"
            elif command -v dnf &> /dev/null; then
                echo "  sudo dnf install ${missing_deps[*]}"
            elif command -v pacman &> /dev/null; then
                echo "  sudo pacman -S ${missing_deps[*]}"
            fi
        elif [ "$PLATFORM" = "macOS" ]; then
            if command -v brew &> /dev/null; then
                echo "  brew install ${missing_deps[*]}"
            else
                echo "  请先安装Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo "  然后运行: brew install ${missing_deps[*]}"
            fi
        fi
        
        echo
        read -p "是否继续安装？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 创建项目目录
create_directories() {
    log_info "创建项目目录..."
    
    local directories=(
        "data/vectordb"
        "data/documents"
        "data/cache"
        "logs"
        "config"
        "backups"
        "temp"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        log_success "创建目录: $dir"
    done
}

# 设置配置文件
setup_config() {
    log_info "设置配置文件..."
    
    # 复制示例配置文件
    local config_files=(
        ".env.example:.env"
        "config/config.example.yaml:config/config.yaml"
        "config/mcp_servers.example.json:config/mcp_servers.json"
    )
    
    for config in "${config_files[@]}"; do
        IFS=':' read -r source target <<< "$config"
        if [ ! -f "$target" ]; then
            if [ -f "$source" ]; then
                cp "$source" "$target"
                log_success "创建配置文件: $target"
            else
                log_warning "示例配置文件不存在: $source"
            fi
        else
            log_info "配置文件已存在: $target"
        fi
    done
    
    # 创建默认.env文件（如果示例文件不存在）
    if [ ! -f ".env" ] && [ ! -f ".env.example" ]; then
        cat > .env << EOF
# TestAgent Linux/macOS 配置
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
REDIS_URL=redis://localhost:6379/0
VECTOR_DB_PATH=./data/vectordb
LOG_FILE=./logs/testagent.log
EOF
        log_success "创建默认 .env 配置文件"
    fi
}

# 创建Python虚拟环境
create_virtual_env() {
    log_info "创建Python虚拟环境..."
    
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
        log_success "Python虚拟环境创建成功"
    else
        log_warning "Python虚拟环境已存在"
    fi
}

# 安装Python依赖
install_python_deps() {
    log_info "安装Python依赖..."
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装核心依赖
    local core_deps=(
        "fastapi>=0.104.0"
        "uvicorn[standard]>=0.24.0"
        "pydantic>=2.5.0"
        "pydantic-settings>=2.0.0"
        "python-dotenv>=1.0.0"
        "PyYAML>=6.0.0"
    )
    
    pip install "${core_deps[@]}"
    log_success "核心Python依赖安装完成"
    
    # 尝试安装完整依赖
    if [ -f "requirements.txt" ]; then
        log_info "安装完整依赖包..."
        if pip install -r requirements.txt; then
            log_success "完整依赖安装成功"
        else
            log_warning "部分依赖安装失败，但核心功能可用"
        fi
    fi
}

# 安装前端依赖
install_frontend_deps() {
    log_info "安装前端依赖..."
    
    if [ -d "frontend" ]; then
        cd frontend
        npm install
        if [ $? -eq 0 ]; then
            log_success "前端依赖安装完成"
        else
            log_error "前端依赖安装失败"
            cd ..
            exit 1
        fi
        cd ..
    else
        log_warning "前端目录不存在，跳过前端依赖安装"
    fi
}

# 创建启动脚本
create_startup_scripts() {
    log_info "创建启动脚本..."
    
    # 创建开发环境启动脚本
    cat > start-dev.sh << 'EOF'
#!/bin/bash
# TestAgent 开发环境启动脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}启动TestAgent开发环境...${NC}"

# 激活虚拟环境
source venv/bin/activate

# 启动后端服务
if [ -f "run_simple_server.py" ]; then
    echo -e "${CYAN}使用简化版API服务器...${NC}"
    python run_simple_server.py &
    BACKEND_PID=$!
elif [ -f "run_api_server.py" ]; then
    echo -e "${CYAN}使用完整版API服务器...${NC}"
    python run_api_server.py &
    BACKEND_PID=$!
else
    echo "错误: 找不到服务器启动脚本"
    exit 1
fi

# 等待后端服务启动
sleep 5

# 启动前端服务
if [ -d "frontend" ]; then
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
fi

echo -e "${GREEN}服务已启动:${NC}"
echo -e "${CYAN}  - 后端API: http://localhost:8000${NC}"
echo -e "${CYAN}  - 前端界面: http://localhost:3000${NC}"
echo -e "${YELLOW}按Ctrl+C停止服务...${NC}"

# 等待中断信号
trap 'echo "停止服务..."; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

wait
EOF
    chmod +x start-dev.sh
    
    # 创建生产环境启动脚本（如果Docker可用）
    if [ "$DOCKER_AVAILABLE" = true ]; then
        cat > start-prod.sh << 'EOF'
#!/bin/bash
# TestAgent 生产环境启动脚本

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}启动TestAgent生产环境...${NC}"

docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}服务已启动:${NC}"
    echo -e "${CYAN}  - 主应用: http://localhost:8000${NC}"
    echo -e "${CYAN}  - API文档: http://localhost:8000/docs${NC}"
    echo -e "${CYAN}  - 监控面板: http://localhost:3000${NC}"
else
    echo "错误: 生产环境启动失败"
    exit 1
fi
EOF
        chmod +x start-prod.sh
    fi
    
    # 创建停止脚本
    cat > stop.sh << 'EOF'
#!/bin/bash
# TestAgent 停止脚本

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}停止TestAgent服务...${NC}"

# 停止Python进程
pkill -f "python.*run_.*_server.py" 2>/dev/null || true

# 停止Node.js进程
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true

# 停止Docker容器
docker-compose down 2>/dev/null || true

echo -e "${GREEN}所有服务已停止${NC}"
EOF
    chmod +x stop.sh
    
    log_success "启动脚本创建完成"
}

# 创建Makefile
create_makefile() {
    log_info "创建Makefile..."
    
    cat > Makefile << 'EOF'
# TestAgent Makefile

.PHONY: help install dev prod stop status logs clean test format lint

# 默认目标
help:
	@echo "TestAgent 可用命令:"
	@echo "  make install  - 安装依赖"
	@echo "  make dev      - 启动开发环境"
	@echo "  make prod     - 启动生产环境"
	@echo "  make stop     - 停止所有服务"
	@echo "  make status   - 检查服务状态"
	@echo "  make logs     - 查看日志"
	@echo "  make test     - 运行测试"
	@echo "  make format   - 格式化代码"
	@echo "  make lint     - 代码检查"
	@echo "  make clean    - 清理环境"

# 安装依赖
install:
	@echo "安装依赖..."
	@./scripts/install.sh

# 启动开发环境
dev:
	@echo "启动开发环境..."
	@./start-dev.sh

# 启动生产环境
prod:
	@echo "启动生产环境..."
	@if [ -f start-prod.sh ]; then ./start-prod.sh; else echo "Docker不可用，请使用 make dev"; fi

# 停止服务
stop:
	@./stop.sh

# 检查服务状态
status:
	@echo "检查服务状态..."
	@curl -s http://localhost:8000/health >/dev/null && echo "后端服务: 运行中" || echo "后端服务: 未运行"
	@curl -s http://localhost:3000 >/dev/null && echo "前端服务: 运行中" || echo "前端服务: 未运行"
	@docker-compose ps 2>/dev/null || echo "Docker服务: 未运行"

# 查看日志
logs:
	@echo "应用日志:"
	@tail -n 50 logs/testagent.log 2>/dev/null || echo "日志文件不存在"
	@echo "Docker日志:"
	@docker-compose logs --tail=50 2>/dev/null || echo "Docker日志不可用"

# 运行测试
test:
	@echo "运行测试..."
	@source venv/bin/activate && python -m pytest tests/ -v

# 格式化代码
format:
	@echo "格式化代码..."
	@source venv/bin/activate && python -m black src/ tests/
	@source venv/bin/activate && python -m isort src/ tests/

# 代码检查
lint:
	@echo "代码检查..."
	@source venv/bin/activate && python -m flake8 src/ tests/
	@source venv/bin/activate && python -m mypy src/

# 清理环境
clean:
	@echo "清理环境..."
	@./stop.sh
	@docker system prune -f 2>/dev/null || true
	@rm -rf __pycache__ .pytest_cache .mypy_cache
	@find . -name "*.pyc" -delete
	@echo "清理完成"
EOF
    
    log_success "Makefile创建完成"
}

# 设置权限
set_permissions() {
    log_info "设置文件权限..."
    
    # 设置脚本执行权限
    chmod +x scripts/*.sh 2>/dev/null || true
    chmod +x *.sh 2>/dev/null || true
    
    # 设置日志目录权限
    chmod 755 logs 2>/dev/null || true
    
    log_success "文件权限设置完成"
}

# 主安装函数
main() {
    show_banner
    
    # 检测系统信息
    detect_system
    
    # 检查依赖
    check_dependencies
    
    # 创建目录
    create_directories
    
    # 设置配置文件
    setup_config
    
    # 创建Python虚拟环境
    create_virtual_env
    
    # 安装Python依赖
    install_python_deps
    
    # 安装前端依赖
    install_frontend_deps
    
    # 创建启动脚本
    create_startup_scripts
    
    # 创建Makefile
    create_makefile
    
    # 设置权限
    set_permissions
    
    # 显示完成信息
    echo
    log_success "========================================"
    log_success "        安装完成！"
    log_success "========================================"
    echo
    log_info "使用方法:"
    log_info "  - 开发环境: ./start-dev.sh 或 make dev"
    if [ "$DOCKER_AVAILABLE" = true ]; then
        log_info "  - 生产环境: ./start-prod.sh 或 make prod"
    fi
    log_info "  - 停止服务: ./stop.sh 或 make stop"
    log_info "  - 查看帮助: make help"
    echo
    log_info "访问地址:"
    log_info "  - 后端API: http://localhost:8000"
    log_info "  - API文档: http://localhost:8000/docs"
    log_info "  - 前端界面: http://localhost:3000"
    echo
    log_info "配置文件:"
    log_info "  - 主配置: .env"
    log_info "  - 应用配置: config/config.yaml"
    log_info "  - MCP配置: config/mcp_servers.json"
    echo
}

# 执行主函数
main "$@"