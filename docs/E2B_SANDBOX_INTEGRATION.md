# E2B Sandbox集成文档

## 概述

本文档描述了TestAgent项目中E2B Sandbox的集成实现，包括强隔离代码执行环境、资源限制控制和错误处理机制。

## 架构设计

### 核心组件

1. **E2BSandboxExecutor** - E2B沙盒执行器
2. **FallbackSandboxExecutor** - 回退沙盒执行器
3. **UnifiedSandboxExecutor** - 统一沙盒接口
4. **EnhancedSandboxExecutor** - 增强沙盒执行器（用于Executor智能体）

### 设计原则

- **强隔离优先**: 优先使用E2B提供的云端强隔离环境
- **智能回退**: E2B不可用时自动回退到本地沙盒
- **统一接口**: 提供一致的API接口，屏蔽底层实现差异
- **资源控制**: 严格的超时、内存和CPU限制
- **安全保障**: 完整的错误处理和恶意代码防护

## 功能特性

### 1. 强隔离执行环境

#### E2B Sandbox特性
- 云端容器化隔离环境
- 完全隔离的文件系统
- 网络访问控制
- 资源使用监控
- 自动环境清理

#### 回退沙盒特性
- 本地临时目录隔离
- 进程级别隔离
- 基本的资源限制
- 文件系统访问控制

### 2. 多种执行模式

```python
# Python代码片段执行
result = await executor.execute_python_code('print("Hello World!")')

# Python脚本文件执行
result = await executor.execute_python_script(script_content, "script.py")

# pytest测试执行
result = await executor.execute_pytest_script(test_content, "test_example.py")
```

### 3. 资源限制和控制

- **执行超时**: 默认60秒，可配置
- **内存限制**: 默认512MB，可配置
- **CPU限制**: 默认1核心，可配置
- **磁盘使用**: 临时目录大小限制

### 4. 完整的结果处理

```python
{
    'success': True,                    # 执行是否成功
    'stdout': 'Hello World!',          # 标准输出
    'stderr': '',                       # 错误输出
    'return_code': 0,                   # 返回码
    'execution_time': 0.123,            # 执行时间（秒）
    'memory_usage': None,               # 内存使用（如果可用）
    'error': None,                      # 错误信息
    'sandbox_type': 'e2b',              # 沙盒类型
    'sandbox_id': 'sandbox_123',        # 沙盒ID
    'timestamp': '2025-01-01T12:00:00', # 时间戳
    'test_results': {...}               # pytest结果（如果适用）
}
```

## 配置说明

### 环境变量配置

```bash
# E2B API密钥
E2B_API_KEY=your_e2b_api_key_here
```

### 配置文件 (config/sandbox.yaml)

```yaml
# 沙盒基本配置
prefer_e2b: true                    # 优先使用E2B
e2b_api_key: null                   # E2B API密钥
e2b_template_id: "python3"          # E2B模板ID
timeout: 60                         # 执行超时时间
memory_limit: "512m"                # 内存限制
cpu_limit: 1.0                      # CPU限制
max_sandboxes: 3                    # 最大沙盒数量

# 安全设置
security:
  enable_code_scanning: true        # 启用代码扫描
  forbidden_modules:                # 禁止的模块
    - os.system
    - subprocess.call
    - eval
    - exec
  forbidden_paths:                  # 禁止访问的路径
    - "/etc"
    - "/proc"
    - "/sys"

# 监控设置
monitoring:
  enable_monitoring: true           # 启用监控
  monitoring_interval: 1            # 监控间隔
  log_execution: true               # 记录执行日志
```

## 使用示例

### 1. 基本使用

```python
import asyncio
from src.tools.unified_sandbox import UnifiedSandboxExecutor

async def basic_example():
    async with UnifiedSandboxExecutor() as executor:
        # 执行Python代码
        result = await executor.execute_python_code('''
import json
data = {"message": "Hello", "value": 42}
print(json.dumps(data, indent=2))
''')
        
        print(f"成功: {result['success']}")
        print(f"输出: {result['stdout']}")
        print(f"沙盒类型: {result['sandbox_type']}")

asyncio.run(basic_example())
```

