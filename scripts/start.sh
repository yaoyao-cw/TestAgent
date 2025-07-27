#!/bin/bash
# TestAgent Linux/macOS 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 全局变量
COMMAND="${1:-dev}"
SERVICE="${2:-}"
BACKGROUND=false
VERBOSE=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --background|-b)
            BACKGROUND=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            if [ -z "$COMMAND" ]; then
                COMMAND="$1"
            elif [ -z "$SERVICE" ]; then
                SERVICE="$1"
            fi
            shift
            ;;
    esac
done

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

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}[VERBOSE]${NC} $1"
    fi
}

# 显示横幅
show_banner() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}    TestAgent Linux/macOS 启动脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 检查项目环境
check_project_env() {
    if [ ! -d "venv" ]; then
        log_error "虚拟环境不存在，请先运行 ./scripts/install.sh"
        return 1
    fi
    
    if [ ! -f ".env" ]; then
        log_error "配置文件不存在，请先运行 ./scripts/install.sh"
        return 1
    fi
    
    return 0
}

# 检查端口占用
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port &> /dev/null
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep ":$port " &> /dev/null
    else
        # 如果没有可用的工具，假设端口可用
        return 1
    fi
}

# 等待服务启动
wait_for_service() {
    local url=$1
    local timeout=${2:-30}
    local service_name=${3:-"服务"}
    
    log_info "等待 $service_name 启动..."
    
    for ((i=1; i<=timeout; i++)); do
        if curl -s "$url" &> /dev/null; then
            log_success "$service_name 启动成功"
            return 0
        fi
        
        log_verbose "等待 $service_name... ($i/$timeout)"
        sleep 1
    done
    
    log_error "$service_name 启动超时"
    return 1
}

# 启动开发环境
start_dev() {
    log_info "启动开发环境..."
    
    # 检查端口占用
    if check_port 8000; then
        log_warning "端口8000已被占用，尝试停止相关服务..."
        stop_all_services
        sleep 2
    fi
    
    if check_port 3000; then
        log_warning "端口3000已被占用，尝试停止相关服务..."
        stop_all_services
        sleep 2
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 启动后端服务
    log_info "启动后端服务..."
    local backend_script=""
    if [ -f "run_simple_server.py" ]; then
        backend_script="run_simple_server.py"
        log_info "使用简化版API服务器..."
    elif [ -f "run_api_server.py" ]; then
        backend_script="run_api_server.py"
        log_info "使用完整版API服务器..."
    else
        log_error "找不到服务器启动脚本"
        return 1
    fi
    
    if [ "$BACKGROUND" = true ]; then
        nohup python "$backend_script" > logs/backend.log 2>&1 &
        BACKEND_PID=$!
        echo $BACKEND_PID > .backend.pid
    else
        python "$backend_script" &
        BACKEND_PID=$!
    fi
    
    # 等待后端服务启动
    if ! wait_for_service "http://localhost:8000/health" 30 "后端服务"; then
        return 1
    fi
    
    # 启动前端服务
    if [ -d "frontend" ]; then
        log_info "启动前端服务..."
        cd frontend
        if [ "$BACKGROUND" = true ]; then
            nohup npm run dev > ../logs/frontend.log 2>&1 &
            FRONTEND_PID=$!
            echo $FRONTEND_PID > ../.frontend.pid
        else
            npm run dev &
            FRONTEND_PID=$!
        fi
        cd ..
        
        # 等待前端服务启动
        sleep 10
        log_success "前端服务启动中..."
    else
        log_warning "前端目录不存在，仅启动后端服务"
    fi
    
    # 显示访问信息
    show_access_info
    
    if [ "$BACKGROUND" = false ]; then
        echo
        log_info "按Ctrl+C停止服务..."
        
        # 设置信号处理
        trap 'log_info "正在停止服务..."; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit 0' INT TERM
        
        # 等待进程结束
        wait
    fi
    
    return 0
}

# 启动生产环境
start_prod() {
    log_info "启动生产环境..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，无法启动生产环境"
        log_info "请安装Docker或使用开发模式: $0 dev"
        return 1
    fi
    
    # 检查docker-compose文件
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml文件不存在"
        return 1
    fi
    
    # 启动Docker服务
    log_info "启动Docker容器..."
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    elif docker compose version &> /dev/null; then
        docker compose up -d
    else
        log_error "Docker Compose未安装"
        return 1
    fi
    
    if [ $? -eq 0 ]; then
        log_success "生产环境启动成功"
        echo
        log_info "访问地址:"
        log_info "  - 主应用: http://localhost:8000"
        log_info "  - API文档: http://localhost:8000/docs"
        log_info "  - 监控面板: http://localhost:3000"
        echo
        log_info "管理命令:"
        log_info "  - 查看状态: docker-compose ps"
        log_info "  - 查看日志: docker-compose logs -f"
        log_info "  - 停止服务: docker-compose down"
        return 0
    else
        log_error "生产环境启动失败"
        return 1
    fi
}

# 停止所有服务
stop_all_services() {
    log_info "停止所有服务..."
    
    # 停止后台进程
    if [ -f ".backend.pid" ]; then
        local backend_pid=$(cat .backend.pid)
        kill $backend_pid 2>/dev/null && log_success "后端服务已停止"
        rm -f .backend.pid
    fi
    
    if [ -f ".frontend.pid" ]; then
        local frontend_pid=$(cat .frontend.pid)
        kill $frontend_pid 2>/dev/null && log_success "前端服务已停止"
        rm -f .frontend.pid
    fi
    
    # 停止Python进程
    pkill -f "python.*run_.*_server.py" 2>/dev/null && log_success "Python服务已停止"
    
    # 停止Node.js进程
    pkill -f "npm run dev" 2>/dev/null && log_success "Node.js服务已停止"
    pkill -f "node.*vite" 2>/dev/null
    
    # 停止Docker容器
    if command -v docker-compose &> /dev/null; then
        docker-compose down 2>/dev/null && log_success "Docker容器已停止"
    elif docker compose version &> /dev/null 2>&1; then
        docker compose down 2>/dev/null && log_success "Docker容器已停止"
    fi
    
    log_success "所有服务已停止"
}

