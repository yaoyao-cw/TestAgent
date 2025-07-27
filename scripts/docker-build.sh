#!/bin/bash
# TestAgent Docker 多平台构建脚本

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
    echo -e "${CYAN}    TestAgent Docker 多平台构建脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 默认配置
IMAGE_NAME="testagent"
VERSION="latest"
REGISTRY=""
PLATFORMS="linux/amd64,linux/arm64"
BUILD_TYPE="multi"
PUSH=false
NO_CACHE=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --image|-i)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --registry|-r)
            REGISTRY="$2"
            shift 2
            ;;
        --platforms|-p)
            PLATFORMS="$2"
            shift 2
            ;;
        --type|-t)
            BUILD_TYPE="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
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
    echo "  -i, --image NAME      镜像名称 (默认: testagent)"
    echo "  -v, --version VERSION 镜像版本 (默认: latest)"
    echo "  -r, --registry URL    镜像仓库地址"
    echo "  -p, --platforms LIST  目标平台列表 (默认: linux/amd64,linux/arm64)"
    echo "  -t, --type TYPE       构建类型: single, multi, all (默认: multi)"
    echo "      --push            构建后推送到仓库"
    echo "      --no-cache        不使用构建缓存"
    echo "  -h, --help            显示帮助信息"
    echo
    echo "构建类型:"
    echo "  single    - 单平台构建 (当前平台)"
    echo "  multi     - 多平台构建"
    echo "  all       - 构建所有支持的平台"
    echo
    echo "示例:"
    echo "  $0                                    # 多平台构建"
    echo "  $0 --type single                     # 单平台构建"
    echo "  $0 --platforms linux/amd64          # 仅构建AMD64"
    echo "  $0 --registry myregistry.com --push # 构建并推送"
}

# 检查Docker环境
check_docker() {
    log_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装"
        exit 1
    fi
    
    # 检查Docker是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行"
        exit 1
    fi
    
    # 检查buildx插件
    if ! docker buildx version &> /dev/null; then
        log_error "Docker Buildx插件未安装"
        exit 1
    fi
    
    log_success "Docker环境检查通过"
}

# 设置buildx构建器
setup_buildx() {
    log_info "设置Docker Buildx构建器..."
    
    # 创建新的构建器实例
    BUILDER_NAME="testagent-builder"
    
    if docker buildx ls | grep -q "$BUILDER_NAME"; then
        log_info "构建器 $BUILDER_NAME 已存在"
    else
        docker buildx create --name "$BUILDER_NAME" --driver docker-container --bootstrap
        log_success "构建器 $BUILDER_NAME 创建成功"
    fi
    
    # 使用构建器
    docker buildx use "$BUILDER_NAME"
    
    # 检查构建器状态
    docker buildx inspect --bootstrap
    
    log_success "Buildx构建器设置完成"
}

# 获取当前平台
get_current_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    
    case $arch in
        x86_64)
            arch="amd64"
            ;;
        aarch64|arm64)
            arch="arm64"
            ;;
        armv7l)
            arch="arm"
            ;;
    esac
    
    echo "$os/$arch"
}

# 构建镜像
build_image() {
    local platforms=$1
    local image_tag=$2
    
    log_info "构建平台: $platforms"
    log_info "镜像标签: $image_tag"
    
    # 构建参数
    local build_args=(
        "buildx" "build"
        "--platform" "$platforms"
        "--tag" "$image_tag"
    )
    
    # 添加版本标签
    if [ "$VERSION" != "latest" ]; then
        if [ -n "$REGISTRY" ]; then
            build_args+=("--tag" "$REGISTRY/$IMAGE_NAME:latest")
        else
            build_args+=("--tag" "$IMAGE_NAME:latest")
        fi
    fi
    
    # 添加构建选项
    if [ "$NO_CACHE" = true ]; then
        build_args+=("--no-cache")
    fi
    
    if [ "$PUSH" = true ]; then
        build_args+=("--push")
    else
        build_args+=("--load")
    fi
    
    # 添加构建上下文
    build_args+=(".")
    
    # 执行构建
    log_info "执行构建命令: docker ${build_args[*]}"
    docker "${build_args[@]}"
    
    log_success "镜像构建完成: $image_tag"
}

