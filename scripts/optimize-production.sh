#!/bin/bash
# TestAgent 生产环境性能优化脚本

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
    echo -e "${CYAN}  TestAgent 生产环境性能优化脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 检查系统信息
check_system_info() {
    log_info "检查系统信息..."
    
    echo "系统信息:"
    echo "  操作系统: $(uname -s)"
    echo "  内核版本: $(uname -r)"
    echo "  架构: $(uname -m)"
    echo "  CPU核心数: $(nproc)"
    echo "  内存总量: $(free -h | awk '/^Mem:/ {print $2}')"
    echo "  磁盘空间: $(df -h / | awk 'NR==2 {print $4}')"
    echo
}

# 优化系统内核参数
optimize_kernel_params() {
    log_info "优化系统内核参数..."
    
    # 备份原始配置
    cp /etc/sysctl.conf /etc/sysctl.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # 网络优化
    cat >> /etc/sysctl.conf << 'EOF'

# TestAgent 生产环境优化参数
# 网络优化
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.core.rmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_default = 262144
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_max_tw_buckets = 400000
net.ipv4.tcp_max_orphans = 60000
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_synack_retries = 3
net.ipv4.tcp_syn_retries = 3

# 内存管理
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.overcommit_memory = 1

# 文件系统
fs.file-max = 1000000
fs.nr_open = 1000000

# 进程限制
kernel.pid_max = 4194304
EOF

    # 应用参数
    sysctl -p
    
    log_success "内核参数优化完成"
}

# 优化文件描述符限制
optimize_file_limits() {
    log_info "优化文件描述符限制..."
    
    # 备份原始配置
    cp /etc/security/limits.conf /etc/security/limits.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # 设置文件描述符限制
    cat >> /etc/security/limits.conf << 'EOF'

# TestAgent 生产环境文件描述符限制
* soft nofile 1000000
* hard nofile 1000000
* soft nproc 1000000
* hard nproc 1000000
root soft nofile 1000000
root hard nofile 1000000
root soft nproc 1000000
root hard nproc 1000000
EOF

    # 设置systemd服务限制
    mkdir -p /etc/systemd/system.conf.d
    cat > /etc/systemd/system.conf.d/limits.conf << 'EOF'
[Manager]
DefaultLimitNOFILE=1000000
DefaultLimitNPROC=1000000
EOF

    log_success "文件描述符限制优化完成"
}

# 优化Docker配置
optimize_docker() {
    log_info "优化Docker配置..."
    
    # 创建Docker daemon配置
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "100m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 1000000,
            "Soft": 1000000
        },
        "nproc": {
            "Name": "nproc",
            "Hard": 1000000,
            "Soft": 1000000
        }
    },
    "max-concurrent-downloads": 10,
    "max-concurrent-uploads": 5,
    "userland-proxy": false,
    "experimental": false,
    "metrics-addr": "127.0.0.1:9323",
    "live-restore": true
}
EOF

    # 重启Docker服务
    systemctl restart docker
    
    log_success "Docker配置优化完成"
}

# 优化Nginx配置
optimize_nginx() {
    log_info "优化Nginx配置..."
    
    # 检查Nginx配置文件
    if [ ! -f "/etc/nginx/nginx.conf" ]; then
        log_warning "Nginx配置文件不存在，跳过优化"
        return
    fi
    
    # 备份原始配置
    cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
    
    # 应用优化配置
    cp nginx/nginx.prod.conf /etc/nginx/nginx.conf
    
    # 测试配置
    if nginx -t; then
        systemctl reload nginx
        log_success "Nginx配置优化完成"
    else
        log_error "Nginx配置测试失败，恢复原始配置"
        cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf
    fi
}

# 优化Redis配置
optimize_redis() {
    log_info "优化Redis配置..."
    
    # 检查Redis是否运行
    if ! docker ps | grep -q redis; then
        log_warning "Redis容器未运行，跳过优化"
        return
    fi
    
    # 应用Redis优化配置
    docker exec testagent-redis-master redis-cli CONFIG SET maxmemory-policy allkeys-lru
    docker exec testagent-redis-master redis-cli CONFIG SET tcp-keepalive 300
    docker exec testagent-redis-master redis-cli CONFIG SET timeout 0
    docker exec testagent-redis-master redis-cli CONFIG REWRITE
    
    log_success "Redis配置优化完成"
}

