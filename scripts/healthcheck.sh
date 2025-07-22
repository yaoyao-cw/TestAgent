#!/bin/bash
# TestAgent 健康检查脚本

set -e

# 配置
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
TIMEOUT="${TIMEOUT:-30}"
MAX_RETRIES="${MAX_RETRIES:-3}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
}

log_success() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}SUCCESS${NC}: $1"
}

log_warning() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}WARNING${NC}: $1"
}

log_error() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}ERROR${NC}: $1"
}

# 检查HTTP健康状态
check_http_health() {
    local url=$1
    local timeout=$2
    
    if curl -f -s --max-time "$timeout" "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 检查详细健康状态
check_detailed_health() {
    local url=$1
    local timeout=$2
    
    local response
    response=$(curl -f -s --max-time "$timeout" "$url" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        return 0
    else
        return 1
    fi
}

# 检查服务依赖
check_dependencies() {
    log_info "检查服务依赖..."
    
    local all_healthy=true
    
    # 检查Redis
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping > /dev/null 2>&1; then
            log_success "Redis连接正常"
        else
            log_error "Redis连接失败"
            all_healthy=false
        fi
    fi
    
    # 检查ChromaDB
    local chroma_url="${CHROMA_URL:-http://localhost:8001/api/v1/heartbeat}"
    if check_http_health "$chroma_url" 10; then
        log_success "ChromaDB连接正常"
    else
        log_error "ChromaDB连接失败"
        all_healthy=false
    fi
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# 主健康检查函数
main_health_check() {
    local retries=0
    local success=false
    
    log_info "开始健康检查..."
    log_info "检查URL: $HEALTH_URL"
    log_info "超时时间: ${TIMEOUT}秒"
    log_info "最大重试: $MAX_RETRIES次"
    
    while [ $retries -lt $MAX_RETRIES ]; do
        log_info "尝试 $((retries + 1))/$MAX_RETRIES..."
        
        if check_http_health "$HEALTH_URL" "$TIMEOUT"; then
            log_success "应用健康检查通过"
            success=true
            break
        else
            log_warning "健康检查失败，等待重试..."
            retries=$((retries + 1))
            if [ $retries -lt $MAX_RETRIES ]; then
                sleep 5
            fi
        fi
    done
    
    if [ "$success" = true ]; then
        # 显示详细健康信息
        log_info "获取详细健康信息..."
        if ! check_detailed_health "$HEALTH_URL" "$TIMEOUT"; then
            log_warning "无法获取详细健康信息"
        fi
        
        # 检查依赖服务
        if ! check_dependencies; then
            log_warning "部分依赖服务不健康"
            return 1
        fi
        
        log_success "所有健康检查通过"
        return 0
    else
        log_error "健康检查失败，已达到最大重试次数"
        return 1
    fi
}

# 监控模式
monitor_mode() {
    local interval="${MONITOR_INTERVAL:-60}"
    
    log_info "启动监控模式，检查间隔: ${interval}秒"
    
    while true; do
        if main_health_check; then
            log_success "监控检查通过"
        else
            log_error "监控检查失败"
        fi
        
        sleep "$interval"
    done
}

# 等待服务启动
wait_for_service() {
    local max_wait="${MAX_WAIT:-300}"  # 最大等待5分钟
    local wait_time=0
    local interval=5
    
    log_info "等待服务启动，最大等待时间: ${max_wait}秒"
    
    while [ $wait_time -lt $max_wait ]; do
        if check_http_health "$HEALTH_URL" 5; then
            log_success "服务已启动，等待时间: ${wait_time}秒"
            return 0
        fi
        
        log_info "服务尚未就绪，继续等待... (${wait_time}/${max_wait}秒)"
        sleep $interval
        wait_time=$((wait_time + interval))
    done
    
    log_error "服务启动超时"
    return 1
}

# 显示帮助信息
show_help() {
    echo "TestAgent 健康检查脚本"
    echo
    echo "用法: $0 [选项] [命令]"
    echo
    echo "命令:"
    echo "  check     - 执行健康检查 (默认)"
    echo "  monitor   - 监控模式，持续检查"
    echo "  wait      - 等待服务启动"
    echo "  help      - 显示帮助信息"
    echo
    echo "环境变量:"
    echo "  HEALTH_URL          - 健康检查URL (默认: http://localhost:8000/health)"
    echo "  TIMEOUT             - 请求超时时间 (默认: 30秒)"
    echo "  MAX_RETRIES         - 最大重试次数 (默认: 3次)"
    echo "  MONITOR_INTERVAL    - 监控间隔 (默认: 60秒)"
    echo "  MAX_WAIT            - 最大等待时间 (默认: 300秒)"
    echo "  REDIS_HOST          - Redis主机 (默认: localhost)"
    echo "  REDIS_PORT          - Redis端口 (默认: 6379)"
    echo "  CHROMA_URL          - ChromaDB健康检查URL"
    echo
    echo "示例:"
    echo "  $0                                    # 基本健康检查"
    echo "  $0 monitor                            # 监控模式"
    echo "  $0 wait                               # 等待服务启动"
    echo "  HEALTH_URL=http://app:8000/health $0  # 自定义URL"
}

# 主函数
main() {
    case "${1:-check}" in
        "check")
            main_health_check
            ;;
        "monitor")
            monitor_mode
            ;;
        "wait")
            wait_for_service
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 捕获中断信号
trap 'log_warning "健康检查被中断"; exit 1' INT TERM

# 执行主函数
main "$@"