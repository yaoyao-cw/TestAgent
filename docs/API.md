# TestAgent API 文档

## 概述

TestAgent API 提供了一组RESTful接口，用于与TestAgent系统交互。通过这些接口，您可以创建测试任务、查询任务状态、获取测试结果等。

## 基本信息

- **基础URL**: `http://localhost:8000`
- **内容类型**: `application/json`
- **响应格式**: JSON

## 认证

目前API不需要认证。在生产环境中，建议实现适当的认证机制。

## API端点

### 健康检查

#### GET /health

检查API服务器的健康状态。

**请求示例**:

```bash
curl -X GET http://localhost:8000/health
```

**响应示例**:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2023-06-01T12:00:00.000Z"
}
```

### 任务管理

#### POST /tasks

创建新的测试任务。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_type | string | 是 | 任务类型，如'test_case_generation' |
| task_topic | string | 是 | 任务主题或描述 |
| context | string | 否 | 任务上下文信息 |
| code_snippets | array | 否 | 相关代码片段 |
| requirements | array | 否 | 相关需求 |
| locale | string | 否 | 语言设置，如'zh-CN'或'en-US'，默认'zh-CN' |
| timeout | integer | 否 | 执行超时时间（秒），默认300 |
| config | object | 否 | 额外配置参数 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "test_case_generation",
    "task_topic": "用户登录功能测试",
    "context": "需要测试用户登录功能，包括正常登录、错误密码和账号锁定场景",
    "code_snippets": ["def login(username, password): pass"],
    "locale": "zh-CN"
  }'
```

**响应示例**:

```json
{
  "task_id": "task_12345",
  "status": "pending",
  "created_at": "2023-06-01T12:00:00.000Z",
  "message": "任务已创建，正在处理中"
}
```

#### GET /tasks/{task_id}

获取指定任务的详细信息和状态。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X GET http://localhost:8000/tasks/task_12345
```

**响应示例**:

```json
{
  "task_id": "task_12345",
  "status": "completed",
  "task_type": "test_case_generation",
  "task_topic": "用户登录功能测试",
  "created_at": "2023-06-01T12:00:00.000Z",
  "updated_at": "2023-06-01T12:05:00.000Z",
  "result": {
    "execution_plan": {
      "title": "用户登录功能测试计划",
      "steps": [...]
    },
    "report": {
      "content": "测试报告内容...",
      "summary": "测试总结..."
    }
  }
}
```

#### GET /tasks

获取所有任务的列表。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| status | string | 否 | 按状态过滤：pending, running, completed, failed |
| task_type | string | 否 | 按任务类型过滤 |
| limit | integer | 否 | 返回结果数量限制，默认20 |
| offset | integer | 否 | 结果偏移量，默认0 |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/tasks?status=completed&limit=10"
```

**响应示例**:

```json
{
  "tasks": [
    {
      "task_id": "task_12345",
      "status": "completed",
      "task_type": "test_case_generation",
      "task_topic": "用户登录功能测试",
      "created_at": "2023-06-01T12:00:00.000Z",
      "updated_at": "2023-06-01T12:05:00.000Z"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

#### DELETE /tasks/{task_id}

取消或删除指定的任务。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X DELETE http://localhost:8000/tasks/task_12345
```

**响应示例**:

```json
{
  "message": "任务已取消",
  "task_id": "task_12345"
}
```

#### POST /tasks/{task_id}/retry

重试失败的任务。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X POST http://localhost:8000/tasks/task_12345/retry
```

**响应示例**:

```json
{
  "message": "任务重试已启动",
  "task_id": "task_12345",
  "status": "pending"
}
```

### 人机协作

#### GET /collaboration/reviews

获取待审查的计划列表。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| status | string | 否 | 按状态过滤：pending, approved, rejected |

**请求示例**:

```bash
curl -X GET http://localhost:8000/collaboration/reviews
```

**响应示例**:

```json
{
  "reviews": [
    {
      "review_id": "review_123",
      "plan_id": "plan_456",
      "status": "pending",
      "submitted_at": "2023-06-01T12:00:00.000Z",
      "plan": {
        "title": "用户登录功能测试计划",
        "steps": [...]
      }
    }
  ]
}
```

#### POST /collaboration/reviews/{review_id}/approve

批准待审查的计划。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| review_id | string | 是 | 审查ID |

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| comment | string | 否 | 批准意见 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/collaboration/reviews/review_123/approve \
  -H "Content-Type: application/json" \
  -d '{"comment": "计划看起来很好，批准执行"}'
```

**响应示例**:

```json
{
  "message": "计划已批准",
  "review_id": "review_123",
  "status": "approved"
}
```

#### POST /collaboration/reviews/{review_id}/reject

拒绝待审查的计划。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| review_id | string | 是 | 审查ID |

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| comment | string | 是 | 拒绝原因 |
| feedback | string | 否 | 改进建议 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/collaboration/reviews/review_123/reject \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "测试覆盖不够全面",
    "feedback": "建议增加边界条件测试"
  }'
