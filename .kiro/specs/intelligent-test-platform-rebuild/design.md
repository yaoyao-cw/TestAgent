# 设计文档

## 概述

本设计文档基于智能测试平台全栈重构设计方案v8，构建一个以大型语言模型（LLM）为核心、多智能体协同驱动的下一代智能测试中枢。系统采用文件系统作为终极上下文，通过ReAct框架和思维链技术实现高度智能化、模块化、可扩展的测试平台。

## 架构

### 整体架构

系统采用分层架构设计，包含以下核心层次：

1. **前端展示层 (Frontend Layer)**
   - React 18 + TypeScript + Vite + Tailwind CSS
   - 实时WebSocket连接显示任务进度和日志
   - 响应式UI支持任务管理、文档上传、结果查看

2. **API网关层 (API Gateway Layer)**
   - FastAPI框架提供REST API和WebSocket支持
   - 统一的请求路由和响应处理
   - 身份认证和权限控制

3. **智能体编排层 (Agent Orchestration Layer)**
   - LangGraph驱动的多智能体工作流编排
   - 统一的load -> llm -> router节点模式
   - 全局状态管理和任务调度

4. **核心服务层 (Core Services Layer)**
   - LLM服务（LiteLLM统一接口）
   - 知识库中间层（支持RAGFlow、QAnything、ChromaDB、自研RAG等多种服务）
   - 缓存服务（Redis）
   - 文件系统服务（统一工作空间）

5. **工具执行层 (Tool Execution Layer)**
   - E2B Sandbox沙箱执行环境
   - MCP协议工具集成
   - Python REPL和文档解析器

6. **数据存储层 (Data Storage Layer)**
   - 向量数据库（ChromaDB）
   - 缓存存储（Redis）
   - 文件存储（任务工作空间）

### 核心架构原则

1. **文件系统作为终极上下文**
   - 每个任务创建独立的工作目录
   - 智能体间通过文件引用进行解耦交互
   - 支持任务恢复和完整的执行轨迹追踪

2. **上下文感知的工具管理**
   - 工具状态机动态管理工具可用性
   - 约束解码技术实现三种调用模式
   - 一致性前缀命名规范

3. **KV缓存优先设计**
   - 保持提示词前缀稳定性
   - 仅追加模式更新上下文
   - 确定性序列化过程

## 组件和接口

### 多智能体系统设计

#### 1. Coordinator（协调器）
```python
class Coordinator(BaseAgent):
    def load(self, user_request: str) -> CoordinatorState:
        # 加载用户请求和系统配置
        pass
    
    def llm(self, state: CoordinatorState) -> CoordinatorOutput:
        # 分析请求，创建任务目录
        pass
    
    def router(self, output: CoordinatorOutput) -> str:
        # 路由到Planner或BackgroundInvestigator
        pass
```

#### 2. Planner（规划器）
```python
class Planner(BaseAgent):
    def load(self, task_info: TaskInfo) -> PlannerState:
        # 加载任务信息和背景调查结果
        pass
    
    def llm(self, state: PlannerState) -> PlannerOutput:
        # 使用CoT和ToT技术进行任务分解
        # 生成包含推理过程的plan.md
        pass
    
    def router(self, output: PlannerOutput) -> str:
        # 路由到TestTeam
        pass
```

#### 3. TestTeam（测试团队路由器）
```python
class TestTeam(BaseAgent):
    def load(self, plan: Plan) -> TestTeamState:
        # 加载计划和todo.md状态
        pass
    
    def llm(self, state: TestTeamState) -> TestTeamOutput:
        # 分析当前任务状态
        pass
    
    def router(self, output: TestTeamOutput) -> str:
        # 根据todo.md状态路由到Tester或Coder
        pass
```

