# 外部服务集成模块

本模块实现了智能测试平台的外部服务集成功能，包括LiteLLM统一接口、Redis缓存服务、服务健康检查和监控、服务降级和故障转移策略。

## 功能特性

### 1. LiteLLM统一接口
- 支持多个LLM提供商（OpenAI、Anthropic、Google、Azure、DeepSeek、Kimi、Qwen等）
- 统一的API调用接口
- 自动故障转移和负载均衡
- 调用指标和成本统计
- 健康检查和监控

### 2. Redis缓存服务
- 异步Redis客户端
- 会话存储支持
- 缓存操作封装
- 连接池管理
- 性能指标监控

### 3. 服务健康检查和监控
- 定期健康检查
- 服务状态监控
- 告警机制
- 性能指标收集
- 故障检测和恢复

### 4. 服务注册和发现
- 服务注册中心
- 服务优先级管理
- 动态服务发现
- 标签和分类支持

### 5. 故障转移和降级
- 自动故障检测
- 服务降级策略
- 故障转移机制
- 自动恢复功能

## 模块结构

```
src/services/
├── __init__.py                 # 模块入口
├── health_monitor.py          # 健康监控系统
├── service_registry.py        # 服务注册中心
├── litellm_service.py         # LiteLLM服务
├── redis_service.py           # Redis服务
├── external_service_manager.py # 外部服务管理器
├── config_loader.py           # 配置加载器
├── startup.py                 # 启动脚本
├── api_endpoints.py           # API端点
├── fastapi_integration.py     # FastAPI集成示例
├── integration_test.py        # 集成测试
└── README.md                  # 文档
```

## 快速开始

### 1. 基本使用

```python
import asyncio
from src.services import startup, shutdown

async def main():
    # 初始化外部服务
    success = await startup()
    if success:
        print("外部服务启动成功")
        
        # 使用服务...
        
    # 关闭服务
    await shutdown()

asyncio.run(main())
```

### 2. FastAPI集成

```python
from src.services.fastapi_integration import create_app_with_services

app = create_app_with_services()

# 运行应用
# uvicorn src.services.fastapi_integration:app --host 0.0.0.0 --port 8000
```

### 3. 手动服务管理

```python
from src.services import get_external_service_manager

async def example():
    service_manager = get_external_service_manager()
    
    # 初始化服务
    await service_manager.initialize()
    
    # 获取LiteLLM服务
    litellm_service = service_manager.get_service("litellm")
    if litellm_service:
        response = await litellm_service.complete(
            messages=[{"role": "user", "content": "Hello"}],
            provider="openai"
        )
        print(response["content"])
    
    # 获取Redis服务
    redis_service = service_manager.get_service("redis")
    if redis_service:
        await redis_service.set("test_key", "test_value")
        value = await redis_service.get("test_key")
        print(value)
    
    # 关闭服务
    await service_manager.shutdown()
```

## 配置说明

### 环境变量配置

```bash
# LLM配置
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
DEEPSEEK_API_KEY=your_deepseek_key
KIMI_API_KEY=your_kimi_key
QWEN_API_KEY=your_qwen_key

# Redis配置
REDIS_URL=redis://localhost:6379/0
# 或者
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password

# E2B沙盒配置
E2B_API_KEY=your_e2b_key
```

### 配置文件

在 `config/config.yaml` 中配置：

```yaml
llm:
  provider: openai
  model: gpt-3.5-turbo
  api_key: ${OPENAI_API_KEY}
  temperature: 0.7
  max_tokens: 2000
  timeout: 60

cache:
  redis_url: ${REDIS_URL}
  ttl: 3600

sandbox:
  e2b_api_key: ${E2B_API_KEY}
  prefer_e2b: true
  timeout: 60
```

## API端点

### 服务状态
- `GET /api/services/status` - 获取所有服务状态
- `GET /api/services/statistics` - 获取服务统计信息
- `GET /api/services/health` - 获取健康监控摘要

### 服务管理
- `POST /api/services/initialize` - 初始化所有服务
- `POST /api/services/shutdown` - 关闭所有服务
- `POST /api/services/restart/{service_name}` - 重启指定服务
- `POST /api/services/stop/{service_name}` - 停止指定服务

### LiteLLM相关
- `GET /api/services/litellm/providers` - 获取支持的提供商
- `GET /api/services/litellm/metrics` - 获取LiteLLM指标

### Redis相关
- `GET /api/services/redis/metrics` - 获取Redis指标

### 配置信息
- `GET /api/services/config` - 获取服务配置（脱敏）

## 健康检查

系统提供多层次的健康检查：

1. **服务级健康检查**：检查每个服务的可用性
2. **应用级健康检查**：检查整体应用状态
3. **API健康检查**：通过HTTP端点检查

### 健康状态

- `HEALTHY` - 服务正常运行
- `DEGRADED` - 服务运行但性能降级
- `UNHEALTHY` - 服务不可用
- `UNKNOWN` - 服务状态未知

## 故障处理

### 自动故障转移

当主要服务失败时，系统会：

1. 检测服务故障
2. 更新服务状态
3. 触发告警
4. 启动故障转移（如果配置）
5. 尝试自动恢复

### 手动故障处理

```python
from src.services import get_external_service_manager

service_manager = get_external_service_manager()

# 重启失败的服务
await service_manager.restart_service("redis")

# 检查服务状态
status = service_manager.get_service_status("redis")
print(f"Redis状态: {status.value}")
```

## 监控和指标

### LiteLLM指标
- 总调用次数
- 成功/失败次数
- 平均响应时间
- Token使用量
- 成本统计

### Redis指标
- 操作次数
- 缓存命中率
- 内存使用情况
- 连接数

### 健康监控指标
- 服务可用性
- 响应时间
- 错误率
- 正常运行时间

## 测试

### 运行集成测试

```bash
python src/services/integration_test.py
```

### 运行启动测试

```bash
python src/services/startup.py
```

### 测试FastAPI集成

```bash
python src/services/fastapi_integration.py
```

## 最佳实践

### 1. 服务初始化
- 在应用启动时初始化服务
- 使用生命周期管理器
- 处理初始化失败

### 2. 错误处理
- 实现重试机制
- 使用故障转移
- 记录详细日志

### 3. 性能优化
- 使用连接池
- 启用缓存
- 监控性能指标

### 4. 安全考虑
- 保护API密钥
- 使用环境变量
- 限制访问权限

## 故障排除

### 常见问题

1. **LiteLLM初始化失败**
   - 检查API密钥配置
   - 验证网络连接
   - 查看日志错误信息

2. **Redis连接失败**
   - 检查Redis服务状态
   - 验证连接配置
   - 检查网络和防火墙

3. **健康检查超时**
   - 调整超时设置
   - 检查服务响应时间
   - 优化网络配置

### 日志查看

```bash
# 查看服务日志
tail -f logs/testagent.log | grep -E "(service|health|redis|litellm)"
```

## 扩展开发

### 添加新服务

1. 创建服务类
2. 实现健康检查器
3. 注册到服务管理器
4. 添加配置支持
5. 编写测试

### 自定义健康检查

```python
from src.services.health_monitor import HealthChecker, HealthCheckResult, HealthStatus

class CustomHealthChecker(HealthChecker):
    async def check_health(self) -> HealthCheckResult:
        # 实现自定义健康检查逻辑
        return HealthCheckResult(
            service_name="custom_service",
            status=HealthStatus.HEALTHY,
            response_time=0.1,
            timestamp=datetime.now(),
            message="服务正常"
        )
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 编写测试
4. 提交代码
5. 创建Pull Request

## 许可证

本项目采用MIT许可证。