# TestAgent API 文档

## 概述

TestAgent API 提供了一组RESTful接口，用于与TestAgent智能测试代理系统交互。通过这些接口，您可以创建测试任务、管理文档、监控系统状态、配置智能体等。

## 基本信息

- **基础URL**: `http://localhost:8000`
- **API版本**: `v1`
- **内容类型**: `application/json`
- **响应格式**: JSON
- **字符编码**: UTF-8

## 认证

### JWT认证
生产环境中使用JWT令牌进行身份认证：

```bash
# 获取访问令牌
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# 使用令牌访问API
curl -X GET http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer <your_jwt_token>"
```

### API密钥认证
也可以使用API密钥进行认证：

```bash
curl -X GET http://localhost:8000/api/v1/tasks \
  -H "X-API-Key: <your_api_key>"
```

## API端点

### 1. 系统监控

#### GET /api/v1/monitoring/health

检查系统健康状态。

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/monitoring/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "llm_service": "healthy",
    "rag_service": "healthy"
  },
  "uptime": 3600
}
```

#### GET /api/v1/monitoring/metrics

获取系统性能指标。

**请求示例**:
```bash
curl -X GET http://localhost:8000/api/v1/monitoring/metrics
```

**响应示例**:
```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "system": {
    "cpu_usage": 45.2,
    "memory_usage": 68.5,
    "disk_usage": 32.1
  },
  "application": {
    "active_tasks": 5,
    "completed_tasks": 150,
    "error_rate": 0.02,
    "cache_hit_rate": 0.85,
    "average_response_time": 1.2
  },
  "agents": {
    "coordinator": {"status": "active", "tasks_processed": 45},
    "planner": {"status": "active", "tasks_processed": 42},
    "tester": {"status": "active", "tasks_processed": 38},
    "coder": {"status": "active", "tasks_processed": 35}
  }
}
```

#### GET /api/v1/monitoring/status

获取详细系统状态。

**响应示例**:
```json
{
  "system_status": "operational",
  "version": "1.0.0",
  "build": "20240101-1200",
  "environment": "production",
  "components": {
    "api_server": {"status": "healthy", "response_time": 0.05},
    "database": {"status": "healthy", "connections": 10},
    "cache": {"status": "healthy", "memory_usage": "256MB"},
    "llm_service": {"status": "healthy", "model": "gpt-4"},
    "rag_service": {"status": "healthy", "documents": 1500},
    "sandbox": {"status": "healthy", "containers": 3}
  }
}
```

### 2. 任务管理

#### POST /api/v1/tasks/submit

创建新的测试任务。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| title | string | 是 | 任务标题 |
| description | string | 是 | 任务详细描述 |
| task_type | string | 是 | 任务类型：functional_testing, performance_testing, security_testing |
| documents | array | 否 | 相关文档ID列表 |
| priority | string | 否 | 优先级：low, medium, high，默认medium |
| timeout | integer | 否 | 执行超时时间（秒），默认3600 |
| config | object | 否 | 任务配置参数 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "title": "用户登录功能测试",
    "description": "测试用户登录功能的各种场景，包括正常登录、错误密码、账号锁定等",
    "task_type": "functional_testing",
    "documents": ["doc_123", "doc_456"],
    "priority": "high",
    "config": {
      "enable_performance_test": true,
      "test_environment": "staging"
    }
  }'
```

**响应示例**:

```json
{
  "task_id": "task_20240101_001",
  "status": "pending",
  "title": "用户登录功能测试",
  "created_at": "2024-01-01T12:00:00.000Z",
  "estimated_duration": 1800,
  "workspace_path": "data/tasks/task_20240101_001",
  "message": "任务已创建，正在初始化工作空间",
  "creation_status": {
    "current_step": "initialization",
    "progress_percentage": 10.0,
    "step_message": "正在初始化任务工作空间"
  }
}
```

#### GET /api/v1/tasks/{task_id}/status

获取指定任务的状态信息。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X GET http://localhost:8000/api/v1/tasks/task_20240101_001/status \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "task_id": "task_20240101_001",
  "status": "running",
  "title": "用户登录功能测试",
  "current_agent": "tester",
  "current_step": 3,
  "total_steps": 8,
  "progress": 37.5,
  "created_at": "2024-01-01T12:00:00.000Z",
  "updated_at": "2024-01-01T12:15:00.000Z",
  "estimated_completion": "2024-01-01T12:30:00.000Z",
  "creation_status": {
    "status": "completed",
    "current_step": "notification",
    "progress_percentage": 100.0,
    "step_message": "任务创建完成",
    "service_validations": [
      {
        "service_name": "llm_service",
        "is_available": true,
        "response_time": 0.15
      },
      {
        "service_name": "redis_cache",
        "is_available": true,
        "response_time": 0.02
      }
    ]
  },
  "execution_log": [
    {
      "timestamp": "2024-01-01T12:00:00.000Z",
      "agent": "coordinator",
      "action": "task_initialized",
      "message": "任务工作空间已创建"
    },
    {
      "timestamp": "2024-01-01T12:05:00.000Z",
      "agent": "planner",
      "action": "plan_generated",
      "message": "测试计划已生成"
    },
    {
      "timestamp": "2024-01-01T12:15:00.000Z",
      "agent": "tester",
      "action": "test_cases_generating",
      "message": "正在生成测试用例"
    }
  ]
}
```

#### GET /api/v1/tasks/{task_id}

获取任务的完整信息。

**响应示例**:

```json
{
  "task_id": "task_20240101_001",
  "status": "completed",
  "title": "用户登录功能测试",
  "description": "测试用户登录功能的各种场景",
  "task_type": "functional_testing",
  "priority": "high",
  "created_at": "2024-01-01T12:00:00.000Z",
  "completed_at": "2024-01-01T12:30:00.000Z",
  "duration": 1800,
  "workspace_path": "data/tasks/task_20240101_001",
  "documents": ["doc_123", "doc_456"],
  "agents_involved": ["coordinator", "planner", "tester", "coder", "reviewer"],
  "files_generated": [
    "00_Coordinator_Init_v1.md",
    "01_Planner_Plan_v1.md",
    "02_Tester_TestCases_v1.md",
    "03_Coder_Scripts_v1.py",
    "04_Reviewer_Report_v1.md"
  ],
  "metrics": {
    "test_cases_generated": 25,
    "scripts_created": 8,
    "execution_time": 1800,
    "success_rate": 0.96
  }
}
```

#### GET /api/v1/tasks

获取任务列表。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| status | string | 否 | 按状态过滤：pending, running, completed, failed, cancelled |
| task_type | string | 否 | 按任务类型过滤 |
| priority | string | 否 | 按优先级过滤：low, medium, high |
| created_after | string | 否 | 创建时间过滤（ISO8601格式） |
| created_before | string | 否 | 创建时间过滤（ISO8601格式） |
| page | integer | 否 | 页码，默认1 |
| page_size | integer | 否 | 每页数量，默认20，最大100 |
| sort | string | 否 | 排序字段：created_at, updated_at, priority |
| order | string | 否 | 排序方向：asc, desc，默认desc |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/api/v1/tasks?status=completed&task_type=functional_testing&page=1&page_size=10" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "tasks": [
    {
      "task_id": "task_20240101_001",
      "title": "用户登录功能测试",
      "status": "completed",
      "task_type": "functional_testing",
      "priority": "high",
      "created_at": "2024-01-01T12:00:00.000Z",
      "completed_at": "2024-01-01T12:30:00.000Z",
      "duration": 1800,
      "success_rate": 0.96
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_pages": 5,
    "total_items": 45,
    "has_next": true,
    "has_prev": false
  }
}
```

