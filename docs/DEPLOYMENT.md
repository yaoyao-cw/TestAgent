# TestAgent 部署指南

本文档提供了TestAgent的完整部署指南，包括开发环境和生产环境的部署方式。

## 目录

- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [开发环境部署](#开发环境部署)
- [生产环境部署](#生产环境部署)
- [配置说明](#配置说明)
- [监控和日志](#监控和日志)
- [故障排除](#故障排除)
- [维护和更新](#维护和更新)

## 系统要求

### 最低要求
- **操作系统**: Linux (Ubuntu 20.04+, CentOS 8+) 或 macOS 10.15+
- **内存**: 4GB RAM (推荐 8GB+)
- **存储**: 20GB 可用空间 (推荐 50GB+)
- **CPU**: 2核心 (推荐 4核心+)

### 软件依赖
- **Docker**: 20.10+ 
- **Docker Compose**: 2.0+
- **Git**: 2.20+
- **curl**: 用于健康检查

### 安装Docker和Docker Compose

#### Ubuntu/Debian
```bash
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### CentOS/RHEL
```bash
# 安装Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd TestAgent
```

### 2. 一键部署
```bash
# 生产环境部署
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# 或开发环境部署
chmod +x scripts/dev-deploy.sh
./scripts/dev-deploy.sh
```

### 3. 访问应用
- 主应用: http://localhost:8000
- API文档: http://localhost:8000/docs
- 监控面板: http://localhost:8000/static/monitoring.html

## 开发环境部署

开发环境支持代码热重载、详细日志和调试功能。

### 启动开发环境
```bash
./scripts/dev-deploy.sh dev
```

### 开发环境服务
- **TestAgent应用**: http://localhost:8000 (支持热重载)
- **Redis**: localhost:6380
- **ChromaDB**: http://localhost:8002

### 开发工具命令
```bash
# 查看日志
./scripts/dev-deploy.sh logs

# 进入容器
./scripts/dev-deploy.sh shell

# 运行测试
./scripts/dev-deploy.sh test

# 代码格式化
./scripts/dev-deploy.sh format

# 代码检查
./scripts/dev-deploy.sh lint

# 重新构建
./scripts/dev-deploy.sh build
```

## 生产环境部署

生产环境包含完整的服务栈，包括负载均衡、监控和日志收集。

### 服务架构
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Nginx    │────│  TestAgent  │────│    Redis    │
│ (反向代理)   │    │   (主应用)   │    │   (缓存)    │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
                   ┌─────────────┐    ┌─────────────┐
                   │  ChromaDB   │    │ Prometheus  │
                   │ (向量数据库) │    │   (监控)    │
                   └─────────────┘    └─────────────┘
                                             │
                                     ┌─────────────┐
                                     │   Grafana   │
                                     │ (可视化面板) │
                                     └─────────────┘
```

### 部署步骤

#### 1. 环境准备
```bash
# 创建部署目录
mkdir -p /opt/testagent
cd /opt/testagent

# 克隆代码
git clone <repository-url> .
```

#### 2. 配置文件设置
```bash
# 复制并编辑环境配置
cp .env.example .env
vim .env

# 复制并编辑应用配置
cp config/config.example.yaml config/config.yaml
vim config/config.yaml
```

#### 3. 执行部署
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh deploy
```

### 生产环境服务端口
- **Nginx**: 80, 443 (HTTP/HTTPS)
- **TestAgent**: 8000 (内部)
- **Redis**: 6379 (内部)
- **ChromaDB**: 8001 (内部)
- **Prometheus**: 9090
- **Grafana**: 3000

## 配置说明

### 环境变量配置 (.env)
```bash
# 基本配置
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据库配置
REDIS_URL=redis://redis:6379/0
VECTOR_DB_PATH=/app/data/vectordb

# LLM配置
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-3.5-turbo

# 日志配置
LOG_FILE=/app/logs/testagent.log
```

### 应用配置 (config/config.yaml)
```yaml
# 详细配置请参考 config.example.yaml
debug: false
environment: "production"

logging:
  level: "INFO"
  file: "/app/logs/testagent.log"

llm:
  provider: "openai"
  default_model: "gpt-3.5-turbo"
  temperature: 0.7

cache:
  enabled: true
  redis_url: "redis://redis:6379/0"
  ttl: 3600
```

### Nginx配置
Nginx配置文件位于 `nginx/conf.d/testagent.conf`，包含：
- 反向代理配置
- 负载均衡
- SSL终止 (需要配置证书)
- 速率限制
- 静态文件服务

## 监控和日志

### Prometheus监控
- **访问地址**: http://localhost:9090
- **配置文件**: `monitoring/prometheus.yml`
- **监控指标**: 应用性能、系统资源、错误率等

### Grafana可视化
- **访问地址**: http://localhost:3000
- **默认账号**: admin/admin123
- **数据源**: Prometheus
- **仪表板**: 自动配置应用监控面板

### 日志管理
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f testagent

# 查看应用日志文件
docker exec testagent-app tail -f /app/logs/testagent.log
```

### 健康检查
```bash
# 检查应用健康状态
curl http://localhost:8000/health

# 检查所有服务状态
./scripts/deploy.sh status
```

## 故障排除

### 常见问题

#### 1. 容器启动失败
```bash
# 检查容器状态
docker-compose ps

# 查看容器日志
docker-compose logs <service-name>

# 检查资源使用
docker stats
```

#### 2. 应用无法访问
```bash
# 检查端口占用
netstat -tlnp | grep :8000

# 检查防火墙设置
sudo ufw status

# 检查Nginx配置
docker-compose exec nginx nginx -t
```

#### 3. 数据库连接问题
```bash
# 检查Redis连接
docker-compose exec redis redis-cli ping

# 检查ChromaDB连接
curl http://localhost:8001/api/v1/heartbeat
```

#### 4. 内存不足
```bash
# 检查内存使用
free -h
docker stats

# 清理未使用的镜像和容器
docker system prune -a
```

### 日志分析
```bash
# 查看错误日志
docker-compose logs testagent | grep ERROR

# 查看访问日志
docker-compose logs nginx | grep -E "GET|POST"

# 实时监控日志
docker-compose logs -f --tail=100
```

## 维护和更新

### 备份数据
```bash
# 备份数据卷
docker run --rm -v testagent_testagent_data:/data -v $(pwd):/backup alpine tar czf /backup/testagent_data_backup.tar.gz -C /data .

# 备份配置文件
tar czf config_backup.tar.gz config/ .env
```

### 更新应用
```bash
# 拉取最新代码
git pull origin main

# 重新构建和部署
./scripts/deploy.sh stop
./scripts/deploy.sh deploy
```

### 扩容部署
```bash
# 增加应用实例
docker-compose up -d --scale testagent=3

# 使用外部负载均衡器
# 配置多个TestAgent实例到负载均衡器后端
```

### 数据迁移
```bash
# 导出数据
docker-compose exec testagent python scripts/export_data.py

# 导入数据
docker-compose exec testagent python scripts/import_data.py
```

## 安全建议

### 1. 网络安全
- 使用防火墙限制端口访问
- 配置SSL/TLS证书
- 使用VPN或私有网络

### 2. 认证和授权
- 配置API密钥认证
- 设置强密码策略
- 定期轮换密钥

### 3. 数据安全
- 加密敏感数据
- 定期备份数据
- 限制数据访问权限

### 4. 容器安全
- 使用非root用户运行容器
- 定期更新基础镜像
- 扫描镜像漏洞

## 性能优化

### 1. 资源配置
```yaml
# docker-compose.yml 中的资源限制
services:
  testagent:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### 2. 缓存优化
- 配置Redis集群
- 调整缓存TTL
- 使用CDN加速静态资源

### 3. 数据库优化
- 配置ChromaDB持久化
- 优化向量索引
- 定期清理过期数据

## 支持和帮助

如果遇到问题，请：
1. 查看本文档的故障排除部分
2. 检查应用日志和监控指标
3. 提交Issue到项目仓库
4. 联系技术支持团队

---

更多详细信息请参考：
- [API文档](api.md)
- [开发指南](development.md)
- [配置参考](configuration.md)