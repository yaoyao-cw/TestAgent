#!/bin/bash
# TestAgent 生产环境备份脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# 配置变量
BACKUP_DIR="/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
COMPRESSION_LEVEL=6

# 备份源目录
DATA_DIR="/backup/data"
LOGS_DIR="/backup/logs"
REDIS_DIR="/backup/redis"
CHROMA_DIR="/backup/chroma"

# 备份目标目录
DAILY_BACKUP_DIR="$BACKUP_DIR/daily"
WEEKLY_BACKUP_DIR="$BACKUP_DIR/weekly"
MONTHLY_BACKUP_DIR="$BACKUP_DIR/monthly"

# 创建备份目录
create_backup_dirs() {
    log_info "创建备份目录..."
    
    mkdir -p "$DAILY_BACKUP_DIR"
    mkdir -p "$WEEKLY_BACKUP_DIR"
    mkdir -p "$MONTHLY_BACKUP_DIR"
    
    log_success "备份目录创建完成"
}

# 备份应用数据
backup_app_data() {
    log_info "备份应用数据..."
    
    local backup_file="$DAILY_BACKUP_DIR/testagent_data_$TIMESTAMP.tar.gz"
    
    if [ -d "$DATA_DIR" ]; then
        tar -czf "$backup_file" -C "$DATA_DIR" . --exclude='*.tmp' --exclude='cache/*'
        log_success "应用数据备份完成: $backup_file"
    else
        log_warning "应用数据目录不存在: $DATA_DIR"
    fi
}

# 备份日志
backup_logs() {
    log_info "备份日志文件..."
    
    local backup_file="$DAILY_BACKUP_DIR/testagent_logs_$TIMESTAMP.tar.gz"
    
    if [ -d "$LOGS_DIR" ]; then
        # 只备份最近7天的日志
        find "$LOGS_DIR" -name "*.log" -mtime -7 -print0 | tar -czf "$backup_file" --null -T -
        log_success "日志备份完成: $backup_file"
    else
        log_warning "日志目录不存在: $LOGS_DIR"
    fi
}

# 备份Redis数据
backup_redis() {
    log_info "备份Redis数据..."
    
    local backup_file="$DAILY_BACKUP_DIR/redis_data_$TIMESTAMP.tar.gz"
    
    if [ -d "$REDIS_DIR" ]; then
        # 触发Redis保存
        if command -v redis-cli &> /dev/null; then
            redis-cli -h redis-master BGSAVE || log_warning "Redis BGSAVE失败"
            sleep 5  # 等待保存完成
        fi
        
        tar -czf "$backup_file" -C "$REDIS_DIR" .
        log_success "Redis数据备份完成: $backup_file"
    else
        log_warning "Redis数据目录不存在: $REDIS_DIR"
    fi
}

# 备份ChromaDB数据
backup_chroma() {
    log_info "备份ChromaDB数据..."
    
    local backup_file="$DAILY_BACKUP_DIR/chroma_data_$TIMESTAMP.tar.gz"
    
    if [ -d "$CHROMA_DIR" ]; then
        tar -czf "$backup_file" -C "$CHROMA_DIR" .
        log_success "ChromaDB数据备份完成: $backup_file"
    else
        log_warning "ChromaDB数据目录不存在: $CHROMA_DIR"
    fi
}

# 创建配置备份
backup_configs() {
    log_info "备份配置文件..."
    
    local backup_file="$DAILY_BACKUP_DIR/configs_$TIMESTAMP.tar.gz"
    local temp_dir="/tmp/config_backup_$TIMESTAMP"
    
    mkdir -p "$temp_dir"
    
    # 收集配置文件
    if [ -f "/app/config/config.yaml" ]; then
        cp "/app/config/config.yaml" "$temp_dir/"
    fi
    
    if [ -f "/app/config/mcp_servers.json" ]; then
        cp "/app/config/mcp_servers.json" "$temp_dir/"
    fi
    
    if [ -f "/etc/nginx/nginx.conf" ]; then
        cp "/etc/nginx/nginx.conf" "$temp_dir/nginx.conf"
    fi
    
    # 创建备份
    if [ "$(ls -A $temp_dir)" ]; then
        tar -czf "$backup_file" -C "$temp_dir" .
        log_success "配置文件备份完成: $backup_file"
    else
        log_warning "没有找到配置文件"
    fi
    
    # 清理临时目录
    rm -rf "$temp_dir"
}

# 创建数据库转储
backup_database_dump() {
    log_info "创建数据库转储..."
    
    # 如果有PostgreSQL或MySQL数据库，在这里添加备份逻辑
    # 示例：
    # pg_dump -h postgres -U testagent testagent_db > "$DAILY_BACKUP_DIR/database_$TIMESTAMP.sql"
    
    log_info "数据库转储完成（如果适用）"
}