### 2. 脚本执行

```python
async def script_example():
    script_content = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
'''
    
    async with UnifiedSandboxExecutor() as executor:
        result = await executor.execute_python_script(
            script_content, 
            "fibonacci.py"
        )
        
        print(f"脚本执行成功: {result['success']}")
        print(f"执行时间: {result['execution_time']:.2f}秒")
        print(result['stdout'])
```

### 3. pytest测试执行

```python
async def pytest_example():
    test_content = '''
import pytest

def test_addition():
    assert 1 + 1 == 2

def test_multiplication():
    assert 2 * 3 == 6

def test_division():
    assert 10 / 2 == 5

def test_failure():
    assert 1 == 2  # 这个测试会失败
'''
    
    async with UnifiedSandboxExecutor() as executor:
        result = await executor.execute_pytest_script(
            test_content,
            "test_math.py"
        )
        
        print(f"pytest执行: {result['success']}")
        test_results = result.get('test_results', {})
        print(f"测试结果: {test_results}")
```

### 4. 便捷函数使用

```python
from src.tools.unified_sandbox import execute_code_safely

async def convenience_example():
    # 安全执行代码
    result = await execute_code_safely(
        'print("Hello from convenience function!")',
        execution_type="python",
        timeout=30
    )
    
    print(f"执行成功: {result.is_successful()}")
    print(f"有输出: {result.has_output()}")
    print(f"沙盒类型: {result.sandbox_type}")
    print(f"输出: {result.stdout}")
```

### 5. Executor智能体集成

```python
from src.agents.executor import ExecutorAgent
from src.models.workspace import GlobalState

async def executor_agent_example():
    global_state = GlobalState()
    executor_agent = ExecutorAgent(global_state)
    
    # 模拟输入数据
    input_data = AgentInput(
        data={"task_id": "test_task"},
        metadata={"source": "test"}
    )
    
    # 执行智能体流程
    state = executor_agent.load(input_data)
    state = await executor_agent.llm(state)
    output = executor_agent.router(state)
    
    print(f"执行结果: {output.data}")
```

## 安全考虑

### 1. 代码执行安全

- **强隔离环境**: E2B提供完全隔离的容器环境
- **资源限制**: 严格的CPU、内存、磁盘使用限制
- **超时保护**: 自动终止长时间运行的代码
- **恶意代码检测**: 基本的代码安全扫描

### 2. 文件系统安全

- **临时目录隔离**: 所有文件操作限制在临时目录
- **路径访问控制**: 禁止访问系统关键目录
- **自动清理**: 执行完成后自动清理临时文件

### 3. 网络安全

- **网络访问控制**: 可配置的网络访问策略
- **域名白名单**: 限制可访问的外部域名
- **端口限制**: 限制可使用的网络端口

## 性能优化

### 1. 沙盒池管理

```python
from src.tools.e2b_sandbox import E2BSandboxManager

# 使用沙盒管理器
manager = E2BSandboxManager(max_sandboxes=3)

async with manager.get_sandbox() as sandbox:
    result = await sandbox.execute_python_code('print("Hello")')
    await manager.return_sandbox(sandbox)
```

### 2. 缓存策略

- **结果缓存**: 缓存相同代码的执行结果
- **环境预热**: 预先启动沙盒环境
- **连接复用**: 复用E2B连接减少启动时间

### 3. 并发执行

```python
import asyncio

async def concurrent_execution():
    tasks = []
    for i in range(5):
        task = execute_code_safely(
            f'print("Task {i}")',
            execution_type="python"
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        print(f"Task {i}: {result.stdout.strip()}")
```

## 错误处理

### 1. 错误类型

- **超时错误**: 代码执行超时
- **内存错误**: 内存使用超限
- **语法错误**: Python代码语法错误
- **运行时错误**: 代码执行时异常
- **沙盒错误**: 沙盒环境异常

### 2. 错误恢复策略

