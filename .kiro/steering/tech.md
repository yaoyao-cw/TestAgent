# TestAgent 技术栈

## 后端技术栈
- **Python 3.11+**: 主要编程语言
- **FastAPI**: Web框架，提供REST API和WebSocket支持
- **LangChain/LangGraph**: AI代理框架和工作流编排
- **ChromaDB**: 向量数据库，用于RAG知识库
- **Redis**: 缓存和会话存储
- **Pydantic**: 数据验证和序列化

## 前端技术栈
- **React 18**: 前端框架
- **TypeScript**: 类型安全的JavaScript
- **Vite**: 构建工具
- **Tailwind CSS**: 样式框架
- **React Query**: 数据获取和状态管理
- **Socket.io**: 实时通信

## AI/ML集成
- **LiteLLM**: 多LLM提供商统一接口
- **OpenAI, Anthropic, Google**: LLM提供商
- **Sentence Transformers**: 文本嵌入
- **MCP (Model Context Protocol)**: 外部工具集成

## 部署和基础设施
- **Docker & Docker Compose**: 容器化部署
- **Nginx**: 反向代理
- **Prometheus + Grafana**: 监控和可视化
- **Uvicorn**: ASGI服务器

## 常用命令

### 开发环境
```bash
# 启动开发环境
./scripts/dev-deploy.sh

# 运行测试
python -m pytest tests/ -v

# 代码格式化
python -m black src/ tests/
python -m isort src/ tests/

# 代码检查
python -m flake8 src/ tests/
```

### 生产部署
```bash
# 完整部署
./scripts/deploy.sh

# 服务管理
docker-compose up -d
docker-compose down
docker-compose logs -f
```

### 前端开发
```bash
cd frontend
npm run dev          # 开发服务器
npm run build        # 构建生产版本
npm run lint         # 代码检查
```

## 配置管理
- 环境变量: `.env` 文件
- 应用配置: `config/config.yaml`
- MCP服务器: `config/mcp_servers.json`