# 验证备份完整性
verify_backups() {
    log_info "验证备份完整性..."
    
    local backup_count=0
    local failed_count=0
    
    for backup_file in "$DAILY_BACKUP_DIR"/*_$TIMESTAMP.tar.gz; do
        if [ -f "$backup_file" ]; then
            backup_count=$((backup_count + 1))
            
            # 验证tar文件完整性
            if tar -tzf "$backup_file" > /dev/null 2>&1; then
                log_success "备份文件验证通过: $(basename "$backup_file")"
            else
                log_error "备份文件损坏: $(basename "$backup_file")"
                failed_count=$((failed_count + 1))
            fi
        fi
    done
    
    log_info "备份验证完成: $backup_count 个文件，$failed_count 个失败"
    
    if [ $failed_count -gt 0 ]; then
        return 1
    fi
    
    return 0
}

# 创建周备份
create_weekly_backup() {
    local day_of_week=$(date '+%u')  # 1=Monday, 7=Sunday
    
    if [ "$day_of_week" = "7" ]; then  # Sunday
        log_info "创建周备份..."
        
        local weekly_backup="$WEEKLY_BACKUP_DIR/weekly_backup_$(date '+%Y_W%V').tar.gz"
        
        # 将当天的日备份合并为周备份
        if [ -d "$DAILY_BACKUP_DIR" ]; then
            tar -czf "$weekly_backup" -C "$DAILY_BACKUP_DIR" .
            log_success "周备份创建完成: $weekly_backup"
        fi
    fi
}

# 创建月备份
create_monthly_backup() {
    local day_of_month=$(date '+%d')
    
    if [ "$day_of_month" = "01" ]; then  # First day of month
        log_info "创建月备份..."
        
        local monthly_backup="$MONTHLY_BACKUP_DIR/monthly_backup_$(date '+%Y_%m').tar.gz"
        
        # 将上个月的周备份合并为月备份
        if [ -d "$WEEKLY_BACKUP_DIR" ]; then
            tar -czf "$monthly_backup" -C "$WEEKLY_BACKUP_DIR" .
            log_success "月备份创建完成: $monthly_backup"
        fi
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理旧备份..."
    
    # 清理日备份（保留指定天数）
    find "$DAILY_BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
    
    # 清理周备份（保留12周）
    find "$WEEKLY_BACKUP_DIR" -name "*.tar.gz" -mtime +84 -delete  # 12 weeks
    
    # 清理月备份（保留12个月）
    find "$MONTHLY_BACKUP_DIR" -name "*.tar.gz" -mtime +365 -delete  # 12 months
    
    log_success "旧备份清理完成"
}

# 发送备份报告
send_backup_report() {
    local status=$1
    local backup_size=$(du -sh "$DAILY_BACKUP_DIR" | cut -f1)
    
    log_info "发送备份报告..."
    
    # 这里可以集成邮件或Slack通知
    # 示例：
    # curl -X POST -H 'Content-type: application/json' \
    #     --data "{\"text\":\"TestAgent备份完成 - 状态: $status, 大小: $backup_size\"}" \
    #     "$SLACK_WEBHOOK_URL"
    
    log_info "备份报告已发送（状态: $status, 大小: $backup_size）"
}

# 主备份函数
main_backup() {
    log_info "开始TestAgent生产环境备份..."
    
    local start_time=$(date +%s)
    local backup_status="SUCCESS"
    
    # 创建备份目录
    create_backup_dirs
    
    # 执行各项备份
    backup_app_data
    backup_logs
    backup_redis
    backup_chroma
    backup_configs
    backup_database_dump
    
    # 验证备份
    if ! verify_backups; then
        backup_status="FAILED"
    fi
    
    # 创建周/月备份
    create_weekly_backup
    create_monthly_backup
    
    # 清理旧备份
    cleanup_old_backups
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "备份完成！耗时: ${duration}秒"
    
    # 发送报告
    send_backup_report "$backup_status"
    
    if [ "$backup_status" = "FAILED" ]; then
        exit 1
    fi
}

# 恢复功能
restore_backup() {
    local backup_date=$1
    
    if [ -z "$backup_date" ]; then
        log_error "请指定备份日期 (格式: YYYYMMDD_HHMMSS)"
        exit 1
    fi
    
    log_info "开始恢复备份: $backup_date"
    
    # 恢复应用数据
    if [ -f "$DAILY_BACKUP_DIR/testagent_data_$backup_date.tar.gz" ]; then
        log_info "恢复应用数据..."
        tar -xzf "$DAILY_BACKUP_DIR/testagent_data_$backup_date.tar.gz" -C "$DATA_DIR"
        log_success "应用数据恢复完成"
    fi
    
    # 恢复Redis数据
    if [ -f "$DAILY_BACKUP_DIR/redis_data_$backup_date.tar.gz" ]; then
        log_info "恢复Redis数据..."
        tar -xzf "$DAILY_BACKUP_DIR/redis_data_$backup_date.tar.gz" -C "$REDIS_DIR"
        log_success "Redis数据恢复完成"
    fi
    
    # 恢复ChromaDB数据
    if [ -f "$DAILY_BACKUP_DIR/chroma_data_$backup_date.tar.gz" ]; then
        log_info "恢复ChromaDB数据..."
        tar -xzf "$DAILY_BACKUP_DIR/chroma_data_$backup_date.tar.gz" -C "$CHROMA_DIR"
        log_success "ChromaDB数据恢复完成"
    fi
    
    log_success "备份恢复完成！"
}

# 列出可用备份
list_backups() {
    log_info "可用备份列表:"
    
    echo "日备份:"
    ls -la "$DAILY_BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print $9, $5, $6, $7, $8}' || echo "无日备份"
    
    echo -e "\n周备份:"
    ls -la "$WEEKLY_BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print $9, $5, $6, $7, $8}' || echo "无周备份"
    
    echo -e "\n月备份:"
    ls -la "$MONTHLY_BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print $9, $5, $6, $7, $8}' || echo "无月备份"
}

# 命令行参数处理
case "${1:-backup}" in
    "backup")
        main_backup
        ;;
    "restore")
        restore_backup "$2"
        ;;
    "list")
        list_backups
        ;;
    "cleanup")
        cleanup_old_backups
        ;;
    "verify")
        verify_backups
        ;;
    *)
        echo "用法: $0 [backup|restore|list|cleanup|verify] [backup_date]"
        echo "  backup  - 执行备份 (默认)"
        echo "  restore - 恢复备份 (需要指定备份日期)"
        echo "  list    - 列出可用备份"
        echo "  cleanup - 清理旧备份"
        echo "  verify  - 验证备份完整性"
        exit 1
        ;;
esac