#### GET /api/v1/tasks/{task_id}/report

获取任务测试报告。

**请求示例**:

```bash
curl -X GET http://localhost:8000/api/v1/tasks/task_20240101_001/report \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "task_id": "task_20240101_001",
  "report": {
    "title": "用户登录功能测试报告",
    "summary": {
      "total_test_cases": 25,
      "passed": 24,
      "failed": 1,
      "skipped": 0,
      "success_rate": 0.96,
      "execution_time": 1800
    },
    "test_results": [
      {
        "test_case_id": "TC001",
        "name": "正常登录测试",
        "status": "passed",
        "execution_time": 2.5,
        "details": "用户使用正确的用户名和密码成功登录"
      },
      {
        "test_case_id": "TC002",
        "name": "错误密码测试",
        "status": "failed",
        "execution_time": 1.8,
        "error_message": "预期错误提示未显示",
        "details": "输入错误密码后，系统应显示'密码错误'提示"
      }
    ],
    "recommendations": [
      "修复TC002中的错误提示显示问题",
      "增加密码强度验证测试用例",
      "考虑添加验证码功能的测试"
    ],
    "generated_at": "2024-01-01T12:30:00.000Z"
  }
}
```

#### GET /api/v1/tasks/{task_id}/report/download

下载测试报告文件。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| format | string | 否 | 文件格式：pdf, html, json，默认pdf |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/api/v1/tasks/task_20240101_001/report/download?format=pdf" \
  -H "Authorization: Bearer <token>" \
  -o test_report.pdf
```

#### DELETE /api/v1/tasks/{task_id}

取消或删除指定的任务。

**请求示例**:

```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/task_20240101_001 \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "message": "任务已取消",
  "task_id": "task_20240101_001",
  "status": "cancelled",
  "cancelled_at": "2024-01-01T12:20:00.000Z"
}
```

#### POST /api/v1/tasks/{task_id}/retry

重试失败的任务。

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/task_20240101_001/retry \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "message": "任务重试已启动",
  "task_id": "task_20240101_001",
  "status": "pending",
  "retry_count": 1,
  "restarted_at": "2024-01-01T12:25:00.000Z"
}
```

#### GET /api/v1/tasks/{task_id}/creation-status

获取任务创建状态详情。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X GET http://localhost:8000/api/v1/tasks/task_20240101_001/creation-status \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "task_id": "task_20240101_001",
  "status": "completed",
  "current_step": "notification",
  "progress_percentage": 100.0,
  "step_message": "任务创建完成",
  "created_at": "2024-01-01T12:00:00.000Z",
  "completed_at": "2024-01-01T12:02:00.000Z",
  "duration": 120.5,
  "service_validations": [
    {
      "service_name": "llm_service",
      "is_available": true,
      "response_time": 0.15,
      "timestamp": "2024-01-01T12:00:05.000Z"
    },
    {
      "service_name": "redis_cache",
      "is_available": true,
      "response_time": 0.02,
      "timestamp": "2024-01-01T12:00:05.000Z"
    },
    {
      "service_name": "vector_db",
      "is_available": true,
      "response_time": 0.08,
      "timestamp": "2024-01-01T12:00:05.000Z"
    }
  ],
  "progress_history": [
    {
      "current_step": "initialization",
      "progress_percentage": 10.0,
      "step_message": "正在初始化任务工作空间",
      "timestamp": "2024-01-01T12:00:00.000Z"
    },
    {
      "current_step": "service_validation",
      "progress_percentage": 30.0,
      "step_message": "正在验证服务可用性",
      "timestamp": "2024-01-01T12:00:05.000Z"
    },
    {
      "current_step": "input_validation",
      "progress_percentage": 40.0,
      "step_message": "正在验证输入数据",
      "timestamp": "2024-01-01T12:00:10.000Z"
    },
    {
      "current_step": "resource_allocation",
      "progress_percentage": 60.0,
      "step_message": "正在分配系统资源",
      "timestamp": "2024-01-01T12:00:30.000Z"
    },
    {
      "current_step": "task_generation",
      "progress_percentage": 90.0,
      "step_message": "正在生成任务数据",
      "timestamp": "2024-01-01T12:01:00.000Z"
    },
    {
      "current_step": "persistence",
      "progress_percentage": 98.0,
      "step_message": "正在保存任务数据",
      "timestamp": "2024-01-01T12:01:50.000Z"
    },
    {
      "current_step": "notification",
      "progress_percentage": 100.0,
      "step_message": "任务创建完成",
      "timestamp": "2024-01-01T12:02:00.000Z"
    }
  ]
}
```

#### POST /api/v1/tasks/{task_id}/pause

暂停任务创建或执行。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/task_20240101_001/pause \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "message": "任务已暂停",
  "task_id": "task_20240101_001",
  "status": "paused",
  "paused_at": "2024-01-01T12:15:00.000Z",
  "current_step": "task_generation",
  "progress_percentage": 75.0
}
```

#### POST /api/v1/tasks/{task_id}/resume

恢复暂停的任务。

**路径参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/task_20240101_001/resume \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "message": "任务已恢复",
  "task_id": "task_20240101_001",
  "status": "running",
  "resumed_at": "2024-01-01T12:20:00.000Z",
  "current_step": "task_generation",
  "progress_percentage": 75.0
}
```

#### POST /api/v1/tasks/{task_id}/feedback

为任务提供反馈。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| feedback_type | string | 是 | 反馈类型：plan_review, quality_review, error_handling, general |
| content | string | 是 | 反馈内容 |
| action | string | 否 | 建议操作：approve, reject, modify, retry |
| suggestions | array | 否 | 具体建议列表 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/task_20240101_001/feedback \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "feedback_type": "quality_review",
    "content": "测试用例覆盖不够全面，需要增加边界条件测试",
    "action": "modify",
    "suggestions": [
      "增加输入长度边界测试",
      "添加特殊字符输入测试",
      "考虑并发登录场景"
    ]
  }'
```

**响应示例**:

