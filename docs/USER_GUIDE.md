# TestAgent 用户操作指南

## 概述

TestAgent是一个基于AI的智能测试代理系统，能够自动化执行从需求分析到测试报告生成的完整测试生命周期。本指南将帮助您快速上手并充分利用系统的各项功能。

## 快速开始

### 1. 系统访问

#### 访问地址
- **主应用**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **监控面板**: http://localhost:8000/static/monitoring.html

#### 首次登录
1. 打开浏览器访问主应用地址
2. 使用管理员账号登录（默认：admin/admin123）
3. 完成初始配置向导

### 2. 基本配置

#### 2.1 LLM配置
```bash
# 编辑环境变量文件
vim .env

# 添加API密钥
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-3.5-turbo
```

#### 2.2 知识库配置
```yaml
# config/knowledge_base.yaml
knowledge_base:
  services:
    chromadb:
      enabled: true
      primary: true
      config:
        host: "localhost"
        port: 8001
```

## 核心功能使用

### 1. 任务管理

#### 1.1 创建测试任务

**通过Web界面**:
1. 点击"新建任务"按钮
2. 填写任务基本信息：
   - 任务名称：简洁描述测试目标
   - 任务描述：详细说明测试需求
   - 任务类型：功能测试/性能测试/安全测试
3. 上传相关文档（需求文档、API文档等）
4. 点击"提交任务"

**通过API调用**:
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/submit" \
     -H "Content-Type: application/json" \
     -d '{
       "task_type": "functional_testing",
       "title": "用户登录功能测试",
       "description": "测试用户登录功能的各种场景",
       "documents": ["requirements.pdf", "api_spec.json"]
     }'
```

**任务创建监控**:
```bash
# 监控任务创建进度
curl "http://localhost:8000/api/v1/tasks/{task_id}/creation-status"

# 暂停任务创建
curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/pause"

# 恢复任务创建
curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/resume"
```

#### 1.2 任务状态监控

**实时监控**:
- 任务列表页面显示所有任务状态
- 点击任务可查看详细执行进度
- WebSocket实时更新任务状态和日志
- 任务创建过程的详细进度跟踪

**任务创建状态**:
- `pending`: 等待开始创建
- `validating`: 正在验证服务和输入
- `creating`: 正在创建任务
- `completed`: 创建完成
- `failed`: 创建失败
- `cancelled`: 已取消
- `paused`: 已暂停

**任务执行状态**:
- `pending`: 任务等待执行
- `running`: 任务正在执行
- `completed`: 任务执行完成
- `failed`: 任务执行失败
- `paused`: 任务暂停（等待人工干预）

**创建步骤监控**:
```bash
# 查看任务创建详细状态
curl "http://localhost:8000/api/v1/tasks/{task_id}/creation-status"
```

创建步骤包括：
1. **初始化** (10%): 创建工作空间和基础配置
2. **服务验证** (20%): 检查LLM、缓存、数据库等服务状态
3. **输入验证** (10%): 验证用户输入数据的完整性
4. **资源分配** (20%): 分配计算和存储资源
5. **任务生成** (30%): 生成任务数据和配置
6. **持久化** (8%): 保存任务数据到存储系统
7. **通知** (2%): 发送创建完成通知

#### 1.3 任务结果查看

**测试报告**:
```bash
# 获取任务报告
curl "http://localhost:8000/api/v1/tasks/{task_id}/report"

# 下载报告文件
curl "http://localhost:8000/api/v1/tasks/{task_id}/report/download" \
     -o test_report.pdf
```

**执行轨迹**:
- 查看任务工作目录：`data/tasks/{task_id}/`
- 文件命名规范：`[步骤]_[智能体]_[类型]_[版本].扩展名`
- 错误日志：`_error.log`

### 2. 文档管理

#### 2.1 文档上传

**支持格式**:
- PDF文档
- Word文档（.doc, .docx）
- Excel文档（.xls, .xlsx）
- 纯文本文件（.txt, .md）
- JSON/YAML配置文件

**上传方式**:
```bash
# 单文件上传
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@requirements.pdf" \
     -F "category=requirements"

# 批量上传
curl -X POST "http://localhost:8000/api/v1/documents/batch-upload" \
     -H "Content-Type: multipart/form-data" \
     -F "files=@doc1.pdf" \
     -F "files=@doc2.docx"
```

#### 2.2 文档管理

**查看文档列表**:
```bash
curl "http://localhost:8000/api/v1/documents/"
```

**删除文档**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/{doc_id}"
```

**文档搜索**:
```bash
curl "http://localhost:8000/api/v1/documents/search?query=登录功能"
```

### 3. 智能体协作

#### 3.1 智能体工作流

**标准流程**:
1. **协调器**: 分析用户需求，创建任务工作空间
2. **规划器**: 制定详细测试计划，分解任务
3. **测试员**: 设计测试用例，生成思维导图
4. **编码员**: 编写测试脚本，实现自动化
5. **评审员**: 质量评估，提供改进建议
6. **报告员**: 生成综合测试报告

#### 3.2 人工干预节点