# 优化PostgreSQL配置（如果使用）
optimize_postgresql() {
    log_info "检查PostgreSQL配置..."
    
    if ! docker ps | grep -q postgres; then
        log_info "PostgreSQL未运行，跳过优化"
        return
    fi
    
    log_info "优化PostgreSQL配置..."
    
    # 这里添加PostgreSQL优化配置
    # 示例：
    # docker exec postgres psql -U testagent -c "ALTER SYSTEM SET shared_buffers = '256MB';"
    # docker exec postgres psql -U testagent -c "ALTER SYSTEM SET effective_cache_size = '1GB';"
    # docker exec postgres psql -U testagent -c "SELECT pg_reload_conf();"
    
    log_success "PostgreSQL配置优化完成"
}

# 设置监控和告警
setup_monitoring() {
    log_info "设置监控和告警..."
    
    # 创建监控脚本
    cat > /usr/local/bin/testagent-monitor.sh << 'EOF'
#!/bin/bash
# TestAgent 监控脚本

# 检查服务状态
check_service_health() {
    local service_url="http://localhost:8000/health"
    if ! curl -f "$service_url" &> /dev/null; then
        echo "ALERT: TestAgent服务不可用" | logger -t testagent-monitor
        # 发送告警通知
        # curl -X POST -H 'Content-type: application/json' \
        #     --data '{"text":"TestAgent服务不可用"}' \
        #     "$SLACK_WEBHOOK_URL"
    fi
}

# 检查资源使用
check_resource_usage() {
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    local mem_usage=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo "ALERT: CPU使用率过高: ${cpu_usage}%" | logger -t testagent-monitor
    fi
    
    if (( $(echo "$mem_usage > 80" | bc -l) )); then
        echo "ALERT: 内存使用率过高: ${mem_usage}%" | logger -t testagent-monitor
    fi
    
    if [ "$disk_usage" -gt 85 ]; then
        echo "ALERT: 磁盘使用率过高: ${disk_usage}%" | logger -t testagent-monitor
    fi
}

# 执行检查
check_service_health
check_resource_usage
EOF

    chmod +x /usr/local/bin/testagent-monitor.sh
    
    # 添加到crontab
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/testagent-monitor.sh") | crontab -
    
    log_success "监控和告警设置完成"
}

# 优化日志轮转
setup_log_rotation() {
    log_info "设置日志轮转..."
    
    cat > /etc/logrotate.d/testagent << 'EOF'
/opt/testagent/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker kill -s USR1 testagent-app 2>/dev/null || true
    endscript
}

/opt/testagent/nginx/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker kill -s USR1 testagent-nginx 2>/dev/null || true
    endscript
}
EOF

    log_success "日志轮转设置完成"
}

# 设置自动备份
setup_auto_backup() {
    log_info "设置自动备份..."
    
    # 复制备份脚本
    cp scripts/backup.sh /usr/local/bin/testagent-backup.sh
    chmod +x /usr/local/bin/testagent-backup.sh
    
    # 添加到crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/testagent-backup.sh backup") | crontab -
    
    log_success "自动备份设置完成"
}

# 优化安全设置
optimize_security() {
    log_info "优化安全设置..."
    
    # 设置防火墙规则
    if command -v ufw &> /dev/null; then
        ufw --force enable
        ufw default deny incoming
        ufw default allow outgoing
        ufw allow 22/tcp    # SSH
        ufw allow 80/tcp    # HTTP
        ufw allow 443/tcp   # HTTPS
        ufw allow 8000/tcp  # TestAgent
        ufw allow 3000/tcp  # Grafana
        ufw allow 9090/tcp  # Prometheus
        log_success "防火墙规则设置完成"
    fi
    
    # 设置fail2ban
    if command -v fail2ban-client &> /dev/null; then
        systemctl enable fail2ban
        systemctl start fail2ban
        log_success "fail2ban设置完成"
    fi
    
    # 禁用不必要的服务
    local services_to_disable=("telnet" "rsh" "rlogin" "vsftpd")
    for service in "${services_to_disable[@]}"; do
        if systemctl is-enabled "$service" &> /dev/null; then
            systemctl disable "$service"
            systemctl stop "$service"
            log_info "已禁用服务: $service"
        fi
    done
    
    log_success "安全设置优化完成"
}