```json
{
  "message": "反馈已收到并处理",
  "feedback_id": "feedback_001",
  "task_id": "task_20240101_001",
  "status": "processing",
  "estimated_completion": "2024-01-01T12:45:00.000Z"
}
```

### 3. 文档管理

#### POST /api/v1/documents/upload

上传文档到知识库。

**请求参数**:
- **Content-Type**: `multipart/form-data`

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| file | file | 是 | 文档文件 |
| category | string | 否 | 文档分类：requirements, api_spec, design, test_cases |
| title | string | 否 | 文档标题 |
| description | string | 否 | 文档描述 |
| tags | string | 否 | 标签，逗号分隔 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@requirements.pdf" \
  -F "category=requirements" \
  -F "title=用户管理系统需求文档" \
  -F "description=包含用户注册、登录、权限管理等功能需求" \
  -F "tags=用户管理,认证,权限"
```

**响应示例**:

```json
{
  "document_id": "doc_20240101_001",
  "filename": "requirements.pdf",
  "title": "用户管理系统需求文档",
  "category": "requirements",
  "size": 2048576,
  "pages": 25,
  "uploaded_at": "2024-01-01T12:00:00.000Z",
  "processing_status": "processing",
  "message": "文档上传成功，正在处理中"
}
```

#### GET /api/v1/documents

获取文档列表。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| category | string | 否 | 按分类过滤 |
| tags | string | 否 | 按标签过滤，逗号分隔 |
| search | string | 否 | 搜索关键词 |
| page | integer | 否 | 页码，默认1 |
| page_size | integer | 否 | 每页数量，默认20 |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/api/v1/documents?category=requirements&page=1" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "documents": [
    {
      "document_id": "doc_20240101_001",
      "filename": "requirements.pdf",
      "title": "用户管理系统需求文档",
      "category": "requirements",
      "size": 2048576,
      "pages": 25,
      "tags": ["用户管理", "认证", "权限"],
      "uploaded_at": "2024-01-01T12:00:00.000Z",
      "processing_status": "completed"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "total_items": 45
  }
}
```

#### GET /api/v1/documents/{document_id}

获取文档详细信息。

**响应示例**:

```json
{
  "document_id": "doc_20240101_001",
  "filename": "requirements.pdf",
  "title": "用户管理系统需求文档",
  "description": "包含用户注册、登录、权限管理等功能需求",
  "category": "requirements",
  "size": 2048576,
  "pages": 25,
  "tags": ["用户管理", "认证", "权限"],
  "uploaded_at": "2024-01-01T12:00:00.000Z",
  "processing_status": "completed",
  "content_summary": "文档包含用户管理系统的完整功能需求...",
  "metadata": {
    "author": "产品团队",
    "version": "1.2",
    "last_modified": "2024-01-01T10:00:00.000Z"
  }
}
```

#### DELETE /api/v1/documents/{document_id}

删除文档。

**请求示例**:

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/doc_20240101_001 \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "message": "文档已删除",
  "document_id": "doc_20240101_001",
  "deleted_at": "2024-01-01T12:30:00.000Z"
}
```

#### POST /api/v1/documents/search

搜索文档内容。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| query | string | 是 | 搜索查询 |
| top_k | integer | 否 | 返回结果数量，默认10 |
| category | string | 否 | 限制搜索分类 |
| similarity_threshold | float | 否 | 相似度阈值，默认0.7 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/documents/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "用户登录流程",
    "top_k": 5,
    "category": "requirements"
  }'
```

**响应示例**:

```json
{
  "query": "用户登录流程",
  "results": [
    {
      "document_id": "doc_20240101_001",
      "title": "用户管理系统需求文档",
      "content_snippet": "用户登录流程包括输入用户名密码、验证身份、生成会话令牌...",
      "similarity_score": 0.92,
      "page_number": 5,
      "category": "requirements"
    }
  ],
  "total_results": 5,
  "search_time": 0.15
}
```

### 4. 知识库管理

#### POST /api/v1/knowledge/add

手动添加知识条目。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| title | string | 是 | 知识条目标题 |
| content | string | 是 | 知识内容 |
| category | string | 是 | 知识分类：api_spec, best_practices, troubleshooting, faq |
| tags | array | 否 | 标签列表 |
| source | string | 否 | 知识来源 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "title": "用户登录API规范",
    "content": "POST /api/login 接口用于用户身份认证...",
    "category": "api_spec",
    "tags": ["登录", "认证", "API"],
    "source": "API文档v1.2"
  }'
```

**响应示例**:

```json
{
  "knowledge_id": "kb_20240101_001",
  "title": "用户登录API规范",
  "category": "api_spec",
  "created_at": "2024-01-01T12:00:00.000Z",
  "message": "知识条目已添加到知识库"
}
```

#### GET /api/v1/knowledge/search

搜索知识库。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| query | string | 是 | 搜索查询 |
| category | string | 否 | 限制搜索分类 |
| top_k | integer | 否 | 返回结果数量，默认10 |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/api/v1/knowledge/search?query=登录流程&category=api_spec" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "query": "登录流程",
  "results": [
    {
      "knowledge_id": "kb_20240101_001",
      "title": "用户登录API规范",
      "content_snippet": "POST /api/login 接口用于用户身份认证，需要提供用户名和密码...",
      "category": "api_spec",
      "similarity_score": 0.89,
      "tags": ["登录", "认证", "API"]
    }
  ],
  "total_results": 5
}
```

### 5. 智能体管理

#### GET /api/v1/agents

获取智能体列表和状态。

**响应示例**:

```json
{
  "agents": [
    {
      "name": "coordinator",
      "status": "active",
      "description": "任务协调和分发",
      "current_tasks": 2,
      "total_processed": 150,
      "success_rate": 0.98,
      "average_execution_time": 5.2,
      "last_activity": "2024-01-01T12:00:00.000Z"
    },
    {
      "name": "planner",
      "status": "active",
      "description": "测试计划生成",
      "current_tasks": 1,
      "total_processed": 145,
      "success_rate": 0.95,
      "average_execution_time": 45.8,
      "last_activity": "2024-01-01T11:58:00.000Z"
    }
  ]
}
```

#### GET /api/v1/agents/{agent_name}/logs

获取智能体执行日志。

**查询参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| limit | integer | 否 | 日志条数限制，默认100 |
| level | string | 否 | 日志级别过滤：DEBUG, INFO, WARNING, ERROR |
| since | string | 否 | 时间过滤（ISO8601格式） |

**请求示例**:

```bash
curl -X GET "http://localhost:8000/api/v1/agents/tester/logs?limit=50&level=ERROR" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "agent_name": "tester",
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00.000Z",
      "level": "INFO",
      "message": "开始生成测试用例",
      "task_id": "task_20240101_001",
      "context": {
        "step": 3,
        "action": "test_case_generation"
      }
    },
    {
      "timestamp": "2024-01-01T12:01:00.000Z",
      "level": "ERROR",
      "message": "LLM服务调用失败",
      "task_id": "task_20240101_001",
      "error": "Connection timeout",
      "context": {
        "retry_count": 1,
        "max_retries": 3
      }
    }
  ],
  "total_logs": 50
}
```

