# RAG知识库接入中间层

## 概述

RAG知识库接入中间层是TestAgent项目的核心组件之一，提供了统一的RAG服务接口和多服务管理功能。该中间层支持多种RAG服务的接入，包括ChromaDB、RAGFlow、QAnything和自研RAG服务，并提供主服务和降级策略、健康检查和故障转移机制。

## 核心特性

### 1. 统一服务接口
- **RAGServiceInterface**: 定义了所有RAG服务的标准接口
- **Document**: 统一的文档数据模型
- **SearchResult**: 标准化的搜索结果格式
- **ServiceHealthInfo**: 服务健康状态信息

### 2. 多服务适配器
- **ChromaDBAdapter**: 集成现有ChromaDB功能
- **RAGFlowAdapter**: 支持RAGFlow API调用
- **QAnythingAdapter**: 实现QAnything服务集成
- **CustomRAGAdapter**: 支持自研RAG服务接入

### 3. 智能服务管理
- **RAGServiceManager**: 多服务统一管理
- **服务优先级**: 支持primary、secondary、fallback三级优先级
- **故障转移**: 自动切换到可用服务
- **健康检查**: 定期检查服务状态

### 4. 配置管理系统
- **RAGConfigManager**: 配置文件解析和验证
- **动态配置**: 支持运行时配置更新
- **环境变量**: 支持环境变量替换
- **自动重载**: 配置文件变更自动重载

## 快速开始

### 1. 基本配置

创建配置文件 `config/rag_services.yaml`:

```yaml
services:
  chromadb_primary:
    name: "chromadb_primary"
    service_type: "chromadb"
    priority: "primary"
    enabled: true
    config:
      persist_directory: "./data/vectordb"
      collection_name: "testagent_knowledge"
      embedding_model: "all-MiniLM-L6-v2"
      embedding_provider: "sentence_transformers"
    health_check_interval: 60
    max_failures: 3
    failure_timeout: 300

global_settings:
  default_top_k: 5
  default_similarity_threshold: 0.7
  enable_auto_failover: true
```

### 2. 基本使用

```python
import asyncio
from src.rag import RAGConfigManager, Document

async def main():
    # 1. 创建配置管理器
    config_manager = RAGConfigManager("config/rag_services.yaml")
    
    # 2. 加载配置并创建服务管理器
    config = config_manager.load_config()
    service_manager = await config_manager.create_service_manager()
    
    # 3. 添加文档
    document = Document(
        id="doc_001",
        content="这是一个测试文档",
        metadata={"title": "测试", "category": "示例"}
    )
    
    doc_id = await service_manager.add_document(document)
    print(f"文档添加成功: {doc_id}")
    
    # 4. 检索文档
    results = await service_manager.retrieve("测试", top_k=3)
    for result in results:
        print(f"相似度: {result.similarity_score:.3f}")
        print(f"内容: {result.document.content}")
    
    # 5. 清理资源
    await service_manager.stop_health_checks()

asyncio.run(main())
```

### 3. 直接使用适配器

```python
from src.rag.adapters import ChromaDBAdapter
from src.rag.interfaces import Document

async def direct_usage():
    # 创建适配器
    adapter = ChromaDBAdapter(
        service_name="my_chromadb",
        config={
            "persist_directory": "./data/vectordb",
            "collection_name": "my_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_provider": "sentence_transformers"
        }
    )
    
    # 初始化
    await adapter.initialize()
    
    # 使用适配器
    document = Document(id="test", content="测试内容", metadata={})
    await adapter.add_document(document)
    
    results = await adapter.retrieve("测试", top_k=1)
    print(f"找到 {len(results)} 个结果")
```

## 配置详解

### 服务配置

每个服务配置包含以下字段：

- **name**: 服务名称（必需）
- **service_type**: 服务类型（chromadb/ragflow/qanything/custom）
- **priority**: 优先级（primary/secondary/fallback）
- **enabled**: 是否启用
- **config**: 服务特定配置
- **health_check_interval**: 健康检查间隔（秒）
- **max_failures**: 最大失败次数
- **failure_timeout**: 失败后超时时间（秒）

### ChromaDB配置

```yaml
config:
  persist_directory: "./data/vectordb"  # 持久化目录
  collection_name: "default"           # 集合名称
  embedding_model: "all-MiniLM-L6-v2"  # 嵌入模型
  embedding_provider: "sentence_transformers"  # 嵌入服务提供商
```

### RAGFlow配置

```yaml
config:
  api_url: "http://localhost:9380"     # API地址
  api_key: "${RAGFLOW_API_KEY}"        # API密钥（支持环境变量）
  dataset_id: "default"               # 数据集ID
  timeout: 30                         # 请求超时
  max_retries: 3                      # 最大重试次数
```

### QAnything配置

```yaml
config:
  api_url: "http://localhost:8777"     # API地址
  api_key: "${QANYTHING_API_KEY}"      # API密钥
  knowledge_base_id: "default"        # 知识库ID
  timeout: 30                         # 请求超时
  max_retries: 3                      # 最大重试次数
```