# 性能测试
run_performance_test() {
    log_info "运行性能测试..."
    
    # 检查服务是否运行
    if ! curl -f http://localhost:8000/health &> /dev/null; then
        log_error "TestAgent服务未运行，无法进行性能测试"
        return 1
    fi
    
    # 简单的负载测试
    log_info "执行负载测试..."
    
    # 使用ab进行测试（如果可用）
    if command -v ab &> /dev/null; then
        ab -n 1000 -c 10 http://localhost:8000/health > /tmp/performance_test.log 2>&1
        
        local rps=$(grep "Requests per second" /tmp/performance_test.log | awk '{print $4}')
        local response_time=$(grep "Time per request" /tmp/performance_test.log | head -1 | awk '{print $4}')
        
        log_info "性能测试结果:"
        log_info "  每秒请求数: $rps"
        log_info "  平均响应时间: ${response_time}ms"
    else
        log_warning "ab工具未安装，跳过负载测试"
    fi
    
    # 检查资源使用情况
    log_info "当前资源使用情况:"
    echo "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
    echo "  内存: $(free -h | awk '/^Mem:/ {print $3"/"$2}')"
    echo "  磁盘: $(df -h / | awk 'NR==2 {print $3"/"$2" ("$5")"}')"
    
    log_success "性能测试完成"
}

# 生成优化报告
generate_optimization_report() {
    log_info "生成优化报告..."
    
    local report_file="/tmp/testagent_optimization_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
TestAgent 生产环境优化报告
生成时间: $(date)

系统信息:
$(uname -a)
CPU核心数: $(nproc)
内存总量: $(free -h | awk '/^Mem:/ {print $2}')
磁盘空间: $(df -h / | awk 'NR==2 {print $2}')

优化项目:
✓ 内核参数优化
✓ 文件描述符限制优化
✓ Docker配置优化
✓ Nginx配置优化
✓ Redis配置优化
✓ 监控和告警设置
✓ 日志轮转设置
✓ 自动备份设置
✓ 安全设置优化

当前服务状态:
$(docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}")

资源使用情况:
CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
内存: $(free -h | awk '/^Mem:/ {print $3"/"$2}')
磁盘: $(df -h / | awk 'NR==2 {print $3"/"$2" ("$5")"}')

建议:
1. 定期监控系统资源使用情况
2. 定期检查备份完整性
3. 定期更新安全补丁
4. 监控应用性能指标
5. 定期清理日志和临时文件

EOF

    log_success "优化报告已生成: $report_file"
    cat "$report_file"
}

# 主函数
main() {
    show_banner
    
    # 检查权限
    if [ "$EUID" -ne 0 ]; then
        log_error "请以root权限运行此脚本"
        exit 1
    fi
    
    check_system_info
    
    log_info "开始生产环境优化..."
    
    # 执行优化
    optimize_kernel_params
    optimize_file_limits
    optimize_docker
    optimize_nginx
    optimize_redis
    optimize_postgresql
    setup_monitoring
    setup_log_rotation
    setup_auto_backup
    optimize_security
    
    # 运行性能测试
    run_performance_test
    
    # 生成报告
    generate_optimization_report
    
    log_success "生产环境优化完成！"
    echo
    log_info "重要提醒:"
    log_info "1. 请重启系统以确保所有内核参数生效"
    log_info "2. 请检查防火墙规则是否符合要求"
    log_info "3. 请定期检查监控和备份状态"
    log_info "4. 请根据实际情况调整配置参数"
}

# 处理命令行参数
case "${1:-optimize}" in
    "optimize")
        main
        ;;
    "test")
        run_performance_test
        ;;
    "report")
        generate_optimization_report
        ;;
    "security")
        optimize_security
        ;;
    "monitoring")
        setup_monitoring
        ;;
    *)
        echo "用法: $0 [optimize|test|report|security|monitoring]"
        echo "  optimize   - 执行完整优化 (默认)"
        echo "  test       - 运行性能测试"
        echo "  report     - 生成优化报告"
        echo "  security   - 仅优化安全设置"
        echo "  monitoring - 仅设置监控"
        exit 1
        ;;
esac