**干预时机**:
- 计划确认：规划器生成计划后
- 质量评审：测试用例和脚本完成后
- 异常处理：执行出现错误时

**干预操作**:
1. 系统暂停并发送通知
2. 用户查看当前状态和建议
3. 提供反馈或修改指令
4. 系统继续执行或重新规划

#### 3.3 反馈机制

**提供反馈**:
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/feedback" \
     -H "Content-Type: application/json" \
     -d '{
       "feedback_type": "plan_review",
       "content": "请增加边界条件测试用例",
       "action": "modify"
     }'
```

**反馈类型**:
- `plan_review`: 计划评审反馈
- `quality_review`: 质量评审反馈
- `error_handling`: 错误处理反馈
- `general`: 一般性反馈

## 高级功能

### 1. 自定义配置

#### 1.1 智能体配置

**配置文件**: `config/agents.yaml`
```yaml
agents:
  coordinator:
    model: "gpt-4"
    temperature: 0.3
    max_tokens: 2000
  
  planner:
    model: "gpt-4"
    temperature: 0.5
    enable_cot: true
    enable_tot: true
  
  tester:
    model: "gpt-3.5-turbo"
    react_max_iterations: 10
    tools: ["knowledge_search", "file_read", "browser_search"]
```

#### 1.2 工具配置

**工具状态机配置**:
```yaml
tools:
  categories:
    file_: ["file_read", "file_write", "file_list"]
    knowledge_: ["knowledge_search", "knowledge_retrieve"]
    sandbox_: ["sandbox_execute", "sandbox_upload"]
  
  constraints:
    tester:
      mode: "specified"
      allowed: ["knowledge_", "file_", "browser_"]
    
    coder:
      mode: "required"
      required: ["sandbox_", "file_"]
```

### 2. 知识库管理

#### 2.1 知识库构建

**自动学习**:
- 系统自动从上传文档中提取知识
- 历史测试用例和缺陷信息自动入库
- API规范和技术文档自动解析

**手动管理**:
```bash
# 添加知识条目
curl -X POST "http://localhost:8000/api/v1/knowledge/add" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "登录API规范",
       "content": "POST /api/login 接口说明...",
       "category": "api_spec",
       "tags": ["登录", "认证", "API"]
     }'

# 搜索知识
curl "http://localhost:8000/api/v1/knowledge/search?query=登录流程"
```

#### 2.2 RAG服务配置

**多服务支持**:
```yaml
knowledge_base:
  services:
    chromadb:
      enabled: true
      primary: false
      fallback: true
    
    ragflow:
      enabled: true
      primary: true
      api_url: "http://ragflow-server:9380"
    
    custom:
      enabled: true
      fallback: true
      api_url: "http://custom-rag:8080"
```

### 3. 错误处理和故障排除

#### 3.1 智能错误提示

TestAgent提供智能错误处理系统，将技术错误转换为用户友好的提示信息：

**错误消息格式**:
- **标题**: 简洁的错误描述
- **消息**: 用户友好的错误说明
- **建议**: 具体的解决方案建议
- **操作按钮**: 可执行的操作选项
- **帮助链接**: 相关文档和支持信息

**错误严重程度**:
- `low`: 轻微问题，不影响核心功能
- `medium`: 中等问题，可能影响部分功能
- `high`: 严重问题，影响系统正常运行

**常见错误类型和处理**:

**网络连接错误**:
```
错误提示: "网络连接问题"
可能原因: 网络不稳定、服务器维护、防火墙设置
建议操作:
1. 检查网络连接是否正常
2. 尝试刷新页面或重新加载
3. 检查防火墙或代理设置
4. 稍后重试
```

**API服务错误**:
```
错误提示: "服务暂时不可用"
可能原因: 服务器负载过高、维护中、配置问题
建议操作:
1. 等待几分钟后重试
2. 检查服务状态页面
3. 联系技术支持
```

**认证错误**:
```
错误提示: "登录信息已过期"
可能原因: 会话超时、密码更改、权限变更
建议操作:
1. 重新登录系统
2. 检查用户名和密码
3. 联系管理员确认权限
```

#### 3.2 错误恢复指南

**自动恢复机制**:
- **智能重试**: 系统自动重试失败的操作
- **降级服务**: 在主服务不可用时提供基础功能
- **状态恢复**: 自动恢复中断的任务执行

**手动恢复步骤**:

**任务执行失败**:
1. 查看任务详情页面的错误信息
2. 根据错误提示执行建议操作
3. 使用"重试"按钮重新执行任务
4. 如问题持续，联系技术支持

**系统响应慢**:
1. 检查网络连接状态
2. 清理浏览器缓存
3. 尝试使用不同浏览器
4. 检查系统资源使用情况

**数据同步问题**:
1. 刷新页面获取最新数据
2. 检查网络连接稳定性
3. 等待系统自动同步完成
4. 手动触发数据同步

#### 3.3 错误报告和反馈

**错误报告功能**:
- 每个错误都有唯一的错误ID
- 自动收集错误上下文信息
- 支持一键发送错误报告

**反馈渠道**:
```bash
# 通过API提交错误反馈
curl -X POST "http://localhost:8000/api/v1/feedback/error" \
     -H "Content-Type: application/json" \
     -d '{
       "error_id": "NET001A2B",
       "user_description": "网络连接经常中断",
       "steps_to_reproduce": "1. 提交任务 2. 等待5分钟 3. 连接中断",
       "expected_behavior": "任务应该正常执行完成",
       "actual_behavior": "任务执行中途失败"
     }'
