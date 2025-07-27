#!/bin/bash
# TestAgent 测试环境部署脚本

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
    echo -e "${CYAN}    TestAgent 测试环境部署脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo
}

# 配置变量
ENVIRONMENT="staging"
NAMESPACE="testagent-staging"
IMAGE_TAG="${1:-latest}"
REGISTRY="ghcr.io"
REPO_NAME="testagent"
HEALTH_CHECK_TIMEOUT=300

# 检查依赖
check_dependencies() {
    log_info "检查部署依赖..."
    
    # 检查kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl未安装"
        return 1
    fi
    
    # 检查helm (如果使用)
    if ! command -v helm &> /dev/null; then
        log_warning "helm未安装，将使用kubectl部署"
    fi
    
    # 检查docker
    if ! command -v docker &> /dev/null; then
        log_error "docker未安装"
        return 1
    fi
    
    log_success "依赖检查通过"
    return 0
}

# 检查Kubernetes连接
check_k8s_connection() {
    log_info "检查Kubernetes连接..."
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到Kubernetes集群"
        return 1
    fi
    
    log_success "Kubernetes连接正常"
    return 0
}

# 创建命名空间
create_namespace() {
    log_info "创建命名空间: $NAMESPACE"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "命名空间已存在: $NAMESPACE"
    else
        kubectl create namespace "$NAMESPACE"
        log_success "命名空间创建成功: $NAMESPACE"
    fi
}

# 部署配置映射
deploy_configmaps() {
    log_info "部署配置映射..."
    
    # 创建应用配置
    kubectl create configmap testagent-config \
        --from-file=config/config.yaml \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # 创建MCP配置
    kubectl create configmap testagent-mcp-config \
        --from-file=config/mcp_servers.json \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # 创建监控配置
    kubectl create configmap prometheus-config \
        --from-file=monitoring/prometheus.yml \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "配置映射部署完成"
}

# 部署密钥
deploy_secrets() {
    log_info "部署密钥..."
    
    # 创建数据库密钥
    kubectl create secret generic testagent-secrets \
        --from-literal=redis-password="$(openssl rand -base64 32)" \
        --from-literal=jwt-secret="$(openssl rand -base64 64)" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "密钥部署完成"
}

# 部署Redis
deploy_redis() {
    log_info "部署Redis..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes", "--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"]
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: $NAMESPACE
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
EOF
    
    log_success "Redis部署完成"
}

# 部署ChromaDB
deploy_chroma() {
    log_info "部署ChromaDB..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chroma
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: chroma
  template:
    metadata:
      labels:
        app: chroma
    spec:
      containers:
      - name: chroma
        image: chromadb/chroma:latest
        ports:
        - containerPort: 8000
        env:
        - name: CHROMA_SERVER_HOST
          value: "0.0.0.0"
        - name: CHROMA_SERVER_HTTP_PORT
          value: "8000"
        resources:
          requests:
            memory: "512Mi"
            cpu: "200m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        volumeMounts:
        - name: chroma-data
          mountPath: /chroma/chroma
      volumes:
      - name: chroma-data
        persistentVolumeClaim:
          claimName: chroma-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: chroma
  namespace: $NAMESPACE
spec:
  selector:
    app: chroma
  ports:
  - port: 8000
    targetPort: 8000
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: chroma-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
    
    log_success "ChromaDB部署完成"
}

# 部署TestAgent主应用
deploy_testagent() {
    log_info "部署TestAgent主应用..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: testagent
  namespace: $NAMESPACE
spec:
  replicas: 2
  selector:
    matchLabels:
      app: testagent
  template:
    metadata:
      labels:
        app: testagent
    spec:
      containers:
      - name: testagent
        image: $REGISTRY/$REPO_NAME:$IMAGE_TAG
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: DEBUG
          value: "false"
        - name: LOG_LEVEL
          value: "INFO"
        - name: REDIS_URL
          value: "redis://redis:6379/0"
        - name: VECTOR_DB_URL
          value: "http://chroma:8000"
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: mcp-config
          mountPath: /app/config/mcp_servers.json
          subPath: mcp_servers.json
      volumes:
      - name: config
        configMap:
          name: testagent-config
      - name: mcp-config
        configMap:
          name: testagent-mcp-config
---
apiVersion: v1
kind: Service
metadata:
  name: testagent
  namespace: $NAMESPACE
spec:
  selector:
    app: testagent
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: testagent-ingress
  namespace: $NAMESPACE
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: testagent-staging.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: testagent
            port:
              number: 8000
EOF
    
    log_success "TestAgent主应用部署完成"
}

