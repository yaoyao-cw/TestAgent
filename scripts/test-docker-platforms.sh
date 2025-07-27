#!/bin/bash
# TestAgent Docker 平台兼容性测试脚本

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
    echo -e "${CYAN}  TestAgent Docker 平台兼容性测试${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 测试配置
TEST_PLATFORMS=("linux/amd64" "linux/arm64")
TEST_IMAGE="testagent-test"
TEST_TIMEOUT=300  # 5分钟超时
CLEANUP=true

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --platforms)
            IFS=',' read -ra TEST_PLATFORMS <<< "$2"
            shift 2
            ;;
        --image)
            TEST_IMAGE="$2"
            shift 2
            ;;
        --timeout)
            TEST_TIMEOUT="$2"
            shift 2
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo
    echo "选项:"
    echo "  --platforms LIST    测试平台列表 (默认: linux/amd64,linux/arm64)"
    echo "  --image NAME        测试镜像名称 (默认: testagent-test)"
    echo "  --timeout SECONDS   测试超时时间 (默认: 300)"
    echo "  --no-cleanup        测试后不清理资源"
    echo "  -h, --help          显示帮助信息"
    echo
    echo "示例:"
    echo "  $0                                    # 测试所有平台"
    echo "  $0 --platforms linux/amd64          # 仅测试AMD64"
    echo "  $0 --timeout 600                    # 设置10分钟超时"
}

# 检查Docker环境
check_docker_env() {
    log_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行"
        return 1
    fi
    
    if ! docker buildx version &> /dev/null; then
        log_error "Docker Buildx插件未安装"
        return 1
    fi
    
    log_success "Docker环境检查通过"
    return 0
}

# 设置测试环境
setup_test_env() {
    log_info "设置测试环境..."
    
    # 创建测试构建器
    local builder_name="testagent-test-builder"
    
    if docker buildx ls | grep -q "$builder_name"; then
        docker buildx rm "$builder_name" || true
    fi
    
    docker buildx create --name "$builder_name" --driver docker-container --bootstrap
    docker buildx use "$builder_name"
    
    log_success "测试环境设置完成"
}