# 检查服务状态
check_status() {
    log_info "检查服务状态..."
    
    # 检查后端服务
    if curl -s "http://localhost:8000/health" &> /dev/null; then
        log_success "后端服务运行正常 (http://localhost:8000)"
    else
        log_error "后端服务未运行"
    fi
    
    # 检查前端服务
    if curl -s "http://localhost:3000" &> /dev/null; then
        log_success "前端服务运行正常 (http://localhost:3000)"
    else
        log_warning "前端服务未运行或未安装"
    fi
    
    # 检查Docker容器
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps 2>/dev/null | grep -q "Up"; then
            log_info "Docker容器状态:"
            docker-compose ps
        else
            log_info "Docker服务未运行"
        fi
    elif docker compose version &> /dev/null 2>&1; then
        if docker compose ps 2>/dev/null | grep -q "Up"; then
            log_info "Docker容器状态:"
            docker compose ps
        else
            log_info "Docker服务未运行"
        fi
    fi
}

# 显示日志
show_logs() {
    log_info "显示服务日志..."
    
    if [ -n "$SERVICE" ]; then
        case $SERVICE in
            backend)
                if [ -f "logs/backend.log" ]; then
                    tail -f logs/backend.log
                elif [ -f "logs/testagent.log" ]; then
                    tail -f logs/testagent.log
                else
                    log_warning "后端日志文件不存在"
                fi
                ;;
            frontend)
                if [ -f "logs/frontend.log" ]; then
                    tail -f logs/frontend.log
                else
                    log_warning "前端日志文件不存在"
                fi
                ;;
            docker)
                if command -v docker-compose &> /dev/null; then
                    docker-compose logs -f
                elif docker compose version &> /dev/null 2>&1; then
                    docker compose logs -f
                else
                    log_warning "Docker Compose不可用"
                fi
                ;;
            *)
                log_error "未知服务: $SERVICE"
                log_info "可用服务: backend, frontend, docker"
                ;;
        esac
    else
        # 显示所有日志
        if [ -f "logs/testagent.log" ]; then
            log_info "应用日志 (最近50行):"
            tail -n 50 logs/testagent.log
        fi
        
        if [ -f "logs/backend.log" ]; then
            log_info "后端日志 (最近20行):"
            tail -n 20 logs/backend.log
        fi
        
        if [ -f "logs/frontend.log" ]; then
            log_info "前端日志 (最近20行):"
            tail -n 20 logs/frontend.log
        fi
        
        # 显示Docker日志
        if command -v docker-compose &> /dev/null; then
            if docker-compose ps 2>/dev/null | grep -q "Up"; then
                log_info "Docker日志 (最近20行):"
                docker-compose logs --tail=20
            fi
        elif docker compose version &> /dev/null 2>&1; then
            if docker compose ps 2>/dev/null | grep -q "Up"; then
                log_info "Docker日志 (最近20行):"
                docker compose logs --tail=20
            fi
        fi
    fi
}

# 显示访问信息
show_access_info() {
    echo
    log_success "========================================"
    log_success "        服务启动完成！"
    log_success "========================================"
    echo
    log_info "访问地址:"
    log_info "  - 后端API: http://localhost:8000"
    log_info "  - API文档: http://localhost:8000/docs"
    if [ -d "frontend" ]; then
        log_info "  - 前端界面: http://localhost:3000"
    fi
    echo
    log_info "管理命令:"
    log_info "  - 查看状态: $0 status"
    log_info "  - 查看日志: $0 logs"
    log_info "  - 停止服务: $0 stop"
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [命令] [服务] [选项]"
    echo
    echo "命令:"
    echo "  dev      - 启动开发环境 (默认)"
    echo "  prod     - 启动生产环境 (需要Docker)"
    echo "  stop     - 停止所有服务"
    echo "  status   - 检查服务状态"
    echo "  logs     - 查看服务日志"
    echo "  help     - 显示帮助信息"
    echo
    echo "服务 (仅用于logs命令):"
    echo "  backend  - 后端服务日志"
    echo "  frontend - 前端服务日志"
    echo "  docker   - Docker容器日志"
    echo
    echo "选项:"
    echo "  -b, --background  - 后台运行服务"
    echo "  -v, --verbose     - 显示详细输出"
    echo "  -h, --help        - 显示帮助信息"
    echo
    echo "示例:"
    echo "  $0 dev                    # 启动开发环境"
    echo "  $0 dev --background       # 后台启动开发环境"
    echo "  $0 prod                   # 启动生产环境"
    echo "  $0 logs backend           # 查看后端日志"
    echo "  $0 stop                   # 停止服务"
    echo
}

# 主函数
main() {
    show_banner
    
    # 检查项目环境
    if ! check_project_env; then
        exit 1
    fi
    
    # 根据命令执行不同操作
    case $COMMAND in
        dev)
            start_dev
            ;;
        prod)
            start_prod
            ;;
        stop)
            stop_all_services
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs
            ;;
        help)
            show_help
            ;;
        *)
            log_error "未知命令: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main