#### 4. Tester（测试工程师）
```python
class Tester(BaseAgent):
    def load(self, task: Task) -> TesterState:
        # 加载测试任务和相关文档
        pass
    
    def llm(self, state: TesterState) -> TesterOutput:
        # 内部ReAct循环：推理-行动-观察
        # 生成测试用例和思维导图
        pass
    
    def router(self, output: TesterOutput) -> str:
        # 路由到Reviewer或Coder
        pass
```

#### 5. Coder（编码工程师）
```python
class Coder(BaseAgent):
    def load(self, test_cases: TestCases) -> CoderState:
        # 加载测试用例和编码要求
        pass
    
    def llm(self, state: CoderState) -> CoderOutput:
        # 内部ReAct循环生成测试脚本
        pass
    
    def router(self, output: CoderOutput) -> str:
        # 路由到Executor或Reviewer
        pass
```

### 统一工作空间设计

#### 文件命名规范
```
tasks/{task_id}/
├── 00_Coordinator_Init_v1.md
├── 01_Planner_Plan_v1.md
├── 02_Tester_Mindmap_v1.json
├── 03_Tester_TestCases_v2.md
├── 04_Coder_Scripts_v1.py
├── 05_Executor_Results_v1.json
├── 06_Reviewer_Report_v1.md
├── todo.md (动态更新)
└── _error.log (错误记录)
```

#### 状态管理
```python
class GlobalState:
    current_task_id: str
    current_step: int
    last_file_output_path: str
    active_agent: str
    error_count: int
    cache_keys: List[str]
```

### 工具状态机设计

#### 工具分类和命名
```python
TOOL_CATEGORIES = {
    "file_": ["file_read", "file_write", "file_list"],
    "knowledge_": ["knowledge_search", "knowledge_retrieve"],
    "sandbox_": ["sandbox_execute", "sandbox_upload"],
    "browser_": ["browser_search", "browser_navigate"],
    "shell_": ["shell_execute", "shell_upload"]
}
```

#### 约束解码模式
```python
class ToolStateMachine:
    def get_available_tools(self, agent_state: str, mode: str) -> List[str]:
        if mode == "auto":
            return self.all_tools
        elif mode == "required":
            return self.get_required_tools(agent_state)
        elif mode == "specified":
            return self.get_specified_tools(agent_state)
```

## 数据模型

### 核心数据结构

#### 任务模型
```python
@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus
    workspace_path: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
```

#### 智能体状态模型
```python
@dataclass
class AgentState:
    agent_name: str
    current_step: int
    input_files: List[str]
    output_files: List[str]
    tool_calls: List[ToolCall]
    errors: List[Error]
    context_tokens: int
```

#### 文件引用模型
```python
@dataclass
class FileReference:
    path: str
    type: FileType
    size: int
    checksum: str
    created_by: str
    metadata: Dict[str, Any]
```

### 知识库数据模型

#### 文档向量化
```python
class DocumentEmbedding:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    
    def embed_document(self, document: Document) -> List[float]:
        return self.model.encode(document.content)
```

#### 知识库接入中间层设计

#### 统一RAG服务接口
```python
from abc import ABC, abstractmethod

class RAGServiceInterface(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        """统一的文档检索接口"""
        pass
    
    @abstractmethod
    def add_document(self, document: Document) -> str:
        """统一的文档添加接口"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """服务健康检查"""
        pass
```

#### 多RAG服务适配器
```python
class ChromaDBAdapter(RAGServiceInterface):
    def __init__(self, chroma_client: ChromaDB):
        self.client = chroma_client
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        # ChromaDB检索实现
        pass

class RAGFlowAdapter(RAGServiceInterface):
    def __init__(self, ragflow_config: dict):
        self.config = ragflow_config
        self.client = RAGFlowClient(ragflow_config)
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        # RAGFlow检索实现
        pass

class QAnythingAdapter(RAGServiceInterface):
    def __init__(self, qanything_config: dict):
        self.config = qanything_config
        self.client = QAnythingClient(qanything_config)
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        # QAnything检索实现
        pass

class CustomRAGAdapter(RAGServiceInterface):
    def __init__(self, custom_config: dict):
        self.config = custom_config
        self.client = CustomRAGClient(custom_config)
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        # 自研RAG服务检索实现
        pass
```