### 6. 配置管理

#### GET /api/v1/config/settings

获取系统配置。

**响应示例**:

```json
{
  "llm": {
    "provider": "openai",
    "default_model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "cache": {
    "enabled": true,
    "redis_url": "redis://localhost:6379/0",
    "ttl": 3600
  },
  "knowledge_base": {
    "primary_service": "ragflow",
    "fallback_services": ["chromadb", "custom"],
    "similarity_threshold": 0.7
  },
  "collaboration": {
    "auto_accept_mode": "conditional",
    "confidence_threshold": 0.8,
    "human_review_required": true
  }
}
```

#### PUT /api/v1/config/settings

更新系统配置。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| section | string | 是 | 配置节：llm, cache, knowledge_base, collaboration |
| settings | object | 是 | 配置参数 |

**请求示例**:

```bash
curl -X PUT http://localhost:8000/api/v1/config/settings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "section": "llm",
    "settings": {
      "default_model": "gpt-3.5-turbo",
      "temperature": 0.5,
      "max_tokens": 1500
    }
  }'
```

**响应示例**:

```json
{
  "message": "配置已更新",
  "section": "llm",
  "updated_settings": {
    "default_model": "gpt-3.5-turbo",
    "temperature": 0.5,
    "max_tokens": 1500
  },
  "updated_at": "2024-01-01T12:00:00.000Z"
}
```

### 7. 工具管理

#### GET /api/v1/tools

获取可用工具列表。

**响应示例**:

```json
{
  "tools": [
    {
      "name": "file_read",
      "category": "file",
      "description": "读取文件内容",
      "status": "active",
      "usage_count": 1250,
      "success_rate": 0.98
    },
    {
      "name": "sandbox_execute",
      "category": "sandbox",
      "description": "在沙箱环境中执行代码",
      "status": "active",
      "usage_count": 850,
      "success_rate": 0.92
    },
    {
      "name": "knowledge_search",
      "category": "knowledge",
      "description": "搜索知识库",
      "status": "active",
      "usage_count": 2100,
      "success_rate": 0.95
    }
  ]
}
```

#### POST /api/v1/tools/{tool_name}/test

测试工具功能。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| parameters | object | 是 | 工具测试参数 |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/tools/sandbox_execute/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "parameters": {
      "code": "print(\"Hello, World!\")",
      "language": "python"
    }
  }'
```

**响应示例**:

```json
{
  "tool_name": "sandbox_execute",
  "test_result": {
    "success": true,
    "output": "Hello, World!\n",
    "execution_time": 0.15,
    "memory_usage": "12MB"
  },
  "tested_at": "2024-01-01T12:00:00.000Z"
}
```

### 8. 错误处理和消息格式化

#### POST /api/v1/errors/format

格式化错误消息为用户友好的格式。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| error_type | string | 是 | 错误类型：network_error, api_error, generic_error |
| error_message | string | 是 | 原始错误消息 |
| context | object | 否 | 错误上下文信息 |
| style | string | 否 | 消息样式：simple, detailed, technical, friendly，默认friendly |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/errors/format \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "error_type": "network_error",
    "error_message": "Connection timeout",
    "context": {
      "service": "API服务",
      "url": "https://api.example.com",
      "retry_count": 2
    },
    "style": "friendly"
  }'
```

**响应示例**:

```json
{
  "formatted_message": {
    "title": "网络连接问题",
    "message": "无法连接到API服务，请检查网络连接。",
    "severity": "medium",
    "error_type": "network",
    "icon": "wifi-off",
    "color": "orange",
    "suggestions": [
      "检查网络连接是否正常",
      "尝试刷新页面或重新加载",
      "检查防火墙或代理设置"
    ],
    "action_buttons": [
      {"text": "重试", "action": "retry", "type": "primary"},
      {"text": "检查网络", "action": "check_network", "type": "secondary"}
    ],
    "estimated_fix_time": 180,
    "retry_available": true,
    "help_url": "/help/network-issues",
    "error_id": "NET001A2B",
    "timestamp": "2024-01-01T12:00:00.000Z"
  }
}
```

#### GET /api/v1/errors/templates

获取错误消息模板列表。

**响应示例**:

```json
{
  "templates": {
    "network_error": {
      "title": "网络连接问题",
      "icon": "wifi-off",
      "color": "orange",
      "supported_styles": ["simple", "detailed", "friendly"]
    },
    "timeout_error": {
      "title": "请求超时",
      "icon": "clock",
      "color": "yellow",
      "supported_styles": ["simple", "detailed", "friendly"]
    },
    "server_error": {
      "title": "服务器错误",
      "icon": "server",
      "color": "red",
      "supported_styles": ["simple", "detailed", "technical", "friendly"]
    }
  }
}
```

### 9. 系统管理

#### POST /api/v1/system/cleanup

清理系统资源。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| cleanup_type | string | 是 | 清理类型：tasks, cache, logs, all |
| older_than_days | integer | 否 | 清理多少天前的数据，默认30 |
| dry_run | boolean | 否 | 是否只是预览，不实际删除，默认false |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/system/cleanup \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "cleanup_type": "tasks",
    "older_than_days": 7,
    "dry_run": false
  }'
```

**响应示例**:

```json
{
  "message": "系统清理完成",
  "cleanup_type": "tasks",
  "cleaned_items": {
    "tasks_deleted": 25,
    "files_deleted": 150,
    "space_freed": "2.5GB"
  },
  "cleanup_duration": 15.2,
  "completed_at": "2024-01-01T12:00:00.000Z"
}
```

#### POST /api/v1/system/backup

创建系统备份。

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| backup_type | string | 是 | 备份类型：full, incremental, config_only |
| include_tasks | boolean | 否 | 是否包含任务数据，默认true |
| include_documents | boolean | 否 | 是否包含文档，默认true |

**请求示例**:

```bash
curl -X POST http://localhost:8000/api/v1/system/backup \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "backup_type": "full",
    "include_tasks": true,
    "include_documents": true
  }'
```

**响应示例**:

```json
{
  "backup_id": "backup_20240101_001",
  "backup_type": "full",
  "status": "in_progress",
  "estimated_completion": "2024-01-01T12:30:00.000Z",
  "backup_size_estimate": "5.2GB",
  "created_at": "2024-01-01T12:00:00.000Z"
}
```

## 错误处理

### HTTP状态码

API使用标准的HTTP状态码来表示请求的结果：

| 状态码 | 含义 | 描述 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 202 | Accepted | 请求已接受，正在处理 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未授权访问 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 请求格式正确但语义错误 |
| 429 | Too Many Requests | 请求频率超限 |
| 500 | Internal Server Error | 服务器内部错误 |
| 502 | Bad Gateway | 网关错误 |
| 503 | Service Unavailable | 服务不可用 |

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_TASK_TYPE",
    "message": "不支持的任务类型",
    "details": "支持的任务类型包括: functional_testing, performance_testing, security_testing",
    "timestamp": "2024-01-01T12:00:00.000Z",
    "request_id": "req_20240101_001",
    "documentation_url": "https://docs.testagent.com/api/errors#INVALID_TASK_TYPE"
  }
}
```