# 单平台构建
build_single() {
    log_info "执行单平台构建..."
    
    local current_platform=$(get_current_platform)
    local image_tag
    
    if [ -n "$REGISTRY" ]; then
        image_tag="$REGISTRY/$IMAGE_NAME:$VERSION"
    else
        image_tag="$IMAGE_NAME:$VERSION"
    fi
    
    build_image "$current_platform" "$image_tag"
}

# 多平台构建
build_multi() {
    log_info "执行多平台构建..."
    
    local image_tag
    if [ -n "$REGISTRY" ]; then
        image_tag="$REGISTRY/$IMAGE_NAME:$VERSION"
    else
        image_tag="$IMAGE_NAME:$VERSION"
    fi
    
    build_image "$PLATFORMS" "$image_tag"
}

# 构建所有平台
build_all() {
    log_info "构建所有支持的平台..."
    
    local all_platforms="linux/amd64,linux/arm64,linux/arm/v7"
    local image_tag
    
    if [ -n "$REGISTRY" ]; then
        image_tag="$REGISTRY/$IMAGE_NAME:$VERSION"
    else
        image_tag="$IMAGE_NAME:$VERSION"
    fi
    
    build_image "$all_platforms" "$image_tag"
}

# 验证构建结果
verify_build() {
    log_info "验证构建结果..."
    
    local image_tag
    if [ -n "$REGISTRY" ]; then
        image_tag="$REGISTRY/$IMAGE_NAME:$VERSION"
    else
        image_tag="$IMAGE_NAME:$VERSION"
    fi
    
    if [ "$PUSH" = false ]; then
        # 本地构建验证
        if docker images | grep -q "$IMAGE_NAME.*$VERSION"; then
            log_success "本地镜像构建成功"
            docker images | grep "$IMAGE_NAME"
        else
            log_error "本地镜像构建失败"
            return 1
        fi
    else
        # 远程推送验证
        log_info "镜像已推送到仓库: $image_tag"
    fi
    
    # 显示镜像信息
    if [ "$PUSH" = false ] && [ "$BUILD_TYPE" = "single" ]; then
        log_info "镜像详细信息:"
        docker inspect "$image_tag" | jq -r '.[0].Architecture, .[0].Os' 2>/dev/null || echo "无法获取架构信息"
    fi
}

# 清理构建器
cleanup_buildx() {
    if [ "$1" = "remove" ]; then
        log_info "清理构建器..."
        docker buildx rm "$BUILDER_NAME" 2>/dev/null || true
        log_success "构建器清理完成"
    fi
}

# 主函数
main() {
    show_banner
    
    log_info "构建配置:"
    log_info "  镜像名称: $IMAGE_NAME"
    log_info "  版本: $VERSION"
    log_info "  仓库: ${REGISTRY:-'本地'}"
    log_info "  平台: $PLATFORMS"
    log_info "  构建类型: $BUILD_TYPE"
    log_info "  推送: ${PUSH:-false}"
    log_info "  无缓存: ${NO_CACHE:-false}"
    echo
    
    # 检查环境
    check_docker
    
    # 设置构建器
    if [ "$BUILD_TYPE" != "single" ]; then
        setup_buildx
    fi
    
    # 执行构建
    case $BUILD_TYPE in
        "single")
            build_single
            ;;
        "multi")
            build_multi
            ;;
        "all")
            build_all
            ;;
        *)
            log_error "未知构建类型: $BUILD_TYPE"
            show_help
            exit 1
            ;;
    esac
    
    # 验证构建结果
    verify_build
    
    log_success "Docker构建完成！"
    
    # 显示使用说明
    echo
    log_info "使用说明:"
    if [ -n "$REGISTRY" ]; then
        echo "  docker run --rm -p 8000:8000 $REGISTRY/$IMAGE_NAME:$VERSION"
    else
        echo "  docker run --rm -p 8000:8000 $IMAGE_NAME:$VERSION"
    fi
    echo "  docker-compose up -d"
}

# 捕获中断信号
trap 'log_warning "构建被中断"; cleanup_buildx remove; exit 1' INT TERM

# 执行主函数
main "$@"