#### RAG服务管理器
```python
class RAGServiceManager:
    def __init__(self, config: dict):
        self.services = {}
        self.primary_service = None
        self.fallback_services = []
        self._initialize_services(config)
    
    def _initialize_services(self, config: dict):
        """根据配置初始化多个RAG服务"""
        for service_name, service_config in config.items():
            if service_config.get('enabled', False):
                adapter = self._create_adapter(service_name, service_config)
                self.services[service_name] = adapter
                
                if service_config.get('primary', False):
                    self.primary_service = adapter
                elif service_config.get('fallback', False):
                    self.fallback_services.append(adapter)
    
    def _create_adapter(self, service_name: str, config: dict) -> RAGServiceInterface:
        """工厂方法创建对应的适配器"""
        adapters = {
            'chromadb': ChromaDBAdapter,
            'ragflow': RAGFlowAdapter,
            'qanything': QAnythingAdapter,
            'custom': CustomRAGAdapter
        }
        adapter_class = adapters.get(service_name)
        if not adapter_class:
            raise ValueError(f"Unsupported RAG service: {service_name}")
        return adapter_class(config)
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        """智能检索，支持主服务和降级策略"""
        try:
            if self.primary_service and self.primary_service.health_check():
                return self.primary_service.retrieve(query, top_k)
        except Exception as e:
            logger.warning(f"Primary RAG service failed: {e}")
        
        # 降级到备用服务
        for fallback_service in self.fallback_services:
            try:
                if fallback_service.health_check():
                    return fallback_service.retrieve(query, top_k)
            except Exception as e:
                logger.warning(f"Fallback RAG service failed: {e}")
        
        raise Exception("All RAG services are unavailable")
```

#### 知识库配置管理
```python
# config/knowledge_base.yaml
knowledge_base:
  services:
    chromadb:
      enabled: true
      primary: false
      fallback: true
      config:
        host: "localhost"
        port: 8001
        collection_name: "test_documents"
    
    ragflow:
      enabled: true
      primary: true
      fallback: false
      config:
        api_url: "http://ragflow-server:9380"
        api_key: "${RAGFLOW_API_KEY}"
        dataset_id: "test_dataset"
    
    qanything:
      enabled: false
      primary: false
      fallback: true
      config:
        api_url: "http://qanything-server:8777"
        api_key: "${QANYTHING_API_KEY}"
    
    custom:
      enabled: true
      primary: false
      fallback: true
      config:
        api_url: "http://custom-rag:8080"
        api_key: "${CUSTOM_RAG_API_KEY}"
        model_name: "custom-embedding-model"
```

## 错误处理

### 错误分类和处理策略

#### 1. 系统级错误
- LLM API调用失败
- 沙箱环境异常
- 网络连接问题

处理策略：
- 自动重试机制（指数退避）
- 降级处理（切换备用模型）
- 错误日志记录和告警

#### 2. 智能体执行错误
- 工具调用失败
- 输出格式错误
- 逻辑推理错误

处理策略：
- 保留错误上下文供学习
- ReAct循环自我修正
- 人工干预节点

#### 3. 业务逻辑错误
- 测试用例生成不完整
- 代码语法错误
- 文档解析失败

处理策略：
- Reviewer智能体质量检查
- 多轮迭代优化
- 错误模式学习

### 错误恢复机制

```python
class ErrorRecoveryManager:
    def handle_error(self, error: Exception, context: AgentContext) -> RecoveryAction:
        # 分析错误类型和上下文
        # 决定恢复策略：重试、降级、人工干预
        pass
    
    def preserve_error_context(self, error: Exception, context: AgentContext):
        # 将错误信息写入_error.log
        # 保留在上下文中供后续学习
        pass
```

