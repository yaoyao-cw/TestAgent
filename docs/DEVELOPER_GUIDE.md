# TestAgent 开发者文档和扩展指南

## 概述

本文档面向希望扩展TestAgent功能、集成第三方服务或贡献代码的开发者。涵盖系统架构、开发环境搭建、扩展开发、API集成等内容。

## 开发环境搭建

### 1. 环境要求

#### 基础环境
- **Python**: 3.11+
- **Node.js**: 18+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Git**: 2.30+

#### 推荐配置
- **内存**: 8GB+
- **存储**: 50GB+
- **CPU**: 4核+

### 2. 项目结构

```
TestAgent/
├── src/                    # 后端源代码
│   ├── agents/            # 智能体实现
│   ├── server/            # FastAPI服务器
│   ├── services/          # 核心服务
│   │   ├── task_creation_monitor.py    # 任务创建监控
│   │   ├── progress_tracker.py         # 进度跟踪
│   │   ├── task_status_notifier.py     # 状态通知
│   │   └── task_monitoring_integration.py  # 监控集成
│   ├── tools/             # 工具集成
│   ├── models/            # 数据模型
│   │   ├── task_monitoring.py          # 任务监控模型
│   │   └── ...
│   └── utils/             # 工具函数
├── frontend/              # 前端应用
│   ├── src/
│   │   ├── components/    # React组件
│   │   ├── pages/         # 页面组件
│   │   ├── hooks/         # 自定义hooks
│   │   ├── services/      # API服务
│   │   └── types/         # TypeScript类型
├── tests/                 # 测试文件
├── config/                # 配置文件
├── docs/                  # 项目文档
├── scripts/               # 部署脚本
└── data/                  # 数据存储
```

### 3. 开发环境启动

#### 3.1 克隆项目
```bash
git clone <repository-url>
cd TestAgent
```

#### 3.2 后端环境
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，添加必要的API密钥

# 启动开发服务器
python -m uvicorn src.server.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3.3 前端环境
```bash
cd frontend
npm install
npm run dev
```

#### 3.4 Docker开发环境
```bash
# 启动完整开发环境
./scripts/dev-deploy.sh

# 或使用Docker Compose
docker-compose -f docker-compose.dev.yml up -d
```

## 核心架构详解

### 1. 智能体架构

