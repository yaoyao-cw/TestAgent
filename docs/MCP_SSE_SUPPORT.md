# MCP SSE支持文档

TestAgent现在支持两种MCP（Model Context Protocol）连接类型：

1. **stdio** - 标准输入输出连接（原有支持）
2. **sse** - Server-Sent Events连接（新增支持）

## 配置说明

### stdio配置

```json
{
  "mcpServers": {
    "stdio-server": {
      "connection_type": "stdio",
      "command": "uvx",
      "args": ["example-mcp-server"],
      "env": {
        "LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "timeout": 30,
      "retry_count": 3,
      "auto_restart": true
    }
  }
}
```

### SSE配置

```json
{
  "mcpServers": {
    "sse-server": {
      "connection_type": "sse",
      "url": "https://api.example.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer your-token-here",
        "Content-Type": "application/json"
      },
      "disabled": false,
      "timeout": 30,
      "retry_count": 3,
      "auto_restart": true
    }
  }
}
```

## 配置参数说明

### 通用参数

- `connection_type`: 连接类型，必须是 "stdio" 或 "sse"
- `disabled`: 是否禁用服务器（默认：false）
- `timeout`: 连接超时时间，单位秒（默认：30）
- `retry_count`: 重试次数（默认：3）
- `auto_restart`: 是否自动重启（默认：true）

### stdio特有参数

- `command`: 启动命令（必需）
- `args`: 命令参数列表（可选）
- `env`: 环境变量字典（可选）

### SSE特有参数

- `url`: SSE服务器URL（必需，必须以http://或https://开头）
- `headers`: HTTP请求头字典（可选）

## 使用示例

### Python代码示例

```python
import asyncio
from src.mcp.config import MCPConfig, MCPServerConfig
from src.mcp.server_manager import MCPServerManager
from src.mcp.tool_adapter import MCPToolAdapter

async def main():
    # 创建SSE服务器配置
    sse_config = MCPServerConfig(
        connection_type="sse",
        url="https://api.example.com/mcp/sse",
        headers={"Authorization": "Bearer token"}
    )
    
    # 创建配置
    config = MCPConfig()
    config.add_server("my-sse-server", sse_config)
    
    # 创建管理器
    manager = MCPServerManager(config)
    await manager.start()
    
    # 创建适配器
    adapter = MCPToolAdapter(manager)
    
    # 获取可用工具
    tools = adapter.get_available_tools()
    print(f"可用工具: {len(tools)}")
    
    # 调用工具
    if tools:
        result = await adapter.call_tool(
            tools[0]["full_name"], 
            {"param": "value"}
        )
        print(f"工具调用结果: {result}")
    
    # 关闭管理器
    await manager.stop()

asyncio.run(main())
```

## 技术实现

### SSE传输层

SSE客户端使用`aiohttp-sse-client`库实现：

- 支持异步连接和消息处理
- 自动重连和错误恢复
- 支持自定义HTTP头和认证
- 双向通信（通过HTTP POST发送消息）

### 客户端工厂

使用工厂模式根据配置类型创建相应的客户端：

```python
from src.mcp.client import create_mcp_client

# 自动根据配置类型创建客户端
client = create_mcp_client("server-name", server_config)
```

### 统一接口

无论是stdio还是SSE客户端，都提供相同的接口：

- `connect()` - 建立连接
- `disconnect()` - 断开连接
- `call_tool()` - 调用工具
- `read_resource()` - 读取资源
- `health_check()` - 健康检查

## 依赖要求

SSE支持需要以下额外依赖：

```
aiohttp-sse-client>=0.2.1
```

## 错误处理

SSE客户端包含完善的错误处理：

- 连接失败自动重试
- 网络中断自动重连
- 超时处理和恢复
- 详细的错误日志记录

## 性能考虑

- SSE连接保持长连接，减少连接开销
- 支持并发工具调用
- 内置连接池和资源管理
- 自动清理无效连接

## 安全注意事项

1. **HTTPS**: 生产环境建议使用HTTPS URL
2. **认证**: 使用适当的认证头（如Bearer token）
3. **超时**: 设置合理的超时时间避免资源泄露
4. **重试**: 限制重试次数避免无限重试

## 故障排除

### 常见问题

1. **连接失败**
   - 检查URL是否正确
   - 验证网络连接
   - 确认服务器是否运行

2. **认证失败**
   - 检查Authorization头是否正确
   - 验证token是否有效

3. **超时问题**
   - 增加timeout设置
   - 检查网络延迟

### 调试方法

启用详细日志：

```python
import logging
logging.getLogger("src.mcp").setLevel(logging.DEBUG)
```

## 示例文件

参考 `examples/mcp_sse_example.py` 获取完整的使用示例。