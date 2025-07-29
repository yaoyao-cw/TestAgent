# TestAgent - 智能测试代理系统

TestAgent是一个基于AI的智能测试代理系统，能够自动化执行软件测试的各个环节，从需求分析到测试报告生成，提供完整的测试解决方案。

## 🎯 项目概述

TestAgent采用多智能体协作架构，通过协调器、规划器、研究员、编码员、报告员和评审员等专业化智能体，实现测试任务的智能化分解和执行。系统支持多种LLM提供商，集成RAG知识库，提供人机协作界面，确保测试质量和效率。

## ✨ 核心特性

### 🤖 多智能体协作
- **协调器**: 任务分发和意图识别
- **规划器**: 测试计划生成和优化
- **研究员**: 需求分析和测试用例设计
- **编码员**: 测试脚本编写和执行
- **报告员**: 测试报告生成和格式化
- **评审员**: 质量评估和改进建议

### 🧠 AI能力集成
- 支持多种LLM提供商 (OpenAI, Anthropic, Azure OpenAI)
- RAG知识库集成，支持文档检索和语义搜索
- 智能缓存机制，提升响应速度
- 自适应模型选择和参数优化

### 🔧 工具生态
- Python REPL代码执行环境
- MCP外部工具集成
- 文档解析器 (PDF, Word, Excel)
- 网络搜索和信息检索

### 👥 人机协作
- 计划审查和反馈机制
- 自然语言计划修改
- 报告后编辑和优化
- 可配置的自动化程度

### 🚀 企业级特性
- 微服务架构设计
- 容器化部署支持
- 监控和日志系统
- 任务创建状态监控系统
- 智能错误处理和用户友好提醒系统
- 网络错误诊断和自动恢复机制
- 性能优化和缓存
- 配置管理系统

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    TestAgent 系统架构                        │
├─────────────────────────────────────────────────────────────┤
│  Web API Layer                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   FastAPI   │ │  WebSocket  │ │   静态文件   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Agent Orchestration Layer                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   协调器     │ │   规划器     │ │   工作流     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Specialized Agents Layer                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   研究员     │ │   编码员     │ │   报告员     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐                           │
│  │   评审员     │ │  人机协作    │                           │
│  └─────────────┘ └─────────────┘                           │
├─────────────────────────────────────────────────────────────┤
│  Core Services Layer                                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  LLM服务    │ │  RAG服务    │ │  工具管理    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  MCP集成    │ │  缓存系统    │ │  监控系统    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Redis     │ │  ChromaDB   │ │  文件系统    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Docker & Docker Compose
- 4GB+ RAM
- 20GB+ 存储空间

### 一键部署

#### 开发环境
```bash
git clone <repository-url>
cd TestAgent
chmod +x scripts/dev-deploy.sh
./scripts/dev-deploy.sh
```

#### 生产环境
```bash
git clone <repository-url>
cd TestAgent
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### 访问地址
- **主应用**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **监控面板**: http://localhost:8000/static/monitoring.html
- **Grafana**: http://localhost:3000 (admin/admin123)

## 📖 使用指南

### 基本使用流程

1. **配置系统**
   ```bash
   # 复制配置文件
   cp .env.example .env
   cp config/config.example.yaml config/config.yaml
   
   # 编辑配置文件，添加API密钥等
   vim .env
   ```

2. **上传测试文档**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/documents/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "file=@test_requirements.pdf"
   ```

3. **提交测试任务**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/tasks/submit" \
        -H "Content-Type: application/json" \
        -d '{
          "task_type": "functional_testing",
          "description": "测试用户登录功能",
          "documents": ["test_requirements.pdf"]
        }'
   ```

4. **查看任务状态**
   ```bash
   curl "http://localhost:8000/api/v1/tasks/{task_id}/status"
   ```

5. **监控任务创建进度**
   ```bash
   curl "http://localhost:8000/api/v1/tasks/{task_id}/creation-status"
   ```

6. **获取测试报告**
   ```bash
   curl "http://localhost:8000/api/v1/tasks/{task_id}/report"
   ```

### API接口

#### 任务管理
- `POST /api/v1/tasks/submit` - 提交测试任务
- `GET /api/v1/tasks/{task_id}/status` - 查看任务状态
- `GET /api/v1/tasks/{task_id}/creation-status` - 查看任务创建状态
- `POST /api/v1/tasks/{task_id}/pause` - 暂停任务
- `POST /api/v1/tasks/{task_id}/resume` - 恢复任务
- `GET /api/v1/tasks/{task_id}/report` - 获取测试报告
- `POST /api/v1/tasks/{task_id}/feedback` - 提供反馈

#### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/` - 列出文档
- `DELETE /api/v1/documents/{doc_id}` - 删除文档

#### 系统管理
- `GET /api/v1/monitoring/health` - 健康检查
- `GET /api/v1/monitoring/metrics` - 系统指标
- `GET /api/v1/config/settings` - 配置管理
- `GET /api/v1/errors/format` - 错误消息格式化

## 🔧 配置说明

### 环境变量配置
```bash
# LLM配置
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-3.5-turbo

# 数据库配置
REDIS_URL=redis://localhost:6379/0
VECTOR_DB_PATH=./data/vectordb

# API配置
API_HOST=0.0.0.0
API_PORT=8000
```

### 应用配置
```yaml
# config/config.yaml
llm:
  provider: "openai"
  default_model: "gpt-3.5-turbo"
  temperature: 0.7

cache:
  enabled: true
  redis_url: "redis://localhost:6379/0"
  ttl: 3600

collaboration:
  auto_accept_mode: "conditional"
  confidence_threshold: 0.8
```

## 🧪 测试

### 运行测试
```bash
# 单元测试
python -m pytest tests/ -v

# 集成测试
python -m pytest tests/integration/ -v

# 性能测试
python -m pytest tests/performance/ -v
```

### 测试覆盖率
```bash
python -m pytest --cov=src tests/
```

## 📊 监控和运维

### 健康检查
```bash
# 基本健康检查
./scripts/healthcheck.sh

# 监控模式
./scripts/healthcheck.sh monitor
```

### 日志管理
```bash
# 查看应用日志
docker-compose logs -f testagent

# 查看所有服务日志
docker-compose logs -f
```

### 性能监控
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **应用监控**: http://localhost:8000/static/monitoring.html

## 🔒 安全特性

- 非root用户运行容器
- API密钥认证
- 速率限制和防护
- 输入验证和清理
- 安全头设置
- 数据加密存储

## 🚀 性能优化

- 多层缓存架构 (内存 + Redis)
- LLM响应缓存
- RAG检索结果缓存
- 并发处理优化
- 异步执行框架
- 资源管理和监控

## 📚 文档

- [部署指南](docs/deployment.md)
- [API文档](http://localhost:8000/docs)
- [开发指南](docs/development.md)
- [配置参考](docs/configuration.md)

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢所有为TestAgent项目做出贡献的开发者和用户。

## 📞 支持

如果您遇到问题或需要帮助：

1. 查看 [文档](docs/)
2. 搜索 [Issues](../../issues)
3. 创建新的 [Issue](../../issues/new)
4. 联系维护团队

---

**TestAgent** - 让AI为您的测试工作赋能 🚀