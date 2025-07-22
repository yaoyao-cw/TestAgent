#!/bin/bash
# TestAgent 部署脚本

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

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p data/vectordb
    mkdir -p data/documents
    mkdir -p data/cache
    mkdir -p logs
    mkdir -p config
    mkdir -p backups
    mkdir -p nginx/logs
    
    log_success "目录创建完成"
}

# 复制配置文件
setup_config() {
    log_info "设置配置文件..."
    
    # 复制示例配置文件
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_info "已复制 .env.example 到 .env，请根据需要修改配置"
        else
            log_warning ".env.example 文件不存在"
        fi
    fi
    
    if [ ! -f config/config.yaml ]; then
        if [ -f config/config.example.yaml ]; then
            cp config/config.example.yaml config/config.yaml
            log_info "已复制配置示例文件"
        fi
    fi
    
    if [ ! -f config/mcp_servers.json ]; then
        if [ -f config/mcp_servers.example.json ]; then
            cp config/mcp_servers.example.json config/mcp_servers.json
            log_info "已复制MCP服务器配置示例文件"
        fi
    fi
    
    log_success "配置文件设置完成"
}

# 构建镜像
build_images() {
    log_info "构建Docker镜像..."
    
    docker-compose build --no-cache
    
    log_success "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    # 启动基础服务
    docker-compose up -d redis chroma
    
    # 等待基础服务启动
    log_info "等待基础服务启动..."
    sleep 10
    
    # 启动主应用
    docker-compose up -d testagent
    
    # 等待主应用启动
    log_info "等待主应用启动..."
    sleep 15
    
    # 启动其他服务
    docker-compose up -d nginx prometheus grafana
    
    log_success "所有服务已启动"
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    # 检查容器状态
    docker-compose ps
    
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

# 显示访问信息
show_access_info() {
    log_success "部署完成！"
    echo
    echo "访问地址："
    echo "  - 主应用: http://localhost:8000"
    echo "  - API文档: http://localhost:8000/docs"
    echo "  - 监控仪表板: http://localhost:8000/static/monitoring.html"
    echo "  - Grafana: http://localhost:3000 (admin/admin123)"
    echo "  - Prometheus: http://localhost:9090"
    echo
    echo "管理命令："
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
    echo "  - 查看状态: docker-compose ps"
}

# 清理函数
cleanup() {
    log_info "清理资源..."
    docker-compose down
    docker system prune -f
    log_success "清理完成"
}

# 主函数
main() {
    case "${1:-deploy}" in
        "deploy")
            log_info "开始部署 TestAgent..."
            check_dependencies
            create_directories
            setup_config
            build_images
            start_services
            check_services
            show_access_info
            ;;
        "start")
            log_info "启动 TestAgent 服务..."
            docker-compose up -d
            check_services
            show_access_info
            ;;
        "stop")
            log_info "停止 TestAgent 服务..."
            docker-compose down
            log_success "服务已停止"
            ;;
        "restart")
            log_info "重启 TestAgent 服务..."
            docker-compose restart
            check_services
            log_success "服务已重启"
            ;;
        "status")
            log_info "检查服务状态..."
            docker-compose ps
            check_services
            ;;
        "logs")
            docker-compose logs -f "${2:-}"
            ;;
        "cleanup")
            cleanup
            ;;
        "help")
            echo "用法: $0 [命令]"
            echo
            echo "命令:"
            echo "  deploy   - 完整部署 (默认)"
            echo "  start    - 启动服务"
            echo "  stop     - 停止服务"
            echo "  restart  - 重启服务"
            echo "  status   - 检查状态"
            echo "  logs     - 查看日志"
            echo "  cleanup  - 清理资源"
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
trap 'log_warning "部署被中断"; exit 1' INT TERM

# 执行主函数
main "$@"