#### 1.1 基础智能体类
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class BaseAgent(ABC):
    """智能体基类，定义统一的load->llm->router模式"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.llm_service = self._init_llm_service()
        self.tools = self._init_tools()
    
    @abstractmethod
    def load(self, input_data: Any) -> BaseModel:
        """加载阶段：处理输入数据，准备上下文"""
        pass
    
    @abstractmethod
    def llm(self, state: BaseModel) -> BaseModel:
        """LLM阶段：调用大语言模型进行推理"""
        pass
    
    @abstractmethod
    def router(self, output: BaseModel) -> str:
        """路由阶段：决定下一步执行流程"""
        pass
    
    def execute(self, input_data: Any) -> tuple[BaseModel, str]:
        """执行完整的智能体流程"""
        state = self.load(input_data)
        output = self.llm(state)
        next_agent = self.router(output)
        return output, next_agent
```

#### 1.2 ReAct智能体实现
```python
class ReActAgent(BaseAgent):
    """支持ReAct循环的复杂智能体"""
    
    def llm(self, state: BaseModel) -> BaseModel:
        """实现ReAct循环：Reason-Act-Observe"""
        max_iterations = self.config.get('react_max_iterations', 10)
        
        for iteration in range(max_iterations):
            # Reason: 分析当前状态，制定行动计划
            reasoning = self._reason(state)
            
            # Act: 执行具体行动（工具调用）
            action_result = self._act(reasoning, state)
            
            # Observe: 观察行动结果，更新状态
            state = self._observe(action_result, state)
            
            # 检查是否达到终止条件
            if self._should_terminate(state):
                break
        
        return state
    
    def _reason(self, state: BaseModel) -> str:
        """推理阶段：分析当前状态，制定计划"""
        prompt = self._build_reasoning_prompt(state)
        response = self.llm_service.generate(prompt)
        return response
    
    def _act(self, reasoning: str, state: BaseModel) -> Any:
        """行动阶段：执行工具调用"""
        tool_calls = self._extract_tool_calls(reasoning)
        results = []
        
        for tool_call in tool_calls:
            tool = self.tools[tool_call.name]
            result = tool.execute(tool_call.parameters)
            results.append(result)
        
        return results
    
    def _observe(self, action_result: Any, state: BaseModel) -> BaseModel:
        """观察阶段：处理行动结果，更新状态"""
        # 更新状态，记录观察结果
        state.observations.append(action_result)
        state.iteration += 1
        return state
```

### 2. 工具系统架构

#### 2.1 工具基类
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel

class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """执行工具功能"""
        pass
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """验证参数有效性"""
        # 实现参数验证逻辑
        return True

class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """按类别获取工具"""
        return [tool for name, tool in self.tools.items() 
                if name.startswith(f"{category}_")]
```

#### 2.2 工具状态机
```python
class ToolStateMachine:
    """工具状态机，管理工具可用性"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tool_registry = ToolRegistry()
        self.constraints = config.get('constraints', {})
    
    def get_available_tools(self, agent_name: str, mode: str = "auto") -> List[str]:
        """获取可用工具列表"""
        if mode == "auto":
            return list(self.tool_registry.tools.keys())
        
        elif mode == "required":
            agent_config = self.constraints.get(agent_name, {})
            required_categories = agent_config.get('required', [])
            return self._get_tools_by_categories(required_categories)
        
        elif mode == "specified":
            agent_config = self.constraints.get(agent_name, {})
            allowed_categories = agent_config.get('allowed', [])
            return self._get_tools_by_categories(allowed_categories)
        
        return []
    
    def _get_tools_by_categories(self, categories: List[str]) -> List[str]:
        """按类别获取工具"""
        tools = []
        for category in categories:
            tools.extend([name for name in self.tool_registry.tools.keys() 
                         if name.startswith(f"{category}_")])
        return tools
```

### 3. 文件系统工作空间

#### 3.1 工作空间管理器
```python
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

class WorkspaceManager:
    """工作空间管理器"""
    
    def __init__(self, base_path: str = "data/tasks"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_task_workspace(self, task_id: str) -> Path:
        """创建任务工作空间"""
        workspace_path = self.base_path / task_id
        workspace_path.mkdir(exist_ok=True)
        
        # 创建初始文件
        self._create_todo_file(workspace_path)
        self._create_metadata_file(workspace_path, task_id)
        
        return workspace_path
    
    def get_task_workspace(self, task_id: str) -> Path:
        """获取任务工作空间路径"""
        return self.base_path / task_id
    
    def save_agent_output(self, task_id: str, agent_name: str, 
                         output_type: str, content: Any, version: int = 1) -> str:
        """保存智能体输出"""
        workspace = self.get_task_workspace(task_id)
        
        # 生成文件名：[步骤]_[Agent]_[类型]_[版本].扩展名
        step = self._get_next_step(workspace)
        filename = f"{step:02d}_{agent_name}_{output_type}_v{version}"
        
        # 根据内容类型确定扩展名
        if isinstance(content, dict) or isinstance(content, list):
            filename += ".json"
            file_path = workspace / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            filename += ".md"
            file_path = workspace / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(content))
        
        return str(file_path)
    
    def load_agent_input(self, task_id: str, file_pattern: str) -> Optional[Any]:
        """加载智能体输入"""
        workspace = self.get_task_workspace(task_id)
        
        # 查找匹配的文件
        files = list(workspace.glob(file_pattern))
        if not files:
            return None
        
        # 选择最新版本的文件
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        
        if latest_file.suffix == '.json':
            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(latest_file, 'r', encoding='utf-8') as f:
                return f.read()
    
    def update_todo_file(self, task_id: str, todo_items: List[str]):
        """更新todo.md文件"""
        workspace = self.get_task_workspace(task_id)
        todo_file = workspace / "todo.md"
        
        content = "# 任务待办事项\n\n"
        for i, item in enumerate(todo_items, 1):
            content += f"{i}. {item}\n"
        
        with open(todo_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def log_error(self, task_id: str, error: Exception, context: Dict[str, Any]):
        """记录错误信息"""
        workspace = self.get_task_workspace(task_id)
        error_file = workspace / "_error.log"
        
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context
        }
        
        # 追加到错误日志
        with open(error_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_entry, ensure_ascii=False) + "\n")