### 自研RAG配置

```yaml
config:
  api_url: "http://localhost:8080"     # API地址
  api_key: "${CUSTOM_RAG_API_KEY}"     # API密钥
  model_name: "custom-embedding-model" # 模型名称
  index_name: "default"               # 索引名称
  timeout: 30                         # 请求超时
  max_retries: 3                      # 最大重试次数
  custom_headers:                     # 自定义请求头
    "X-Client-Version": "1.0.0"
```

## 高级功能

### 1. 故障转移

系统会按照优先级自动选择可用服务：

1. **Primary服务**: 优先使用的主服务
2. **Secondary服务**: 主服务不可用时的备用服务
3. **Fallback服务**: 最后的降级服务

### 2. 健康检查

- 定期检查服务健康状态
- 自动标记不健康的服务为不可用
- 支持服务自动恢复

### 3. 配置热重载

```python
# 启用自动重载
await config_manager.enable_auto_reload(check_interval=10)

# 手动更新服务配置
await config_manager.update_service_config(
    "chromadb_primary", 
    {"collection_name": "new_collection"}
)
```

### 4. 监控和统计

```python
# 获取服务状态
status = service_manager.get_service_status("chromadb_primary")
print(f"服务状态: {status}")

# 获取管理器统计
stats = service_manager.get_manager_stats()
print(f"成功率: {stats['success_rate']:.1f}%")
```

## API参考

### RAGServiceInterface

核心接口方法：

- `initialize()`: 初始化服务
- `retrieve(query, top_k, **kwargs)`: 检索文档
- `add_document(document, **kwargs)`: 添加文档
- `add_documents(documents, **kwargs)`: 批量添加文档
- `delete_document(document_id, **kwargs)`: 删除文档
- `update_document(document_id, document, **kwargs)`: 更新文档
- `get_document(document_id, **kwargs)`: 获取文档
- `health_check()`: 健康检查
- `get_service_info()`: 获取服务信息

### RAGServiceManager

管理器方法：

- `add_service(service_config)`: 添加服务
- `initialize_all_services()`: 初始化所有服务
- `retrieve(query, top_k, **kwargs)`: 统一检索接口
- `add_document(document, **kwargs)`: 统一添加文档接口
- `get_service_status(service_name)`: 获取服务状态
- `get_manager_stats()`: 获取统计信息
- `reload_service(service_name, new_config)`: 重载服务

### RAGConfigManager

配置管理方法：

- `load_config(config_path)`: 加载配置
- `save_config(config, config_path)`: 保存配置
- `validate_config(config_data)`: 验证配置
- `create_service_manager(config)`: 创建服务管理器
- `update_service_config(service_name, new_config)`: 更新服务配置
- `enable_auto_reload(check_interval)`: 启用自动重载

## 最佳实践

### 1. 服务配置

- 至少配置一个primary服务
- 为重要应用配置fallback服务
- 合理设置健康检查间隔
- 使用环境变量管理敏感信息

### 2. 错误处理

```python
try:
    results = await service_manager.retrieve("查询")
except RAGServiceException as e:
    logger.error(f"RAG服务异常: {e}")
    # 处理异常
```

### 3. 资源管理

```python
# 使用上下文管理器
async with RAGConfigManager("config.yaml") as config_manager:
    service_manager = await config_manager.create_service_manager()
    # 使用服务管理器
    # 自动清理资源
```

### 4. 性能优化

- 合理设置top_k值
- 使用批量操作提高效率
- 监控服务性能指标
- 定期清理不需要的文档

## 故障排除

### 常见问题

1. **服务初始化失败**
   - 检查配置文件格式
   - 验证服务依赖是否安装
   - 确认网络连接正常

2. **嵌入模型加载失败**
   - 检查模型名称是否正确
   - 确认网络可以访问模型仓库
   - 考虑使用本地模型

3. **API调用失败**
   - 验证API密钥是否正确
   - 检查API服务是否运行
   - 确认请求参数格式

### 调试技巧

- 启用DEBUG日志级别
- 使用健康检查诊断服务状态
- 查看服务统计信息
- 检查配置验证结果

## 扩展开发

### 自定义适配器

```python
from src.rag.interfaces import RAGServiceInterface

class MyCustomAdapter(RAGServiceInterface):
    async def initialize(self) -> bool:
        # 实现初始化逻辑
        pass
    
    async def retrieve(self, query: str, top_k: int = 5, **kwargs):
        # 实现检索逻辑
        pass
    
    # 实现其他必需方法...
```

### 自定义配置验证

```python
def custom_validator(config_data):
    # 自定义验证逻辑
    errors = []
    warnings = []
    
    # 验证逻辑...
    
    return errors, warnings
```

## 更新日志

### v1.0.0
- 初始版本发布
- 支持ChromaDB、RAGFlow、QAnything、自研RAG
- 实现统一服务接口和管理器
- 提供配置管理和健康检查功能