```python
async def error_handling_example():
    try:
        async with UnifiedSandboxExecutor(timeout=5) as executor:
            # 这段代码会超时
            result = await executor.execute_python_code('''
import time
time.sleep(10)
print("This won't print")
''')
            
    except Exception as e:
        print(f"执行失败: {e}")
        # 实现错误恢复逻辑
```

### 3. 日志记录

所有执行过程都会记录详细日志：

```
2025-01-01 12:00:00 - e2b_sandbox - INFO - 启动E2B沙盒环境
2025-01-01 12:00:01 - e2b_sandbox - INFO - 在E2B沙盒中执行Python代码
2025-01-01 12:00:02 - e2b_sandbox - INFO - 代码执行完成，成功: True, 耗时: 0.12秒
```

## 监控和调试

### 1. 执行监控

- **实时状态**: 监控沙盒执行状态
- **资源使用**: 跟踪CPU、内存使用情况
- **执行时间**: 记录详细的执行时间统计
- **错误统计**: 统计各类错误的发生频率

### 2. 调试支持

```python
# 启用调试模式
executor = UnifiedSandboxExecutor(prefer_e2b=False)

# 获取系统信息
async with executor:
    info = await executor.get_system_info()
    print(f"调试信息: {info}")
```

### 3. 性能分析

```python
import time

async def performance_analysis():
    start_time = time.time()
    
    async with UnifiedSandboxExecutor() as executor:
        result = await executor.execute_python_code('print("Performance test")')
        
    total_time = time.time() - start_time
    execution_time = result['execution_time']
    overhead = total_time - execution_time
    
    print(f"总时间: {total_time:.3f}秒")
    print(f"执行时间: {execution_time:.3f}秒")
    print(f"开销时间: {overhead:.3f}秒")
```

## 最佳实践

### 1. 资源管理

- 始终使用异步上下文管理器
- 及时释放沙盒资源
- 合理设置超时时间
- 监控资源使用情况

### 2. 错误处理

- 实现完整的异常捕获
- 提供有意义的错误信息
- 实现重试机制
- 记录详细的错误日志

### 3. 安全实践

- 验证输入代码的安全性
- 限制可执行的操作
- 监控异常行为
- 定期更新安全策略

### 4. 性能优化

- 使用沙盒池减少启动开销
- 缓存常用的执行结果
- 并发执行多个任务
- 优化代码执行路径

## 故障排除

### 1. 常见问题

**Q: E2B沙盒启动失败**
A: 检查E2B_API_KEY是否正确配置，网络连接是否正常

**Q: 代码执行超时**
A: 增加timeout设置，或优化代码逻辑

**Q: 内存使用超限**
A: 增加memory_limit设置，或优化代码内存使用

**Q: 回退沙盒权限错误**
A: 检查临时目录权限，确保Python有足够的文件系统权限

### 2. 调试步骤

1. 检查配置文件和环境变量
2. 查看详细的错误日志
3. 测试基本的代码执行功能
4. 验证网络连接和API密钥
5. 检查系统资源使用情况

### 3. 性能调优

1. 监控沙盒启动时间
2. 分析代码执行性能
3. 优化资源使用配置
4. 调整并发执行参数

## 扩展开发

### 1. 自定义沙盒执行器

```python
from src.tools.unified_sandbox import UnifiedSandboxExecutor

class CustomSandboxExecutor(UnifiedSandboxExecutor):
    async def execute_custom_code(self, code: str, language: str):
        # 实现自定义代码执行逻辑
        pass
```

### 2. 添加新的执行模式

```python
async def execute_javascript_code(self, code: str):
    # 添加JavaScript代码执行支持
    node_code = f"console.log({code})"
    return await self.sandbox.run_command(f"node -e '{node_code}'")
```

### 3. 集成其他沙盒服务

```python
class DockerSandboxExecutor:
    async def execute_in_docker(self, code: str, image: str):
        # 使用Docker容器执行代码
        pass
```

## 总结

E2B Sandbox集成为TestAgent提供了强大的代码执行能力，通过多层安全防护、智能回退机制和完整的资源控制，确保了代码执行的安全性和可靠性。该实现支持多种执行模式，提供了丰富的配置选项和监控功能，能够满足各种测试场景的需求。