```

## 扩展开发指南

### 1. 开发新智能体

#### 1.1 智能体开发模板
```python
from src.agents.base import BaseAgent
from src.models.agent_models import YourAgentState, YourAgentOutput
from typing import Any

class YourCustomAgent(BaseAgent):
    """自定义智能体示例"""
    
    def load(self, input_data: Any) -> YourAgentState:
        """加载阶段实现"""
        # 1. 解析输入数据
        # 2. 加载相关文档和上下文
        # 3. 初始化状态对象
        
        state = YourAgentState(
            input_data=input_data,
            context=self._load_context(input_data),
            tools=self._get_available_tools()
        )
        return state
    
    def llm(self, state: YourAgentState) -> YourAgentOutput:
        """LLM阶段实现"""
        # 1. 构建提示词
        prompt = self._build_prompt(state)
        
        # 2. 调用LLM
        response = self.llm_service.generate(
            prompt=prompt,
            temperature=self.config.get('temperature', 0.7),
            max_tokens=self.config.get('max_tokens', 2000)
        )
        
        # 3. 解析响应
        output = self._parse_response(response, state)
        
        return output
    
    def router(self, output: YourAgentOutput) -> str:
        """路由阶段实现"""
        # 根据输出决定下一个智能体
        if output.needs_review:
            return "reviewer"
        elif output.is_complete:
            return "reporter"
        else:
            return "continue"
    
    def _build_prompt(self, state: YourAgentState) -> str:
        """构建提示词"""
        template = """
        你是一个专业的{agent_type}智能体。
        
        任务描述：{task_description}
        
        当前状态：{current_state}
        
        可用工具：{available_tools}
        
        请根据以上信息完成你的任务。
        """
        
        return template.format(
            agent_type=self.name,
            task_description=state.task_description,
            current_state=state.current_state,
            available_tools=state.tools
        )
```

#### 1.2 注册新智能体
```python
# src/agents/__init__.py
from .your_custom_agent import YourCustomAgent

AGENT_REGISTRY = {
    "coordinator": CoordinatorAgent,
    "planner": PlannerAgent,
    "tester": TesterAgent,
    "coder": CoderAgent,
    "reviewer": ReviewerAgent,
    "your_custom": YourCustomAgent,  # 添加新智能体
}

def create_agent(agent_type: str, config: dict) -> BaseAgent:
    """创建智能体实例"""
    agent_class = AGENT_REGISTRY.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    return agent_class(agent_type, config)
```

### 2. 开发新工具

#### 2.1 工具开发模板
```python
from src.tools.base import BaseTool
from typing import Any, Dict
import requests

class YourCustomTool(BaseTool):
    """自定义工具示例"""
    
    def __init__(self):
        super().__init__(
            name="your_custom_tool",
            description="这是一个自定义工具的示例",
            parameters={
                "param1": {"type": "string", "description": "参数1描述"},
                "param2": {"type": "integer", "description": "参数2描述", "default": 10}
            }
        )
    
    def execute(self, params: Dict[str, Any]) -> Any:
        """执行工具功能"""
        # 1. 验证参数
        if not self.validate_parameters(params):
            raise ValueError("Invalid parameters")
        
        # 2. 执行具体逻辑
        param1 = params.get("param1")
        param2 = params.get("param2", 10)
        
        try:
            # 实现你的工具逻辑
            result = self._do_something(param1, param2)
            
            return {
                "success": True,
                "result": result,
                "message": "Tool executed successfully"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Tool execution failed"
            }
    
    def _do_something(self, param1: str, param2: int) -> Any:
        """实现具体功能"""
        # 这里实现你的工具逻辑
        pass
```

#### 2.2 注册新工具
```python
# src/tools/__init__.py
from .your_custom_tool import YourCustomTool

