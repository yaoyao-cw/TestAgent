# TestAgent 项目结构

## 根目录结构
```
TestAgent/
├── src/                    # 主要源代码
├── frontend/              # React前端应用
├── tests/                 # 测试文件
├── config/                # 配置文件
├── data/                  # 数据存储
├── docs/                  # 项目文档
├── scripts/               # 部署和工具脚本
├── monitoring/            # 监控配置
├── nginx/                 # Nginx配置
└── demos/                 # 演示和示例
```

## 核心源码结构 (src/)
- **agents/**: 各种AI代理实现（协调器、规划器、研究员等）
- **server/**: FastAPI服务器和API端点
- **services/**: 核心服务（LLM、RAG、缓存等）
- **tools/**: 工具集成（Python REPL、MCP、文档解析）
- **models/**: 数据模型和Pydantic schemas
- **utils/**: 通用工具函数

## 前端结构 (frontend/)
- **src/components/**: React组件
- **src/pages/**: 页面组件
- **src/hooks/**: 自定义React hooks
- **src/services/**: API调用服务
- **src/types/**: TypeScript类型定义
- **src/utils/**: 前端工具函数

## 配置和数据
- **config/**: YAML配置文件和MCP服务器配置
- **data/vectordb/**: ChromaDB向量数据库存储
- **data/documents/**: 上传的文档文件
- **data/cache/**: 缓存数据
- **logs/**: 应用日志文件
- **backups/**: 数据备份

## 部署相关
- **scripts/**: 部署脚本（dev-deploy.sh, deploy.sh等）
- **docker-compose.yml**: 生产环境容器编排
- **docker-compose.dev.yml**: 开发环境容器编排
- **Dockerfile**: 应用容器构建文件
- **nginx/**: Nginx反向代理配置

## 开发约定
- Python代码遵循PEP 8规范
- 使用Black进行代码格式化
- 使用pytest进行测试
- 前端使用ESLint和Prettier
- 所有配置文件都有对应的example文件
- 日志统一存储在logs/目录
- 敏感信息通过环境变量管理