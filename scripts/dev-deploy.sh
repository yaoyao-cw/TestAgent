#!/bin/bash
# TestAgent 开发环境部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 创建开发环境目录
create_dev_directories() {
    log_info "创建开发环境目录..."
    
    mkdir -p data/vectordb
    mkdir -p data/documents
    mkdir -p data/cache
    mkdir -p logs
    mkdir -p config
    
    log_success "开发环境目录创建完成"
}

# 设置开发环境配置
setup_dev_config() {
    log_info "设置开发环境配置..."
    
    # 创建开发环境配置文件
    if [ ! -f .env.dev ]; then
        cat > .env.dev << EOF
# TestAgent 开发环境配置
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
REDIS_URL=redis://localhost:6380/0
VECTOR_DB_PATH=./data/vectordb
LOG_FILE=./logs/testagent.log

# 开发专用设置
ENABLE_METRICS=true
METRICS_PORT=9090
EOF
        log_info "已创建开发环境配置文件 .env.dev"
    fi
    
    log_success "开发环境配置设置完成"
}

# 启动开发环境
start_dev_services() {
    log_info "启动开发环境服务..."
    
    # 使用开发环境配置
    docker-compose -f docker-compose.dev.yml up -d
    
    log_success "开发环境服务已启动"
}

# 检查开发环境服务状态
check_dev_services() {
    log_info "检查开发环境服务状态..."
    
    # 检查容器状态
    docker-compose -f docker-compose.dev.yml ps
    
    # 检查健康状态
    log_info "检查应用健康状态..."
    
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "应用健康检查通过"
            break
        else
            log_info "等待应用启动... ($attempt/$max_attempts)"
            sleep 5
            ((attempt++))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "应用健康检查失败"
        return 1
    fi
}

# 显示开发环境访问信息
show_dev_access_info() {
    log_success "开发环境部署完成！"
    echo
    echo "访问地址："
    echo "  - 主应用: http://localhost:8000"
    echo "  - API文档: http://localhost:8000/docs"
    echo "  - 监控仪表板: http://localhost:8000/static/monitoring.html"
    echo "  - Redis: localhost:6380"
    echo "  - ChromaDB: http://localhost:8002"
    echo
    echo "开发工具："
    echo "  - 热重载已启用，修改代码会自动重启"
    echo "  - 调试模式已启用"
    echo "  - 详细日志已启用"
    echo
    echo "管理命令："
    echo "  - 查看日志: docker-compose -f docker-compose.dev.yml logs -f"
    echo "  - 停止服务: docker-compose -f docker-compose.dev.yml down"
    echo "  - 重启服务: docker-compose -f docker-compose.dev.yml restart"
    echo "  - 进入容器: docker exec -it testagent-dev bash"
}

# 运行测试
run_tests() {
    log_info "运行测试..."
    
    docker-compose -f docker-compose.dev.yml exec testagent-dev python -m pytest tests/ -v
    
    log_success "测试完成"
}

# 代码格式化
format_code() {
    log_info "格式化代码..."
    
    docker-compose -f docker-compose.dev.yml exec testagent-dev python -m black src/ tests/
    docker-compose -f docker-compose.dev.yml exec testagent-dev python -m isort src/ tests/
    
    log_success "代码格式化完成"
}

# 代码检查
lint_code() {
    log_info "代码检查..."
    
    docker-compose -f docker-compose.dev.yml exec testagent-dev python -m flake8 src/ tests/
    docker-compose -f docker-compose.dev.yml exec testagent-dev python -m mypy src/
    
    log_success "代码检查完成"
}

# 主函数
main() {
    case "${1:-dev}" in
        "dev")
            log_info "启动开发环境..."
            check_dependencies
            create_dev_directories
            setup_dev_config
            start_dev_services
            check_dev_services
            show_dev_access_info
            ;;
        "start")
            log_info "启动开发环境服务..."
            docker-compose -f docker-compose.dev.yml up -d
            check_dev_services
            show_dev_access_info
            ;;
        "stop")
            log_info "停止开发环境服务..."
            docker-compose -f docker-compose.dev.yml down
            log_success "开发环境服务已停止"
            ;;
        "restart")
            log_info "重启开发环境服务..."
            docker-compose -f docker-compose.dev.yml restart
            check_dev_services
            log_success "开发环境服务已重启"
            ;;
        "logs")
            docker-compose -f docker-compose.dev.yml logs -f "${2:-}"
            ;;
        "shell")
            docker-compose -f docker-compose.dev.yml exec testagent-dev bash
            ;;
        "test")
            run_tests
            ;;
        "format")
            format_code
            ;;
        "lint")
            lint_code
            ;;
        "build")
            log_info "构建开发环境镜像..."
            docker-compose -f docker-compose.dev.yml build --no-cache
            log_success "开发环境镜像构建完成"
            ;;
        "clean")
            log_info "清理开发环境..."
            docker-compose -f docker-compose.dev.yml down -v
            docker system prune -f
            log_success "开发环境清理完成"
            ;;
        "help")
            echo "用法: $0 [命令]"
            echo
            echo "命令:"
            echo "  dev      - 启动开发环境 (默认)"
            echo "  start    - 启动服务"
            echo "  stop     - 停止服务"
            echo "  restart  - 重启服务"
            echo "  logs     - 查看日志"
            echo "  shell    - 进入容器shell"
            echo "  test     - 运行测试"
            echo "  format   - 格式化代码"
            echo "  lint     - 代码检查"
            echo "  build    - 构建镜像"
            echo "  clean    - 清理环境"
            echo "  help     - 显示帮助"
            ;;
        *)
            log_error "未知命令: $1"
            echo "使用 '$0 help' 查看可用命令"
            exit 1
            ;;
    esac
}

# 捕获中断信号
trap 'log_warning "操作被中断"; exit 1' INT TERM

# 执行主函数
main "$@"