### 验证错误格式

对于422状态码的验证错误，响应格式如下：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数验证失败",
    "details": "以下字段存在错误",
    "validation_errors": [
      {
        "field": "title",
        "message": "标题不能为空",
        "code": "REQUIRED_FIELD"
      },
      {
        "field": "task_type",
        "message": "任务类型必须是以下值之一: functional_testing, performance_testing, security_testing",
        "code": "INVALID_ENUM_VALUE",
        "allowed_values": ["functional_testing", "performance_testing", "security_testing"]
      }
    ],
    "timestamp": "2024-01-01T12:00:00.000Z",
    "request_id": "req_20240101_002"
  }
}
```

### 常见错误代码

#### 认证和授权错误

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| INVALID_TOKEN | 401 | JWT令牌无效或已过期 |
| MISSING_TOKEN | 401 | 缺少认证令牌 |
| INSUFFICIENT_PERMISSIONS | 403 | 权限不足 |
| ACCOUNT_SUSPENDED | 403 | 账户已被暂停 |

#### 任务相关错误

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| TASK_NOT_FOUND | 404 | 任务不存在 |
| TASK_ALREADY_COMPLETED | 409 | 任务已完成，无法修改 |
| TASK_ALREADY_CANCELLED | 409 | 任务已取消 |
| INVALID_TASK_TYPE | 400 | 无效的任务类型 |
| TASK_EXECUTION_FAILED | 500 | 任务执行失败 |
| TASK_TIMEOUT | 408 | 任务执行超时 |

#### 文档相关错误

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| DOCUMENT_NOT_FOUND | 404 | 文档不存在 |
| DOCUMENT_TOO_LARGE | 413 | 文档文件过大 |
| UNSUPPORTED_FILE_TYPE | 415 | 不支持的文件类型 |
| DOCUMENT_PROCESSING_FAILED | 500 | 文档处理失败 |

#### 系统相关错误

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| SYSTEM_OVERLOAD | 503 | 系统负载过高 |
| LLM_SERVICE_ERROR | 502 | LLM服务错误 |
| RAG_SERVICE_ERROR | 502 | RAG服务错误 |
| CACHE_SERVICE_ERROR | 502 | 缓存服务错误 |
| DATABASE_ERROR | 500 | 数据库错误 |
| NETWORK_ERROR | 502 | 网络连接错误 |
| TIMEOUT_ERROR | 408 | 请求超时错误 |
| CONFIGURATION_ERROR | 500 | 配置错误 |
| RESOURCE_ERROR | 503 | 资源不足错误 |

#### 限制和配额错误

| 错误代码 | HTTP状态码 | 描述 |
|----------|------------|------|
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| CONCURRENT_TASK_LIMIT | 429 | 并发任务数量超限 |
| STORAGE_QUOTA_EXCEEDED | 413 | 存储配额超限 |
| API_QUOTA_EXCEEDED | 429 | API调用配额超限 |

### 用户友好错误处理

#### 1. 错误消息格式化

TestAgent提供智能错误消息格式化功能，将技术错误转换为用户友好的消息：

```javascript
// 使用错误格式化API
async function formatError(error, context = {}) {
  try {
    const response = await fetch('/api/v1/errors/format', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        error_type: determineErrorType(error),
        error_message: error.message,
        context: context,
        style: 'friendly'
      })
    });
    
    const result = await response.json();
    return result.formatted_message;
  } catch (e) {
    // 降级到原始错误消息
    return {
      title: "系统错误",
      message: error.message,
      severity: "medium"
    };
  }
}