```

### 4. 监控和运维

#### 4.1 系统监控

**健康检查**:
```bash
# 基本健康检查
curl "http://localhost:8000/api/v1/monitoring/health"

# 详细系统状态
curl "http://localhost:8000/api/v1/monitoring/status"
```

**性能指标**:
- 任务完成率
- 平均执行时间
- 智能体响应时间
- 缓存命中率
- 错误率统计

#### 4.2 日志管理

**日志查看**:
```bash
# 应用日志
docker-compose logs -f testagent

# 特定任务日志
curl "http://localhost:8000/api/v1/tasks/{task_id}/logs"

# 智能体执行日志
curl "http://localhost:8000/api/v1/agents/{agent_name}/logs"
```

**日志级别**:
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息记录
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

## 最佳实践

### 1. 任务设计

#### 1.1 需求描述
- **明确具体**: 避免模糊的描述，提供具体的测试目标
- **结构化**: 使用标准格式描述功能需求和非功能需求
- **完整性**: 包含输入、输出、边界条件等完整信息

**示例**:
```
任务：用户登录功能测试

功能需求：
1. 用户可以使用用户名/密码登录
2. 支持记住登录状态
3. 登录失败3次后锁定账户

非功能需求：
1. 响应时间 < 2秒
2. 支持并发1000用户
3. 密码加密存储

测试范围：
- 正常登录流程
- 异常情况处理
- 安全性验证
- 性能测试
```

#### 1.2 文档准备
- **需求文档**: 详细的功能规格说明
- **API文档**: 接口规范和示例
- **设计文档**: 系统架构和设计说明
- **历史数据**: 相关的测试用例和缺陷记录

### 2. 执行优化

#### 2.1 任务分解
- **模块化**: 将大任务分解为独立的小任务
- **优先级**: 按重要性和依赖关系排序
- **并行性**: 识别可并行执行的任务

#### 2.2 质量控制
- **及时反馈**: 在关键节点提供人工反馈
- **迭代优化**: 基于执行结果持续改进
- **知识积累**: 将经验和最佳实践沉淀到知识库

### 3. 系统维护

#### 3.1 定期维护
- **缓存清理**: 定期清理过期缓存数据
- **日志轮转**: 配置日志文件自动轮转
- **数据备份**: 定期备份重要数据和配置
- **性能优化**: 监控系统性能并及时优化

#### 3.2 故障处理
- **错误分析**: 分析错误日志，识别问题根因
- **任务恢复**: 利用文件系统状态恢复中断任务
- **降级策略**: 在服务异常时启用降级模式
- **告警响应**: 建立完善的告警和响应机制

## 常见问题

### 1. 任务执行问题

**Q: 任务执行失败怎么办？**
A: 
1. 查看任务工作目录中的`_error.log`文件
2. 分析错误类型：系统错误、智能体错误、业务逻辑错误
3. 根据错误信息调整配置或提供反馈
4. 使用任务恢复功能重新执行

**Q: 智能体响应慢怎么优化？**
A:
1. 检查LLM服务状态和配置
2. 优化提示词，减少不必要的上下文
3. 启用缓存机制，提高响应速度
4. 考虑使用更快的模型或增加资源

### 2. 配置问题

**Q: 如何切换LLM提供商？**
A:
1. 修改`.env`文件中的`LLM_PROVIDER`配置
2. 添加对应的API密钥
3. 重启服务使配置生效
4. 测试新配置是否正常工作

**Q: 知识库检索效果不好怎么办？**
A:
1. 检查文档质量和格式
2. 优化文档分块和向量化参数
3. 调整检索算法和相似度阈值
4. 考虑使用多个RAG服务进行对比

### 3. 性能问题

**Q: 系统资源占用过高？**
A:
1. 监控各组件资源使用情况
2. 调整并发任务数量限制
3. 优化缓存策略和数据存储
4. 考虑水平扩展或资源升级

**Q: 如何提高任务执行效率？**
A:
1. 优化任务分解和并行度
2. 使用更高效的模型和工具
3. 建立完善的知识库减少重复工作
4. 持续优化智能体提示词和逻辑

## 技术支持

### 联系方式
- **文档**: 查看完整技术文档
- **社区**: 参与开源社区讨论
- **Issues**: 在GitHub提交问题和建议
- **邮件**: 联系技术支持团队

### 更新和升级
- **版本检查**: 定期检查系统版本更新
- **功能更新**: 关注新功能和改进
- **安全更新**: 及时应用安全补丁
- **配置迁移**: 升级时注意配置文件迁移

---

通过本指南，您应该能够熟练使用TestAgent系统进行智能化测试工作。如有任何问题，请参考技术文档或联系支持团队。