# 构建测试镜像
build_test_image() {
    local platform=$1
    local image_tag="$TEST_IMAGE:${platform//\//-}"
    
    log_info "构建测试镜像: $image_tag (平台: $platform)"
    
    # 构建镜像
    if docker buildx build \
        --platform "$platform" \
        --tag "$image_tag" \
        --load \
        . > /tmp/build_${platform//\//-}.log 2>&1; then
        log_success "镜像构建成功: $image_tag"
        return 0
    else
        log_error "镜像构建失败: $image_tag"
        log_error "构建日志:"
        cat /tmp/build_${platform//\//-}.log | tail -20
        return 1
    fi
}

# 测试镜像启动
test_image_startup() {
    local platform=$1
    local image_tag="$TEST_IMAGE:${platform//\//-}"
    local container_name="testagent-test-${platform//\//-}"
    
    log_info "测试镜像启动: $image_tag"
    
    # 启动容器
    if docker run -d \
        --name "$container_name" \
        --platform "$platform" \
        -p 8000:8000 \
        "$image_tag" > /dev/null; then
        
        # 等待服务启动
        local count=0
        while [ $count -lt $((TEST_TIMEOUT / 5)) ]; do
            if curl -f http://localhost:8000/health &> /dev/null; then
                log_success "服务启动成功: $image_tag"
                docker stop "$container_name" > /dev/null
                docker rm "$container_name" > /dev/null
                return 0
            fi
            sleep 5
            count=$((count + 1))
        done
        
        log_error "服务启动超时: $image_tag"
        docker logs "$container_name" | tail -20
        docker stop "$container_name" > /dev/null
        docker rm "$container_name" > /dev/null
        return 1
    else
        log_error "容器启动失败: $image_tag"
        return 1
    fi
}

# 测试Docker Compose
test_docker_compose() {
    local platform=$1
    local compose_file="docker-compose.${platform//\//-}.yml"
    
    log_info "测试Docker Compose: $compose_file"
    
    if [ ! -f "$compose_file" ]; then
        log_warning "Compose文件不存在: $compose_file"
        return 0
    fi
    
    # 使用平台选择器测试
    if python3 scripts/docker-compose-platform.py --env prod up -d > /tmp/compose_${platform//\//-}.log 2>&1; then
        sleep 10
        
        # 检查服务状态
        if python3 scripts/docker-compose-platform.py --env prod ps | grep -q "Up"; then
            log_success "Docker Compose测试成功: $compose_file"
            python3 scripts/docker-compose-platform.py --env prod down > /dev/null
            return 0
        else
            log_error "Docker Compose服务未正常启动: $compose_file"
            python3 scripts/docker-compose-platform.py --env prod logs | tail -20
            python3 scripts/docker-compose-platform.py --env prod down > /dev/null
            return 1
        fi
    else
        log_error "Docker Compose启动失败: $compose_file"
        cat /tmp/compose_${platform//\//-}.log | tail -20
        return 1
    fi
}

# 性能基准测试
run_performance_test() {
    local platform=$1
    local image_tag="$TEST_IMAGE:${platform//\//-}"
    local container_name="testagent-perf-${platform//\//-}"
    
    log_info "运行性能测试: $platform"
    
    # 启动容器
    docker run -d \
        --name "$container_name" \
        --platform "$platform" \
        -p 8000:8000 \
        "$image_tag" > /dev/null
    
    # 等待服务启动
    sleep 10
    
    # 简单的性能测试
    local start_time=$(date +%s)
    local success_count=0
    local total_requests=10
    
    for i in $(seq 1 $total_requests); do
        if curl -f http://localhost:8000/health &> /dev/null; then
            success_count=$((success_count + 1))
        fi
        sleep 1
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local success_rate=$((success_count * 100 / total_requests))
    
    log_info "性能测试结果 ($platform):"
    log_info "  成功率: $success_rate%"
    log_info "  总耗时: ${duration}秒"
    
    # 清理
    docker stop "$container_name" > /dev/null
    docker rm "$container_name" > /dev/null
    
    if [ $success_rate -ge 80 ]; then
        log_success "性能测试通过: $platform"
        return 0
    else
        log_error "性能测试失败: $platform"
        return 1
    fi
}

# 清理测试资源
cleanup_test_env() {
    if [ "$CLEANUP" = true ]; then
        log_info "清理测试资源..."
        
        # 停止并删除测试容器
        docker ps -a | grep testagent-test | awk '{print $1}' | xargs -r docker rm -f
        
        # 删除测试镜像
        docker images | grep "$TEST_IMAGE" | awk '{print $3}' | xargs -r docker rmi -f
        
        # 删除测试构建器
        docker buildx rm testagent-test-builder 2>/dev/null || true
        
        # 清理临时文件
        rm -f /tmp/build_*.log /tmp/compose_*.log
        
        log_success "测试资源清理完成"
    fi
}

# 生成测试报告
generate_test_report() {
    local results=("$@")
    local total_tests=${#TEST_PLATFORMS[@]}
    local passed_tests=0
    
    echo
    log_info "测试报告:"
    echo "========================================="
    
    for i in "${!TEST_PLATFORMS[@]}"; do
        local platform="${TEST_PLATFORMS[$i]}"
        local result="${results[$i]}"
        
        if [ "$result" = "PASS" ]; then
            echo -e "  ${GREEN}✅ $platform: PASS${NC}"
            passed_tests=$((passed_tests + 1))
        else
            echo -e "  ${RED}❌ $platform: FAIL${NC}"
        fi
    done
    
    echo "========================================="
    echo "总计: $passed_tests/$total_tests 通过"
    
    if [ $passed_tests -eq $total_tests ]; then
        log_success "所有平台测试通过！"
        return 0
    else
        log_error "部分平台测试失败"
        return 1
    fi
}

# 主测试函数
run_platform_test() {
    local platform=$1
    local test_result="FAIL"
    
    log_info "开始测试平台: $platform"
    
    # 构建测试
    if build_test_image "$platform"; then
        # 启动测试
        if test_image_startup "$platform"; then
            # 性能测试
            if run_performance_test "$platform"; then
                test_result="PASS"
            fi
        fi
    fi
    
    log_info "平台测试完成: $platform ($test_result)"
    echo "$test_result"
}

# 主函数
main() {
    show_banner
    
    log_info "测试配置:"
    log_info "  测试平台: ${TEST_PLATFORMS[*]}"
    log_info "  测试镜像: $TEST_IMAGE"
    log_info "  超时时间: ${TEST_TIMEOUT}秒"
    log_info "  清理资源: $CLEANUP"
    echo
    
    # 检查环境
    if ! check_docker_env; then
        exit 1
    fi
    
    # 设置测试环境
    setup_test_env
    
    # 运行测试
    local test_results=()
    
    for platform in "${TEST_PLATFORMS[@]}"; do
        result=$(run_platform_test "$platform")
        test_results+=("$result")
    done
    
    # 清理资源
    cleanup_test_env
    
    # 生成报告
    if generate_test_report "${test_results[@]}"; then
        exit 0
    else
        exit 1
    fi
}

# 捕获中断信号
trap 'log_warning "测试被中断"; cleanup_test_env; exit 1' INT TERM

# 执行主函数
main "$@"