# 部署监控服务
deploy_monitoring() {
    log_info "部署监控服务..."
    
    # 部署Prometheus
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--storage.tsdb.retention.time=72h'
          - '--web.enable-lifecycle'
        resources:
          requests:
            memory: "512Mi"
            cpu: "200m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus
        - name: prometheus-data
          mountPath: /prometheus
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
      - name: prometheus-data
        persistentVolumeClaim:
          claimName: prometheus-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: $NAMESPACE
spec:
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: prometheus-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
    
    log_success "监控服务部署完成"
}

# 等待部署完成
wait_for_deployment() {
    local deployment=$1
    log_info "等待部署完成: $deployment"
    
    if kubectl rollout status deployment/"$deployment" --namespace="$NAMESPACE" --timeout="${HEALTH_CHECK_TIMEOUT}s"; then
        log_success "部署完成: $deployment"
        return 0
    else
        log_error "部署超时: $deployment"
        return 1
    fi
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查所有Pod状态
    if kubectl get pods --namespace="$NAMESPACE" | grep -v Running | grep -v Completed; then
        log_warning "发现非运行状态的Pod"
    fi
    
    # 检查服务端点
    local service_url="http://testagent-staging.example.com"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f "$service_url/health" &> /dev/null; then
            log_success "健康检查通过: $service_url"
            return 0
        fi
        
        log_info "健康检查尝试 $attempt/$max_attempts..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_error "健康检查失败"
    return 1
}

# 运行冒烟测试
run_smoke_tests() {
    log_info "运行冒烟测试..."
    
    # 基本API测试
    local base_url="http://testagent-staging.example.com"
    
    # 测试健康检查端点
    if curl -f "$base_url/health" &> /dev/null; then
        log_success "健康检查端点测试通过"
    else
        log_error "健康检查端点测试失败"
        return 1
    fi
    
    # 测试API文档端点
    if curl -f "$base_url/docs" &> /dev/null; then
        log_success "API文档端点测试通过"
    else
        log_error "API文档端点测试失败"
        return 1
    fi
    
    log_success "冒烟测试通过"
    return 0
}

# 回滚部署
rollback_deployment() {
    log_warning "开始回滚部署..."
    
    kubectl rollout undo deployment/testagent --namespace="$NAMESPACE"
    kubectl rollout undo deployment/redis --namespace="$NAMESPACE"
    kubectl rollout undo deployment/chroma --namespace="$NAMESPACE"
    
    log_success "部署回滚完成"
}

# 清理资源
cleanup_resources() {
    if [ "$1" = "all" ]; then
        log_warning "清理所有资源..."
        kubectl delete namespace "$NAMESPACE"
        log_success "资源清理完成"
    fi
}

# 主函数
main() {
    show_banner
    
    log_info "部署配置:"
    log_info "  环境: $ENVIRONMENT"
    log_info "  命名空间: $NAMESPACE"
    log_info "  镜像标签: $IMAGE_TAG"
    log_info "  注册表: $REGISTRY"
    echo
    
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi
    
    # 检查Kubernetes连接
    if ! check_k8s_connection; then
        exit 1
    fi
    
    # 执行部署
    create_namespace
    deploy_configmaps
    deploy_secrets
    deploy_redis
    deploy_chroma
    deploy_testagent
    deploy_monitoring
    
    # 等待部署完成
    wait_for_deployment "redis"
    wait_for_deployment "chroma"
    wait_for_deployment "testagent"
    wait_for_deployment "prometheus"
    
    # 健康检查
    if ! health_check; then
        log_error "健康检查失败，考虑回滚"
        read -p "是否回滚部署？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback_deployment
        fi
        exit 1
    fi
    
    # 运行冒烟测试
    if ! run_smoke_tests; then
        log_error "冒烟测试失败"
        exit 1
    fi
    
    log_success "测试环境部署完成！"
    echo
    log_info "访问地址:"
    log_info "  应用: http://testagent-staging.example.com"
    log_info "  监控: http://prometheus-staging.example.com"
    echo
    log_info "管理命令:"
    log_info "  查看状态: kubectl get pods -n $NAMESPACE"
    log_info "  查看日志: kubectl logs -f deployment/testagent -n $NAMESPACE"
    log_info "  清理资源: $0 cleanup"
}

# 处理命令行参数
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "rollback")
        rollback_deployment
        ;;
    "cleanup")
        cleanup_resources all
        ;;
    "health")
        health_check
        ;;
    "smoke")
        run_smoke_tests
        ;;
    *)
        echo "用法: $0 [deploy|rollback|cleanup|health|smoke] [image_tag]"
        exit 1
        ;;
esac