```

**响应示例**:

```json
{
  "message": "计划已拒绝",
  "review_id": "review_123",
  "status": "rejected"
}
```

#### POST /collaboration/feedback

提供反馈以改进报告或计划。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| target_id | string | 是 | 目标ID（任务ID或计划ID） |
| target_type | string | 是 | 目标类型：task, plan, report |
| feedback | string | 是 | 反馈内容 |
| feedback_type | string | 否 | 反馈类型：improvement, correction, addition |

**请求示例**:

```bash
curl -X POST http://localhost:8000/collaboration/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "task_12345",
    "target_type": "report",
    "feedback": "报告中缺少性能测试部分",
    "feedback_type": "addition"
  }'
```

**响应示例**:

```json
{
  "message": "反馈已收到，正在处理",
  "feedback_id": "feedback_789"
}
```

### 系统管理

#### GET /system/status

获取系统状态信息。

**请求示例**:

```bash
curl -X GET http://localhost:8000/system/status
```

**响应示例**:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 3600,
  "workflow_status": {
    "status": "ready",
    "active_executions": 2
  },
  "execution_stats": {
    "total_tasks": 150,
    "completed_tasks": 140,
    "failed_tasks": 5,
    "pending_tasks": 5
  },
  "system_resources": {
    "cpu_usage": 25.5,
    "memory_usage": 60.2,
    "disk_usage": 45.8
  }
}
```

#### POST /system/cleanup

清理系统资源，删除过期的任务和缓存。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| older_than_days | integer | 否 | 删除多少天前的数据，默认30 |
| include_completed | boolean | 否 | 是否包括已完成的任务，默认false |

**请求示例**:

```bash
curl -X POST http://localhost:8000/system/cleanup \
  -H "Content-Type: application/json" \
  -d '{"older_than_days": 7, "include_completed": true}'
```

**响应示例**:

```json
{
  "message": "系统清理完成",
  "cleaned_items": {
    "tasks": 25,
    "cache_entries": 150,
    "log_files": 10
  }
}
```

## 错误处理

API使用标准的HTTP状态码来表示请求的结果：

- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未授权访问
- `404 Not Found` - 资源不存在
- `500 Internal Server Error` - 服务器内部错误

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_TASK_TYPE",
    "message": "不支持的任务类型",
    "details": "支持的任务类型包括: test_case_generation, test_execution, test_analysis"
  }
}
```

### 常见错误代码

| 错误代码 | 描述 |
|----------|------|
| INVALID_TASK_TYPE | 无效的任务类型 |
| TASK_NOT_FOUND | 任务不存在 |
| TASK_ALREADY_COMPLETED | 任务已完成，无法修改 |
| INVALID_PARAMETERS | 请求参数无效 |
| EXECUTION_TIMEOUT | 执行超时 |
| SYSTEM_OVERLOAD | 系统负载过高 |

## 限制和配额

- **请求频率限制**: 每分钟最多100个请求
- **并发任务限制**: 最多同时执行10个任务
- **任务超时**: 默认5分钟，最长30分钟
- **文件大小限制**: 代码片段最大10MB

## WebSocket支持

对于需要实时更新的场景，API还提供WebSocket连接：

### 连接端点

```
ws://localhost:8000/ws/tasks/{task_id}
```

### 消息格式

```json
{
  "type": "status_update",
  "task_id": "task_12345",
  "status": "running",
  "progress": 45,
  "message": "正在生成测试用例..."
}
```

### 使用示例

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/task_12345');

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('任务状态更新:', data);
};
```

## SDK和客户端库

### Python客户端

```python
from testagent_client import TestAgentClient

client = TestAgentClient(base_url="http://localhost:8000")

# 创建任务
task = client.create_task(
    task_type="test_case_generation",
    task_topic="用户登录功能测试",
    context="需要测试用户登录功能"
)

# 等待任务完成
result = client.wait_for_completion(task.task_id)
print(result.report.content)
```

### JavaScript客户端

```javascript
import { TestAgentClient } from 'testagent-js-client';

const client = new TestAgentClient('http://localhost:8000');

// 创建任务
const task = await client.createTask({
  taskType: 'test_case_generation',
  taskTopic: '用户登录功能测试',
  context: '需要测试用户登录功能'
});

// 监听任务状态
client.onTaskUpdate(task.taskId, (update) => {
  console.log('任务状态:', update.status);
});
```

## 最佳实践

1. **异步处理**: 对于长时间运行的任务，使用异步方式处理，通过轮询或WebSocket获取状态更新。

2. **错误重试**: 实现适当的重试机制，特别是对于网络相关的错误。

3. **资源清理**: 定期清理不需要的任务和数据，避免系统资源耗尽。

4. **监控和日志**: 监控API使用情况和性能指标，记录详细的操作日志。

5. **安全考虑**: 在生产环境中实现适当的认证和授权机制。

## 版本控制

API使用语义化版本控制。当前版本为v1.0.0。

- **主版本号**: 不兼容的API更改
- **次版本号**: 向后兼容的功能添加
- **修订版本号**: 向后兼容的问题修复

## 支持和反馈

如有问题或建议，请通过以下方式联系：

- GitHub Issues: https://github.com/yourusername/TestAgent/issues
- 邮箱: support@testagent.com
- 文档: https://docs.testagent.com