## 测试策略

### 单元测试

#### 智能体节点测试
```python
class TestTesterAgent:
    def test_load_phase(self):
        # 测试load阶段数据加载
        pass
    
    def test_llm_phase(self):
        # 测试llm阶段推理输出
        pass
    
    def test_router_phase(self):
        # 测试router阶段路由决策
        pass
```

#### 工具状态机测试
```python
class TestToolStateMachine:
    def test_tool_availability(self):
        # 测试不同状态下工具可用性
        pass
    
    def test_constraint_decoding(self):
        # 测试约束解码三种模式
        pass
```

### 集成测试

#### 端到端工作流测试
```python
class TestWorkflow:
    def test_complete_testing_pipeline(self):
        # 测试从需求到报告的完整流程
        pass
    
    def test_error_recovery(self):
        # 测试错误恢复和任务恢复
        pass
```

#### 性能测试
```python
class TestPerformance:
    def test_kv_cache_hit_rate(self):
        # 测试KV缓存命中率
        pass
    
    def test_concurrent_tasks(self):
        # 测试并发任务处理能力
        pass
```

### 智能体行为测试

#### ReAct循环测试
```python
class TestReActLoop:
    def test_reasoning_quality(self):
        # 测试推理质量和逻辑性
        pass
    
    def test_action_selection(self):
        # 测试动作选择的准确性
        pass
    
    def test_observation_processing(self):
        # 测试观察结果处理能力
        pass
```

## 部署架构

### 容器化部署

#### Docker Compose配置
```yaml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://backend:8000
  
  backend:
    build: ./src
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - CHROMA_URL=http://chromadb:8000
    volumes:
      - ./data/tasks:/app/data/tasks
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  # 多RAG服务支持
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - ./data/vectordb:/chroma/chroma
  
  ragflow:
    image: infiniflow/ragflow:latest
    ports:
      - "9380:9380"
    environment:
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
    volumes:
      - ./data/ragflow:/ragflow/data
    profiles:
      - ragflow
  
  qanything:
    image: freeren/qanything:latest
    ports:
      - "8777:8777"
    environment:
      - QANYTHING_API_KEY=${QANYTHING_API_KEY}
    volumes:
      - ./data/qanything:/qanything/data
    profiles:
      - qanything
  
  custom-rag:
    build: ./custom-rag-service
    ports:
      - "8080:8080"
    environment:
      - CUSTOM_RAG_API_KEY=${CUSTOM_RAG_API_KEY}
    volumes:
      - ./data/custom-rag:/app/data
    profiles:
      - custom-rag
  
  e2b-sandbox:
    image: e2b/sandbox:latest
    privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

### 监控和可观测性

#### Prometheus + Grafana
```python
# 关键指标监控
METRICS = {
    "kv_cache_hit_rate": "KV缓存命中率",
    "agent_execution_time": "智能体执行时间",
    "task_completion_rate": "任务完成率",
    "error_rate": "错误率",
    "concurrent_tasks": "并发任务数"
}
```

#### 日志聚合
```python
class StructuredLogger:
    def log_agent_action(self, agent: str, action: str, context: dict):
        # 结构化记录智能体行为
        pass
    
    def log_performance_metrics(self, metrics: dict):
        # 记录性能指标
        pass
```

### 扩展性设计

#### 水平扩展
- 无状态智能体节点设计
- Redis集群支持会话共享
- 负载均衡器分发请求

#### 垂直扩展
- GPU资源池支持大模型推理
- 内存缓存优化
- 存储性能优化

## 安全考虑

### 代码执行安全
- E2B Sandbox强隔离环境
- 资源限制和超时控制
- 恶意代码检测和过滤

### 数据安全
- 敏感信息脱敏处理
- 访问权限控制
- 数据加密存储和传输

### API安全
- JWT身份认证
- 请求频率限制
- 输入验证和过滤