def register_tools(tool_registry):
    """注册所有工具"""
    # 注册现有工具
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(KnowledgeSearchTool())
    
    # 注册新工具
    tool_registry.register(YourCustomTool())
```

### 3. 扩展RAG服务

#### 3.1 RAG适配器开发
```python
from src.services.rag.base import RAGServiceInterface
from src.models.document import Document
from typing import List
import requests

class YourCustomRAGAdapter(RAGServiceInterface):
    """自定义RAG服务适配器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.api_url = config.get('api_url')
        self.api_key = config.get('api_key')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        """检索文档"""
        try:
            response = requests.post(
                f"{self.api_url}/search",
                headers=self.headers,
                json={
                    "query": query,
                    "top_k": top_k
                }
            )
            response.raise_for_status()
            
            results = response.json()
            documents = []
            
            for result in results.get('documents', []):
                doc = Document(
                    id=result.get('id'),
                    title=result.get('title'),
                    content=result.get('content'),
                    metadata=result.get('metadata', {}),
                    score=result.get('score', 0.0)
                )
                documents.append(doc)
            
            return documents
        
        except Exception as e:
            raise Exception(f"RAG service error: {e}")
    
    def add_document(self, document: Document) -> str:
        """添加文档"""
        try:
            response = requests.post(
                f"{self.api_url}/documents",
                headers=self.headers,
                json={
                    "title": document.title,
                    "content": document.content,
                    "metadata": document.metadata
                }
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('document_id')
        
        except Exception as e:
            raise Exception(f"Failed to add document: {e}")
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        
        except:
            return False
```

#### 3.2 注册RAG服务
```python
# src/services/rag/__init__.py
from .your_custom_adapter import YourCustomRAGAdapter

RAG_ADAPTERS = {
    'chromadb': ChromaDBAdapter,
    'ragflow': RAGFlowAdapter,
    'qanything': QAnythingAdapter,
    'your_custom': YourCustomRAGAdapter,  # 添加新适配器
}
```

### 4. 错误处理系统扩展

#### 4.1 错误消息格式化器开发

**自定义错误格式化器**:
```python
from src.core.error_message_formatter import ErrorMessageFormatter, FormattedMessage, MessageStyle
from src.core.exceptions import TestAgentException

class CustomErrorFormatter(ErrorMessageFormatter):
    """自定义错误格式化器"""
    
    def __init__(self):
        super().__init__()
        # 添加自定义错误模板
        self.templates.update({
            "custom_error": {
                "title": "自定义错误",
                "message": "发生了自定义错误：{error_details}",
                "simple_message": "自定义错误",
                "detailed_message": "详细的自定义错误信息：{error_details}",
                "icon": "alert-circle",
                "color": "red"
            }
        })
    
    def format_custom_error(self, error: Exception, context: dict = None, 
                           style: MessageStyle = MessageStyle.FRIENDLY) -> FormattedMessage:
        """格式化自定义错误"""
        context = context or {}
        template = self.templates["custom_error"]
        style_config = self.style_configs[style]
        
        # 生成消息内容
        if style_config["message_length"] == "detailed":
            message = template["detailed_message"].format(
                error_details=str(error)
            )
        else:
            message = template["message"].format(
                error_details=str(error)
            )
        
        # 生成解决方案建议
        suggestions = self._generate_custom_suggestions(error, context)
        
        return FormattedMessage(
            title=template["title"],
            message=message,
            severity="medium",
            error_type="custom",
            icon=template["icon"],
            color=template["color"],
            suggestions=suggestions,
            action_buttons=self._generate_custom_action_buttons(error, context),
            retry_available=True,
            help_url="/help/custom-errors"
        )
    
    def _generate_custom_suggestions(self, error: Exception, context: dict) -> list:
        """生成自定义错误建议"""
        suggestions = [
            "检查自定义配置是否正确",
            "查看详细错误日志",
            "联系技术支持获取帮助"
        ]
        
        # 根据错误类型添加特定建议
        if "config" in str(error).lower():
            suggestions.insert(0, "验证配置文件格式和内容")
        
        return suggestions
    
    def _generate_custom_action_buttons(self, error: Exception, context: dict) -> list:
        """生成自定义操作按钮"""
        return [
            {"text": "重试", "action": "retry", "type": "primary"},
            {"text": "查看配置", "action": "view_config", "type": "secondary"},
            {"text": "获取帮助", "action": "get_help", "type": "link"}
        ]
```

**注册自定义格式化器**:
```python
# src/core/__init__.py
from .error_message_formatter import ErrorMessageFormatter
from .custom_error_formatter import CustomErrorFormatter

def get_error_formatter(formatter_type: str = "default") -> ErrorMessageFormatter:
    """获取错误格式化器实例"""
    if formatter_type == "custom":
        return CustomErrorFormatter()
    else:
        return ErrorMessageFormatter()
```

#### 4.2 解决方案建议引擎开发

**自定义建议引擎**:
```python
from src.core.solution_suggestion_engine import SolutionSuggestionEngine
from typing import List, Dict, Any

class CustomSuggestionEngine(SolutionSuggestionEngine):
    """自定义解决方案建议引擎"""
    
    def __init__(self):
        super().__init__()
        # 添加自定义建议规则
        self.suggestion_rules.update({
            "database_connection": {
                "keywords": ["database", "connection", "db"],
                "suggestions": [
                    "检查数据库服务是否运行",
                    "验证数据库连接字符串",
                    "检查网络连接和防火墙设置"
                ]
            },
            "api_rate_limit": {
                "keywords": ["rate limit", "429", "too many requests"],
                "suggestions": [
                    "等待一段时间后重试",
                    "检查API调用频率",
                    "考虑实现请求队列"
                ]
            }
        })
    
    def generate_contextual_suggestions(self, error: Exception, 
                                      context: Dict[str, Any]) -> List[str]:
        """生成上下文相关的建议"""
        suggestions = super().generate_contextual_suggestions(error, context)
        
        # 添加基于上下文的自定义建议
        if context.get("component") == "llm_service":
            suggestions.extend([
                "检查LLM服务API密钥是否有效",
                "验证模型名称是否正确",
                "检查API配额是否充足"
            ])
        
        elif context.get("component") == "rag_service":
            suggestions.extend([
                "检查向量数据库连接",
                "验证文档索引是否完整",
                "检查检索参数配置"
            ])
        
        return suggestions
    
    def get_recovery_steps(self, error_type: str, severity: str) -> List[Dict[str, Any]]:
        """获取恢复步骤"""
        recovery_steps = []
        
        if error_type == "network_error":
            recovery_steps = [
                {
                    "step": 1,
                    "action": "check_network",
                    "description": "检查网络连接状态",
                    "command": "ping google.com",
                    "expected_result": "网络连接正常"
                },
                {
                    "step": 2,
                    "action": "restart_service",
                    "description": "重启相关服务",
                    "command": "docker-compose restart",
                    "expected_result": "服务重启成功"
                }
            ]
        
        elif error_type == "api_error":
            recovery_steps = [
                {
                    "step": 1,
                    "action": "check_credentials",
                    "description": "验证API凭据",
                    "command": "curl -H 'Authorization: Bearer $TOKEN' $API_URL/health",
                    "expected_result": "认证成功"
                }
            ]
        
        return recovery_steps
```

#### 4.3 错误恢复指南开发

**自定义恢复指南**:
```python
from src.core.error_recovery_guide import ErrorRecoveryGuide
from typing import Dict, List, Any

class CustomRecoveryGuide(ErrorRecoveryGuide):
    """自定义错误恢复指南"""
    
    def __init__(self):
        super().__init__()
        # 添加自定义恢复策略
        self.recovery_strategies.update({
            "service_unavailable": {
                "immediate_actions": [
                    "检查服务状态",
                    "查看服务日志",
                    "尝试重启服务"
                ],
                "diagnostic_steps": [
                    "检查系统资源使用情况",
                    "验证配置文件",
                    "检查依赖服务状态"
                ],
                "recovery_procedures": [
                    "清理临时文件",
                    "重置服务配置",
                    "执行健康检查"
                ]
            }
        })
    
    def generate_recovery_plan(self, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """生成恢复计划"""
        base_plan = super().generate_recovery_plan(error_context)
        
        # 添加自定义恢复步骤
        if error_context.get("error_type") == "custom_error":
            base_plan["custom_steps"] = [
                {
                    "phase": "preparation",
                    "steps": [
                        "备份当前配置",
                        "记录错误详情",
                        "准备回滚方案"
                    ]
                },
                {
                    "phase": "execution",
                    "steps": [
                        "执行修复操作",
                        "验证修复结果",
                        "更新监控状态"
                    ]
                },
                {
                    "phase": "verification",
                    "steps": [
                        "运行系统测试",
                        "检查功能完整性",
                        "确认问题解决"
                    ]
                }
            ]
        
        return base_plan
    
    def get_preventive_measures(self, error_pattern: str) -> List[str]:
        """获取预防措施"""
        measures = super().get_preventive_measures(error_pattern)
        
        # 添加自定义预防措施
        custom_measures = {
            "network_instability": [
                "实现连接池管理",
                "添加断路器模式",
                "配置重试策略"
            ],
            "resource_exhaustion": [
                "实施资源监控",
                "设置使用限制",
                "优化资源分配"
            ]
        }
        
        if error_pattern in custom_measures:
            measures.extend(custom_measures[error_pattern])
        
        return measures
```

### 5. 任务监控系统扩展

#### 5.1 任务监控组件开发

**TaskCreationMonitor扩展**:
```python
from src.services.task_creation_monitor import TaskCreationMonitor
from src.models.task_monitoring import TaskCreationContext, TaskCreationResult

class CustomTaskCreationMonitor(TaskCreationMonitor):
    """自定义任务创建监控器"""
    
    async def custom_validation_step(self, context: TaskCreationContext) -> bool:
        """自定义验证步骤"""
        # 实现自定义验证逻辑
        pass
    
    async def _validate_services(self, context: TaskCreationContext) -> List[ServiceValidationResult]:
        """扩展服务验证"""
        results = await super()._validate_services(context)
        
        # 添加自定义服务验证
        custom_result = await self._validate_custom_service()
        results.append(custom_result)
        
        return results
```

**ProgressTracker扩展**:
```python
from src.services.progress_tracker import ProgressTracker

class CustomProgressTracker(ProgressTracker):
    """自定义进度跟踪器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 自定义步骤权重
        self.step_weights.update({
            TaskCreationStep.CUSTOM_STEP: 15.0
        })
    
    async def track_custom_milestone(self, task_id: str, milestone_data: Dict):
        """跟踪自定义里程碑"""
        # 实现自定义里程碑跟踪
        pass