// 在UI中显示格式化错误
function displayError(formattedError) {
  const errorElement = document.createElement('div');
  errorElement.className = `error-message ${formattedError.severity}`;
  errorElement.innerHTML = `
    <div class="error-header">
      <i class="icon ${formattedError.icon}"></i>
      <h3>${formattedError.title}</h3>
    </div>
    <div class="error-content">
      <p>${formattedError.message}</p>
      ${formattedError.suggestions.length > 0 ? `
        <div class="suggestions">
          <h4>建议解决方案：</h4>
          <ul>
            ${formattedError.suggestions.map(s => `<li>${s}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
      <div class="action-buttons">
        ${formattedError.action_buttons.map(btn => `
          <button class="btn ${btn.type}" onclick="${btn.action}">${btn.text}</button>
        `).join('')}
      </div>
    </div>
  `;
  
  document.getElementById('error-container').appendChild(errorElement);
}
```

#### 2. 错误类型识别

系统支持多种错误类型的自动识别和处理：

```javascript
function determineErrorType(error) {
  if (error.name === 'NetworkError' || error.message.includes('network')) {
    return 'network_error';
  } else if (error.status >= 400 && error.status < 500) {
    return 'api_error';
  } else if (error.name === 'TimeoutError') {
    return 'timeout_error';
  } else {
    return 'generic_error';
  }
}
```

#### 3. 消息样式选择

根据用户类型和场景选择合适的消息样式：

- **simple**: 简洁样式，适合移动端或空间有限的场景
- **detailed**: 详细样式，提供更多上下文信息
- **technical**: 技术样式，适合开发者和技术人员
- **friendly**: 友好样式，适合普通用户，默认选择

### 错误处理最佳实践

#### 1. 客户端重试策略

```javascript
class APIClient {
  async makeRequest(url, options, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(url, options);
        
        if (response.ok) {
          return await response.json();
        }
        
        // 处理不同类型的错误
        if (response.status === 429) {
          // 速率限制，使用指数退避
          const delay = Math.pow(2, attempt) * 1000;
          await this.sleep(delay);
          continue;
        }
        
        if (response.status >= 500 && response.status < 600) {
          // 服务器错误，可以重试
          if (attempt < maxRetries) {
            await this.sleep(1000 * attempt);
            continue;
          }
        }
        
        // 其他错误不重试
        const error = await response.json();
        throw new APIError(error, response.status);
        
      } catch (error) {
        if (attempt === maxRetries) {
          throw error;
        }
        await this.sleep(1000 * attempt);
      }
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

class APIError extends Error {
  constructor(errorResponse, statusCode) {
    super(errorResponse.error.message);
    this.code = errorResponse.error.code;
    this.statusCode = statusCode;
    this.details = errorResponse.error.details;
    this.requestId = errorResponse.error.request_id;
  }
}
```

#### 2. Python错误处理示例

```python
import requests
import time
from typing import Optional, Dict, Any

class TestAgentAPIError(Exception):
    def __init__(self, error_response: Dict[str, Any], status_code: int):
        self.code = error_response['error']['code']
        self.message = error_response['error']['message']
        self.details = error_response['error']['details']
        self.status_code = status_code
        self.request_id = error_response['error'].get('request_id')
        super().__init__(self.message)

class TestAgentClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.ok:
                    return response.json()
                
                # 处理错误响应
                error_data = response.json()
                
                if response.status_code == 429:
                    # 速率限制，使用指数退避
                    delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                
                if 500 <= response.status_code < 600:
                    # 服务器错误，可以重试
                    if attempt < max_retries:
                        time.sleep(attempt)
                        continue
                
                # 抛出API错误
                raise TestAgentAPIError(error_data, response.status_code)
                
            except requests.RequestException as e:
                if attempt == max_retries:
                    raise e
                time.sleep(attempt)
        
        raise Exception("Max retries exceeded")
```

### 错误监控和日志

建议客户端实现错误监控和日志记录：

```javascript
// 错误监控示例
function logAPIError(error, context) {
  const errorLog = {
    timestamp: new Date().toISOString(),
    error_code: error.code,
    error_message: error.message,
    status_code: error.statusCode,
    request_id: error.requestId,
    context: context,
    user_agent: navigator.userAgent,
    url: window.location.href
  };
  
  // 发送到监控系统
  fetch('/api/client-errors', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(errorLog)
  });
  
  // 本地日志
  console.error('API Error:', errorLog);
}
```

## 限制和配额

### 请求限制

| 限制类型 | 默认值 | 描述 |
|----------|--------|------|
| 请求频率 | 100/分钟 | 每个API密钥每分钟最大请求数 |
| 并发任务 | 10个 | 同时执行的任务数量限制 |
| 文件上传大小 | 50MB | 单个文件最大上传大小 |
| 批量操作 | 100个 | 批量操作最大项目数 |

### 任务限制

| 限制类型 | 默认值 | 最大值 | 描述 |
|----------|--------|--------|------|
| 任务超时 | 1小时 | 6小时 | 单个任务最大执行时间 |
| 任务描述长度 | 10KB | 50KB | 任务描述最大字符数 |
| 文档数量 | 50个 | 200个 | 单个任务关联文档数量 |
| 工作空间大小 | 1GB | 10GB | 任务工作空间最大大小 |

### 存储限制

| 限制类型 | 默认配额 | 描述 |
|----------|----------|------|
| 文档存储 | 10GB | 用户文档总存储空间 |
| 任务数据 | 50GB | 任务工作空间总存储空间 |
| 知识库条目 | 10,000个 | 知识库最大条目数 |
| 历史记录 | 90天 | 任务历史记录保留时间 |

### 配额监控

可以通过以下端点监控配额使用情况：

```bash
curl -X GET http://localhost:8000/api/v1/monitoring/quotas \
  -H "Authorization: Bearer <token>"
```

**响应示例**:
```json
{
  "quotas": {
    "requests": {
      "limit": 100,
      "used": 45,
      "remaining": 55,
      "reset_time": "2024-01-01T13:00:00.000Z"
    },
    "concurrent_tasks": {
      "limit": 10,
      "used": 3,
      "remaining": 7
    },
    "storage": {
      "documents": {
        "limit": "10GB",
        "used": "2.5GB",
        "remaining": "7.5GB"
      },
      "tasks": {
        "limit": "50GB",
        "used": "15.2GB",
        "remaining": "34.8GB"
      }
    }
  }
}
```

## WebSocket支持

TestAgent提供WebSocket连接以支持实时数据推送和双向通信。

### 连接端点

#### 任务状态监控
```
ws://localhost:8000/ws/tasks/{task_id}
```

#### 系统监控
```
ws://localhost:8000/ws/monitoring
```

#### 智能体日志流
```
ws://localhost:8000/ws/agents/{agent_name}/logs
```

### 认证

WebSocket连接需要在连接时提供认证信息：

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/task_20240101_001', [], {
  headers: {
    'Authorization': 'Bearer <your_jwt_token>'
  }
});
```

### 消息格式

#### 任务状态更新
```json
{
  "type": "task_status_update",
  "task_id": "task_20240101_001",
  "status": "running",
  "current_agent": "tester",
  "progress": 45.5,
  "message": "正在生成测试用例...",
  "timestamp": "2024-01-01T12:15:00.000Z"
}
```

#### 智能体行为事件
```json
{
  "type": "agent_action",
  "task_id": "task_20240101_001",
  "agent_name": "tester",
  "action": "tool_call",
  "tool_name": "knowledge_search",
  "parameters": {"query": "登录测试用例"},
  "timestamp": "2024-01-01T12:15:30.000Z"
}
```

#### 系统指标更新
```json
{
  "type": "system_metrics",
  "metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 68.5,
    "active_tasks": 5,
    "cache_hit_rate": 0.85
  },
  "timestamp": "2024-01-01T12:16:00.000Z"
}
```

#### 错误通知
```json
{
  "type": "error",
  "task_id": "task_20240101_001",
  "error_code": "LLM_SERVICE_ERROR",
  "error_message": "LLM服务暂时不可用",
  "severity": "warning",
  "timestamp": "2024-01-01T12:16:30.000Z"
}
```

### 客户端示例

#### JavaScript客户端
```javascript
class TestAgentWebSocket {
  constructor(endpoint, token) {
    this.endpoint = endpoint;
    this.token = token;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }
  
  connect() {
    this.ws = new WebSocket(this.endpoint, [], {
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });
    
    this.ws.onopen = () => {
      console.log('WebSocket连接已建立');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket连接已关闭');
      this.reconnect();
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
  }
  
  handleMessage(data) {
    switch (data.type) {
      case 'task_status_update':
        this.onTaskStatusUpdate(data);
        break;
      case 'agent_action':
        this.onAgentAction(data);
        break;
      case 'system_metrics':
        this.onSystemMetrics(data);
        break;
      case 'error':
        this.onError(data);
        break;
    }
  }
  
  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connect();
      }, 1000 * this.reconnectAttempts);
    }
  }
  
  // 事件处理器（需要实现）
  onTaskStatusUpdate(data) { /* 处理任务状态更新 */ }
  onAgentAction(data) { /* 处理智能体行为 */ }
  onSystemMetrics(data) { /* 处理系统指标 */ }
  onError(data) { /* 处理错误通知 */ }
}

// 使用示例
const taskWs = new TestAgentWebSocket(
  'ws://localhost:8000/ws/tasks/task_20240101_001',
  'your_jwt_token'
);
taskWs.connect();
```

#### Python客户端
```python
import asyncio
import websockets
import json

class TestAgentWebSocket:
    def __init__(self, endpoint, token):
        self.endpoint = endpoint
        self.token = token
        self.websocket = None
    
    async def connect(self):
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            self.websocket = await websockets.connect(
                self.endpoint,
                extra_headers=headers
            )
            
            print("WebSocket连接已建立")
            
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_message(data)
                
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket连接已关闭")
        except Exception as e:
            print(f"WebSocket错误: {e}")
    
    async def handle_message(self, data):
        message_type = data.get('type')
        
        if message_type == 'task_status_update':
            await self.on_task_status_update(data)
        elif message_type == 'agent_action':
            await self.on_agent_action(data)
        elif message_type == 'system_metrics':
            await self.on_system_metrics(data)
        elif message_type == 'error':
            await self.on_error(data)
    
    # 事件处理器
    async def on_task_status_update(self, data):
        print(f"任务状态更新: {data['status']} - {data['message']}")
    
    async def on_agent_action(self, data):
        print(f"智能体行为: {data['agent_name']} - {data['action']}")
    
    async def on_system_metrics(self, data):
        print(f"系统指标: CPU {data['metrics']['cpu_usage']}%")
    
    async def on_error(self, data):
        print(f"错误通知: {data['error_message']}")

# 使用示例
async def main():
    ws = TestAgentWebSocket(
        'ws://localhost:8000/ws/tasks/task_20240101_001',
        'your_jwt_token'
    )
    await ws.connect()

asyncio.run(main())
```

## SDK和客户端库

### Python SDK

#### 安装
```bash
pip install testagent-python-sdk
```

#### 基本使用
```python
from testagent import TestAgentClient
import asyncio

# 初始化客户端
client = TestAgentClient(
    base_url="http://localhost:8000",
    api_key="your_api_key"
)

async def main():
    # 创建任务
    task = await client.tasks.create(
        title="用户登录功能测试",
        description="测试用户登录功能的各种场景",
        task_type="functional_testing",
        documents=["doc_123"]
    )
    
    print(f"任务已创建: {task.task_id}")
    
    # 监听任务状态
    async for update in client.tasks.watch(task.task_id):
        print(f"任务状态: {update.status} - {update.message}")
        if update.status in ['completed', 'failed', 'cancelled']:
            break
    
    # 获取测试报告
    if update.status == 'completed':
        report = await client.tasks.get_report(task.task_id)
        print(f"测试完成，成功率: {report.summary.success_rate}")

# 运行示例
asyncio.run(main())
```

#### 高级功能
```python
# 文档管理
document = await client.documents.upload(
    file_path="requirements.pdf",
    category="requirements",
    title="用户需求文档"
)

# 知识库搜索
results = await client.knowledge.search(
    query="用户登录流程",
    category="api_spec",
    top_k=5
)

# 系统监控
metrics = await client.monitoring.get_metrics()
print(f"系统CPU使用率: {metrics.system.cpu_usage}%")

# 配置管理
await client.config.update_settings(
    section="llm",
    settings={
        "default_model": "gpt-4",
        "temperature": 0.7
    }
)
```

### JavaScript/TypeScript SDK

#### 安装
```bash
npm install testagent-js-sdk
```

#### 基本使用
```typescript
import { TestAgentClient, TaskType } from 'testagent-js-sdk';

// 初始化客户端
const client = new TestAgentClient({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your_api_key'
});

async function main() {
  try {
    // 创建任务
    const task = await client.tasks.create({
      title: '用户登录功能测试',
      description: '测试用户登录功能的各种场景',
      taskType: TaskType.FUNCTIONAL_TESTING,
      documents: ['doc_123']
    });
    
    console.log(`任务已创建: ${task.taskId}`);
    
    // 使用WebSocket监听任务状态
    const subscription = client.tasks.subscribe(task.taskId, (update) => {
      console.log(`任务状态: ${update.status} - ${update.message}`);
      
      if (['completed', 'failed', 'cancelled'].includes(update.status)) {
        subscription.unsubscribe();
        
        if (update.status === 'completed') {
          handleTaskCompletion(task.taskId);
        }
      }
    });
    
  } catch (error) {
    console.error('任务创建失败:', error.message);
  }
}

async function handleTaskCompletion(taskId: string) {
  const report = await client.tasks.getReport(taskId);
  console.log(`测试完成，成功率: ${report.summary.successRate}`);
}

main();
```

#### React Hook
```typescript
import { useTestAgent } from 'testagent-react-hooks';

function TaskDashboard() {
  const { tasks, createTask, isLoading } = useTestAgent();
  
  const handleCreateTask = async () => {
    const task = await createTask({
      title: '新测试任务',
      description: '测试描述',
      taskType: 'functional_testing'
    });
    
    console.log('任务已创建:', task.taskId);
  };
  
  return (
    <div>
      <button onClick={handleCreateTask} disabled={isLoading}>
        创建任务
      </button>
      
      <div>
        {tasks.map(task => (
          <TaskCard key={task.taskId} task={task} />
        ))}
      </div>
    </div>
  );
}
```

### Go SDK

#### 安装
```bash
go get github.com/testagent/go-sdk
```

#### 基本使用
```go
package main

import (
    "context"
    "fmt"
    "log"
    
    "github.com/testagent/go-sdk"
)

func main() {
    client := testagent.NewClient(&testagent.Config{
        BaseURL: "http://localhost:8000",
        APIKey:  "your_api_key",
    })
    
    ctx := context.Background()
    
    // 创建任务
    task, err := client.Tasks.Create(ctx, &testagent.CreateTaskRequest{
        Title:       "用户登录功能测试",
        Description: "测试用户登录功能的各种场景",
        TaskType:    testagent.TaskTypeFunctionalTesting,
        Documents:   []string{"doc_123"},
    })
    
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("任务已创建: %s\n", task.TaskID)
    
    // 等待任务完成
    err = client.Tasks.Wait(ctx, task.TaskID, func(update *testagent.TaskUpdate) {
        fmt.Printf("任务状态: %s - %s\n", update.Status, update.Message)
    })
    
    if err != nil {
        log.Fatal(err)
    }
    
    // 获取报告
    report, err := client.Tasks.GetReport(ctx, task.TaskID)
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("测试完成，成功率: %.2f\n", report.Summary.SuccessRate)
}
```

## 最佳实践

### 1. 任务管理最佳实践

#### 异步处理
```python
# 推荐：使用异步方式处理长时间任务
async def create_and_monitor_task():
    task = await client.tasks.create({
        "title": "复杂测试任务",
        "description": "这是一个可能需要较长时间的任务"
    })
    
    # 使用WebSocket监听状态更新
    async for update in client.tasks.watch(task.task_id):
        if update.status == 'completed':
            break
        elif update.status == 'failed':
            await handle_task_failure(task.task_id)
            break
```

#### 批量操作
```python
# 推荐：批量创建任务
tasks_data = [
    {"title": "任务1", "description": "描述1"},
    {"title": "任务2", "description": "描述2"},
    {"title": "任务3", "description": "描述3"}
]

tasks = await client.tasks.create_batch(tasks_data)
```

### 2. 错误处理最佳实践

#### 重试机制
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def robust_api_call():
    try:
        return await client.tasks.create(task_data)
    except TestAgentAPIError as e:
        if e.code in ['SYSTEM_OVERLOAD', 'LLM_SERVICE_ERROR']:
            raise  # 可重试的错误
        else:
            raise Exception("不可重试的错误") from e
```

#### 优雅降级
```python
async def create_task_with_fallback(task_data):
    try:
        # 尝试使用高级功能
        task_data['config'] = {'enable_advanced_analysis': True}
        return await client.tasks.create(task_data)
    except TestAgentAPIError as e:
        if e.code == 'FEATURE_NOT_AVAILABLE':
            # 降级到基础功能
            task_data['config'] = {'enable_advanced_analysis': False}
            return await client.tasks.create(task_data)
        raise
```

### 3. 性能优化最佳实践

#### 连接池管理
```python
import aiohttp

# 使用连接池
connector = aiohttp.TCPConnector(
    limit=100,  # 总连接数限制
    limit_per_host=20,  # 每个主机连接数限制
    keepalive_timeout=30
)

client = TestAgentClient(
    base_url="http://localhost:8000",
    connector=connector
)
```

#### 缓存策略
```python
from functools import lru_cache
import asyncio

class CachedTestAgentClient:
    def __init__(self, client):
        self.client = client
        self._config_cache = {}
        self._cache_ttl = 300  # 5分钟
    
    @lru_cache(maxsize=128)
    async def get_cached_document(self, doc_id):
        return await self.client.documents.get(doc_id)
    
    async def get_system_config(self):
        now = asyncio.get_event_loop().time()
        
        if ('config' not in self._config_cache or 
            now - self._config_cache['timestamp'] > self._cache_ttl):
            
            config = await self.client.config.get_settings()
            self._config_cache = {
                'config': config,
                'timestamp': now
            }
        
        return self._config_cache['config']
```

### 4. 安全最佳实践

#### 令牌管理
```python
import jwt
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires_at = None
    
    async def get_valid_token(self):
        if (self.token is None or 
            datetime.now() >= self.token_expires_at - timedelta(minutes=5)):
            await self.refresh_token()
        
        return self.token
    
    async def refresh_token(self):
        response = await self.client.auth.get_token(
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        self.token = response['access_token']
        self.token_expires_at = datetime.now() + timedelta(
            seconds=response['expires_in']
        )
```

#### 敏感数据处理
```python
import re

def sanitize_task_description(description):
    """清理任务描述中的敏感信息"""
    
    # 移除邮箱地址
    description = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                        '[EMAIL]', description)
    
    # 移除电话号码
    description = re.sub(r'\b\d{3}-\d{3}-\d{4}\b|\b\d{11}\b', 
                        '[PHONE]', description)
    
    # 移除身份证号
    description = re.sub(r'\b\d{15}|\d{18}\b', 
                        '[ID_CARD]', description)
    
    return description
```

### 5. 监控和日志最佳实践

#### 结构化日志
```python
import structlog
import uuid

logger = structlog.get_logger()

class LoggingTestAgentClient:
    def __init__(self, client):
        self.client = client
    
    async def create_task(self, task_data):
        request_id = str(uuid.uuid4())
        
        logger.info(
            "task_creation_started",
            request_id=request_id,
            task_title=task_data.get('title'),
            task_type=task_data.get('task_type')
        )
        
        try:
            task = await self.client.tasks.create(task_data)
            
            logger.info(
                "task_creation_completed",
                request_id=request_id,
                task_id=task.task_id,
                duration=task.estimated_duration
            )
            
            return task
            
        except Exception as e:
            logger.error(
                "task_creation_failed",
                request_id=request_id,
                error_code=getattr(e, 'code', 'UNKNOWN'),
                error_message=str(e)
            )
            raise
```

#### 指标收集
```python
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
api_requests_total = Counter('testagent_api_requests_total', 
                           'Total API requests', ['method', 'endpoint', 'status'])
api_request_duration = Histogram('testagent_api_request_duration_seconds',
                                'API request duration')
active_tasks = Gauge('testagent_active_tasks', 'Number of active tasks')

class MetricsTestAgentClient:
    def __init__(self, client):
        self.client = client
    
    async def create_task(self, task_data):
        with api_request_duration.time():
            try:
                task = await self.client.tasks.create(task_data)
                api_requests_total.labels('POST', '/tasks', 'success').inc()
                active_tasks.inc()
                return task
            except Exception as e:
                api_requests_total.labels('POST', '/tasks', 'error').inc()
                raise
```

## API版本控制

### 版本策略

TestAgent API采用语义化版本控制（SemVer）：

- **主版本号 (Major)**: 不兼容的API更改
- **次版本号 (Minor)**: 向后兼容的功能添加
- **修订版本号 (Patch)**: 向后兼容的问题修复

### 版本指定

#### URL路径版本控制
```
http://localhost:8000/api/v1/tasks
http://localhost:8000/api/v2/tasks  # 未来版本
```

#### 请求头版本控制
```bash
curl -X GET http://localhost:8000/api/tasks \
  -H "API-Version: v1" \
  -H "Authorization: Bearer <token>"
```

### 版本兼容性

| 版本 | 状态 | 支持截止日期 | 主要变更 |
|------|------|-------------|----------|
| v1.0 | 当前版本 | - | 初始版本 |
| v0.9 | 已弃用 | 2024-06-01 | 测试版本 |

### 迁移指南

当发布新的主版本时，我们会提供详细的迁移指南和工具来帮助用户升级。

## 支持和反馈

### 技术支持

- **文档**: [https://docs.testagent.com](https://docs.testagent.com)
- **API参考**: [https://api.testagent.com/docs](https://api.testagent.com/docs)
- **状态页面**: [https://status.testagent.com](https://status.testagent.com)

### 社区支持

- **GitHub Issues**: [https://github.com/testagent/testagent/issues](https://github.com/testagent/testagent/issues)
- **讨论论坛**: [https://community.testagent.com](https://community.testagent.com)
- **Stack Overflow**: 使用标签 `testagent`

### 商业支持

- **邮箱**: support@testagent.com
- **企业支持**: enterprise@testagent.com
- **紧急支持**: 24/7 电话支持（企业客户）

### 反馈渠道

我们欢迎您的反馈和建议：

- **功能请求**: [https://github.com/testagent/testagent/discussions](https://github.com/testagent/testagent/discussions)
- **Bug报告**: [https://github.com/testagent/testagent/issues](https://github.com/testagent/testagent/issues)
- **API改进建议**: api-feedback@testagent.com

---

**TestAgent API v1.0** - 让AI为您的测试工作赋能 🚀

最后更新: 2024-01-01  
文档版本: 1.0.0