```

**TaskStatusNotifier扩展**:
```python
from src.services.task_status_notifier import TaskStatusNotifier

class CustomTaskStatusNotifier(TaskStatusNotifier):
    """自定义状态通知器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 注册自定义通知渠道
        self.register_notification_handler(
            "custom_channel",
            self._handle_custom_notification
        )
    
    async def _handle_custom_notification(self, notification_data: Dict):
        """处理自定义通知"""
        # 实现自定义通知逻辑
        pass
```

### 6. API扩展

#### 5.1 新API端点开发
```python
from fastapi import APIRouter, HTTPException, Depends
from src.models.api_models import YourRequest, YourResponse
from src.services.your_service import YourService

router = APIRouter(prefix="/api/v1/your-feature", tags=["your-feature"])

@router.post("/action", response_model=YourResponse)
async def your_action(
    request: YourRequest,
    service: YourService = Depends(get_your_service)
):
    """自定义API端点"""
    try:
        result = await service.process_request(request)
        return YourResponse(
            success=True,
            data=result,
            message="Action completed successfully"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Action failed: {str(e)}"
        )

@router.get("/status/{item_id}")
async def get_status(item_id: str):
    """获取状态API"""
    # 实现状态查询逻辑
    pass
```

#### 5.2 注册API路由
```python
# src/server/main.py
from src.api.your_feature import router as your_feature_router

app = FastAPI(title="TestAgent API")

# 注册现有路由
app.include_router(tasks_router)
app.include_router(documents_router)
app.include_router(monitoring_router)

# 注册新路由
app.include_router(your_feature_router)
```

## 测试开发

### 1. 单元测试

#### 1.1 智能体测试
```python
import pytest
from src.agents.your_custom_agent import YourCustomAgent
from src.models.agent_models import YourAgentState

class TestYourCustomAgent:
    
    @pytest.fixture
    def agent(self):
        config = {
            "temperature": 0.7,
            "max_tokens": 1000
        }
        return YourCustomAgent("your_custom", config)
    
    def test_load_phase(self, agent):
        """测试load阶段"""
        input_data = {"task": "test task"}
        state = agent.load(input_data)
        
        assert isinstance(state, YourAgentState)
        assert state.input_data == input_data
    
    def test_llm_phase(self, agent, mocker):
        """测试llm阶段"""
        # Mock LLM服务
        mock_llm = mocker.patch.object(agent, 'llm_service')
        mock_llm.generate.return_value = "test response"
        
        state = YourAgentState(input_data={"task": "test"})
        output = agent.llm(state)
        
        assert output is not None
        mock_llm.generate.assert_called_once()
    
    def test_router_phase(self, agent):
        """测试router阶段"""
        output = YourAgentOutput(is_complete=True)
        next_agent = agent.router(output)
        
        assert next_agent == "reporter"
```

#### 1.2 工具测试
```python
import pytest
from src.tools.your_custom_tool import YourCustomTool

class TestYourCustomTool:
    
    @pytest.fixture
    def tool(self):
        return YourCustomTool()
    
    def test_execute_success(self, tool):
        """测试工具执行成功"""
        params = {
            "param1": "test_value",
            "param2": 20
        }
        
        result = tool.execute(params)
        
        assert result["success"] is True
        assert "result" in result
    
    def test_execute_invalid_params(self, tool):
        """测试无效参数"""
        params = {}  # 缺少必需参数
        
        result = tool.execute(params)
        
        assert result["success"] is False
        assert "error" in result
```

### 2. 集成测试

#### 2.1 端到端测试
```python
import pytest
from fastapi.testclient import TestClient
from src.server.main import app

class TestE2EWorkflow:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_complete_workflow(self, client):
        """测试完整工作流程"""
        # 1. 提交任务
        task_data = {
            "title": "测试任务",
            "description": "端到端测试",
            "task_type": "functional_testing"
        }
        
        response = client.post("/api/v1/tasks/submit", json=task_data)
        assert response.status_code == 200
        
        task_id = response.json()["task_id"]
        
        # 2. 检查任务状态
        response = client.get(f"/api/v1/tasks/{task_id}/status")
        assert response.status_code == 200
        
        # 3. 等待任务完成（在实际测试中可能需要轮询）
        # ...
        
        # 4. 获取任务结果
        response = client.get(f"/api/v1/tasks/{task_id}/report")
        assert response.status_code == 200
```

### 3. 性能测试

#### 3.1 负载测试
```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test():
    """负载测试示例"""
    
    async def make_request(session, url, data):
        async with session.post(url, json=data) as response:
            return await response.json()
    
    # 准备测试数据
    test_data = {
        "title": "负载测试任务",
        "description": "性能测试",
        "task_type": "functional_testing"
    }
    
    # 并发请求
    concurrent_requests = 50
    url = "http://localhost:8000/api/v1/tasks/submit"
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            make_request(session, url, test_data)
            for _ in range(concurrent_requests)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    
    # 分析结果
    successful_requests = sum(1 for r in results if not isinstance(r, Exception))
    total_time = end_time - start_time
    
    print(f"成功请求: {successful_requests}/{concurrent_requests}")
    print(f"总耗时: {total_time:.2f}秒")
    print(f"平均响应时间: {total_time/concurrent_requests:.2f}秒")
```

## 部署和运维

### 1. 容器化部署

#### 1.1 Dockerfile优化
```dockerfile
# 多阶段构建
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 生产阶段
FROM python:3.11-slim

WORKDIR /app

# 创建非root用户
RUN useradd --create-home --shell /bin/bash testagent

# 复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ ./src/
COPY config/ ./config/

# 设置权限
RUN chown -R testagent:testagent /app
USER testagent

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/monitoring/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 1.2 Docker Compose配置
```yaml
version: '3.8'

services:
  testagent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - CHROMA_URL=http://chromadb:8000
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - redis
      - chromadb
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - testagent
    restart: unless-stopped

volumes:
  redis_data:
  chroma_data:
```

### 2. 监控和日志

#### 2.1 Prometheus指标
```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response

# 定义指标
REQUEST_COUNT = Counter('testagent_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('testagent_request_duration_seconds', 'Request duration')
ACTIVE_TASKS = Gauge('testagent_active_tasks', 'Number of active tasks')
AGENT_EXECUTION_TIME = Histogram('testagent_agent_execution_seconds', 'Agent execution time', ['agent_name'])

@app.middleware("http")
async def metrics_middleware(request, call_next):
    """请求指标中间件"""
    start_time = time.time()
    
    response = await call_next(request)
    
    # 记录指标
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response

@app.get("/metrics")
async def metrics():
    """Prometheus指标端点"""
    return Response(generate_latest(), media_type="text/plain")
```

#### 2.2 结构化日志
```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 配置处理器
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_agent_action(self, agent_name: str, action: str, context: dict):
        """记录智能体行为"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "agent_action",
            "agent_name": agent_name,
            "action": action,
            "context": context
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_performance(self, metric_name: str, value: float, labels: dict = None):
        """记录性能指标"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "performance",
            "metric_name": metric_name,
            "value": value,
            "labels": labels or {}
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
```

## 贡献指南

### 1. 代码规范

#### 1.1 Python代码规范
- 遵循PEP 8规范
- 使用Black进行代码格式化
- 使用isort进行导入排序
- 使用flake8进行代码检查

```bash
# 代码格式化
python -m black src/ tests/
python -m isort src/ tests/

# 代码检查
python -m flake8 src/ tests/
```

#### 1.2 TypeScript代码规范
- 使用ESLint和Prettier
- 严格的类型检查
- 组件和函数命名规范

```bash
# 前端代码检查和格式化
cd frontend
npm run lint
npm run format
```

### 2. 提交规范

#### 2.1 Git提交信息
使用约定式提交格式：
```
<类型>(<范围>): <描述>

[可选的正文]

[可选的脚注]
```

类型：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 添加测试
- `chore`: 构建过程或工具变动

#### 2.2 Pull Request流程
1. Fork项目到个人仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建Pull Request

### 3. 文档贡献

#### 3.1 文档结构
- API文档：使用OpenAPI规范
- 代码文档：使用docstring
- 用户文档：使用Markdown

#### 3.2 文档更新
- 新功能必须包含相应文档
- API变更需要更新API文档
- 重要变更需要更新用户指南

## 常见问题

### 1. 开发环境问题

**Q: 依赖安装失败？**
A: 
1. 检查Python版本是否为3.11+
2. 升级pip：`pip install --upgrade pip`
3. 使用虚拟环境避免冲突
4. 检查网络连接和镜像源

**Q: Docker构建失败？**
A:
1. 检查Docker版本和权限
2. 清理Docker缓存：`docker system prune`
3. 检查Dockerfile语法
4. 查看构建日志定位问题

### 2. 扩展开发问题

**Q: 新智能体不工作？**
A:
1. 检查智能体注册是否正确
2. 验证配置文件格式
3. 查看日志文件排查错误
4. 确认依赖服务状态

**Q: 工具调用失败？**
A:
1. 检查工具参数验证
2. 确认工具权限和网络访问
3. 查看工具状态机配置
4. 检查错误处理逻辑

### 3. 性能优化问题

**Q: 响应速度慢？**
A:
1. 检查LLM服务状态和配置
2. 优化提示词长度和复杂度
3. 启用缓存机制
4. 监控系统资源使用

**Q: 内存占用高？**
A:
1. 检查缓存配置和清理策略
2. 优化数据结构和算法
3. 调整并发任务数量
4. 考虑分布式部署

---

通过本开发者指南，您应该能够理解TestAgent的架构设计，并能够进行功能扩展和定制开发。如有任何问题，请参考项目文档或联系开发团队。