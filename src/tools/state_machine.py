#!/usr/bin/env python3
"""
工具状态机模块
实现上下文感知的工具管理，支持约束解码和三种调用模式
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ToolCallMode(Enum):
    """工具调用模式"""

    AUTO = "auto"  # 自动模式：所有工具可用
    REQUIRED = "required"  # 必需模式：必须调用工具
    SPECIFIED = "specified"  # 指定模式：只能使用指定工具子集


class AgentState(Enum):
    """智能体状态枚举"""

    INITIALIZING = "initializing"
    PLANNING = "planning"
    RESEARCHING = "researching"
    GENERATING_MINDMAP = "generating_mindmap"
    GENERATING_TESTCASES = "generating_testcases"
    CODING = "coding"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    REPORTING = "reporting"
    ERROR_HANDLING = "error_handling"
    COMPLETED = "completed"


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    category: str
    description: str
    parameters: Dict[str, Any]
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    """状态转换定义"""

    from_state: AgentState
    to_state: AgentState
    condition: Optional[Callable] = None
    allowed_tools: Set[str] = field(default_factory=set)
    call_mode: ToolCallMode = ToolCallMode.AUTO


class ToolStateMachine:
    """工具状态机

    实现上下文感知的工具管理，支持：
    1. 静态工具定义加载，避免动态增删破坏KV缓存
    2. 状态机驱动的工具可用性控制
    3. 约束解码机制，支持三种调用模式
    4. 响应预填充机制
    """

    # 工具分类和一致性前缀命名规范
    TOOL_CATEGORIES = {
        "file_": [
            "file_read",
            "file_write",
            "file_list",
            "file_delete",
            "file_copy",
            "file_move",
            "file_search",
        ],
        "knowledge_": [
            "knowledge_search",
            "knowledge_retrieve",
            "knowledge_add",
            "knowledge_update",
            "knowledge_query",
        ],
        "sandbox_": [
            "sandbox_execute",
            "sandbox_upload",
            "sandbox_download",
            "sandbox_list",
            "sandbox_clean",
        ],
        "browser_": [
            "browser_search",
            "browser_navigate",
            "browser_extract",
            "browser_screenshot",
            "browser_click",
        ],
        "shell_": [
            "shell_execute",
            "shell_upload",
            "shell_download",
            "shell_list",
            "shell_env",
        ],
        "mcp_": ["mcp_call", "mcp_list", "mcp_info", "mcp_health"],
        "workflow_": [
            "workflow_create",
            "workflow_update",
            "workflow_execute",
            "workflow_status",
            "workflow_cancel",
        ],
    }

    def __init__(self):
        """初始化工具状态机"""
        self.current_state: AgentState = AgentState.INITIALIZING
        self.current_agent: str = ""
        self.call_mode: ToolCallMode = ToolCallMode.AUTO

        # 静态工具定义 - 避免动态增删破坏KV缓存
        self.tool_definitions: Dict[str, ToolDefinition] = {}
        self.all_tools: Set[str] = set()

        # 状态转换规则
        self.state_transitions: Dict[AgentState, List[StateTransition]] = {}

        # 工具可用性缓存
        self._availability_cache: Dict[str, Set[str]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self.cache_ttl: int = 300  # 缓存5分钟

        # 约束解码配置
        self.constraint_config: Dict[str, Any] = {}

        # 初始化工具定义和状态转换
        self._initialize_tool_definitions()
        self._initialize_state_transitions()

        logger.info("工具状态机初始化完成")

    def _initialize_tool_definitions(self):
        """初始化工具定义 - 静态加载避免破坏KV缓存"""
        for category, tools in self.TOOL_CATEGORIES.items():
            for tool_name in tools:
                tool_def = ToolDefinition(
                    name=tool_name,
                    category=category.rstrip("_"),
                    description=f"{category.rstrip('_')}类工具: {tool_name}",
                    parameters=self._get_default_parameters(tool_name),
                    enabled=True,
                )
                self.tool_definitions[tool_name] = tool_def
                self.all_tools.add(tool_name)

        logger.info(f"加载了 {len(self.tool_definitions)} 个工具定义")

    def _get_default_parameters(self, tool_name: str) -> Dict[str, Any]:
        """获取工具的默认参数定义"""
        # 这里可以根据工具名称返回具体的参数定义
        # 为了保持简单，返回通用参数结构
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": f"{tool_name}的输入参数"}
            },
            "required": ["input"],
        }

    def _initialize_state_transitions(self):
        """初始化状态转换规则"""
        # 协调器状态转换
        self.state_transitions[AgentState.INITIALIZING] = [
            StateTransition(
                from_state=AgentState.INITIALIZING,
                to_state=AgentState.PLANNING,
                allowed_tools={"file_read", "file_write", "workflow_create"},
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 规划器状态转换
        self.state_transitions[AgentState.PLANNING] = [
            StateTransition(
                from_state=AgentState.PLANNING,
                to_state=AgentState.RESEARCHING,
                allowed_tools={"knowledge_search", "file_write", "workflow_update"},
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 研究员状态转换
        self.state_transitions[AgentState.RESEARCHING] = [
            StateTransition(
                from_state=AgentState.RESEARCHING,
                to_state=AgentState.GENERATING_MINDMAP,
                allowed_tools={
                    "knowledge_search",
                    "knowledge_retrieve",
                    "browser_search",
                    "file_write",
                },
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 测试员状态转换 - 生成思维导图
        self.state_transitions[AgentState.GENERATING_MINDMAP] = [
            StateTransition(
                from_state=AgentState.GENERATING_MINDMAP,
                to_state=AgentState.GENERATING_TESTCASES,
                allowed_tools={"knowledge_search", "file_read", "file_write"},
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 测试员状态转换 - 生成测试用例
        self.state_transitions[AgentState.GENERATING_TESTCASES] = [
            StateTransition(
                from_state=AgentState.GENERATING_TESTCASES,
                to_state=AgentState.CODING,
                allowed_tools={
                    "knowledge_retrieve",
                    "file_read",
                    "file_write",
                    "browser_search",
                },
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 编码员状态转换
        self.state_transitions[AgentState.CODING] = [
            StateTransition(
                from_state=AgentState.CODING,
                to_state=AgentState.EXECUTING,
                allowed_tools={
                    "file_read",
                    "file_write",
                    "knowledge_search",
                    "browser_search",
                },
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 执行器状态转换
        self.state_transitions[AgentState.EXECUTING] = [
            StateTransition(
                from_state=AgentState.EXECUTING,
                to_state=AgentState.REVIEWING,
                allowed_tools={"sandbox_execute", "file_read", "file_write"},
                call_mode=ToolCallMode.REQUIRED,
            )
        ]

        # 评审员状态转换
        self.state_transitions[AgentState.REVIEWING] = [
            StateTransition(
                from_state=AgentState.REVIEWING,
                to_state=AgentState.REPORTING,
                allowed_tools={"file_read", "file_write", "knowledge_search"},
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        # 报告员状态转换
        self.state_transitions[AgentState.REPORTING] = [
            StateTransition(
                from_state=AgentState.REPORTING,
                to_state=AgentState.COMPLETED,
                allowed_tools={"file_read", "file_write", "workflow_update"},
                call_mode=ToolCallMode.SPECIFIED,
            )
        ]

        logger.info(f"初始化了 {len(self.state_transitions)} 个状态转换规则")

    def set_agent_state(self, agent_name: str, state: AgentState):
        """设置智能体状态

        Args:
            agent_name: 智能体名称
            state: 新状态
        """
        old_state = self.current_state
        self.current_state = state
        self.current_agent = agent_name

        # 清除缓存，强制重新计算工具可用性
        self._clear_availability_cache()

        logger.info(
            f"智能体 {agent_name} 状态从 {old_state.value} 转换到 {state.value}"
        )

    def set_call_mode(self, mode: ToolCallMode):
        """设置工具调用模式

        Args:
            mode: 调用模式
        """
        old_mode = self.call_mode
        self.call_mode = mode

        # 清除缓存
        self._clear_availability_cache()

        logger.info(f"工具调用模式从 {old_mode.value} 切换到 {mode.value}")

    def get_available_tools(
        self,
        agent_state: Optional[AgentState] = None,
        mode: Optional[ToolCallMode] = None,
    ) -> List[str]:
        """获取当前可用的工具列表

        Args:
            agent_state: 智能体状态（可选，默认使用当前状态）
            mode: 调用模式（可选，默认使用当前模式）

        Returns:
            可用工具列表
        """
        state = agent_state or self.current_state
        call_mode = mode or self.call_mode

        # 检查缓存
        cache_key = f"{state.value}_{call_mode.value}"
        if self._is_cache_valid() and cache_key in self._availability_cache:
            return list(self._availability_cache[cache_key])

        # 计算可用工具
        available_tools = self._calculate_available_tools(state, call_mode)

        # 更新缓存
        self._availability_cache[cache_key] = set(available_tools)
        self._cache_timestamp = datetime.now()

        return available_tools

    def _calculate_available_tools(
        self, state: AgentState, mode: ToolCallMode
    ) -> List[str]:
        """计算可用工具列表

        Args:
            state: 智能体状态
            mode: 调用模式

        Returns:
            可用工具列表
        """
        if mode == ToolCallMode.AUTO:
            # 自动模式：返回所有启用的工具
            return [
                name
                for name, tool_def in self.tool_definitions.items()
                if tool_def.enabled
            ]

        elif mode == ToolCallMode.REQUIRED:
            # 必需模式：返回当前状态下必需的工具
            return self._get_required_tools(state)

        elif mode == ToolCallMode.SPECIFIED:
            # 指定模式：返回当前状态下指定的工具子集
            return self._get_specified_tools(state)

        else:
            logger.warning(f"未知的调用模式: {mode}")
            return []

    def _get_required_tools(self, state: AgentState) -> List[str]:
        """获取必需工具列表

        Args:
            state: 智能体状态

        Returns:
            必需工具列表
        """
        # 根据状态返回必需的工具
        required_tools_map = {
            AgentState.EXECUTING: ["sandbox_execute"],
            AgentState.RESEARCHING: ["knowledge_search", "browser_search"],
            AgentState.CODING: ["file_write"],
            AgentState.REVIEWING: ["file_read"],
            AgentState.REPORTING: ["file_write"],
        }

        return required_tools_map.get(state, [])

    def _get_specified_tools(self, state: AgentState) -> List[str]:
        """获取指定工具列表

        Args:
            state: 智能体状态

        Returns:
            指定工具列表
        """
        # 从状态转换规则中获取允许的工具
        transitions = self.state_transitions.get(state, [])

        if not transitions:
            # 如果没有定义转换规则，返回所有工具
            return list(self.all_tools)

        # 合并所有转换规则中允许的工具
        allowed_tools = set()
        for transition in transitions:
            allowed_tools.update(transition.allowed_tools)

        # 只返回启用的工具
        return [
            tool
            for tool in allowed_tools
            if tool in self.tool_definitions and self.tool_definitions[tool].enabled
        ]

    def get_tools_by_category(self, category: str) -> List[str]:
        """根据类别获取工具列表

        Args:
            category: 工具类别（如 'file', 'knowledge'）

        Returns:
            该类别的工具列表
        """
        category_prefix = f"{category}_"
        return [
            name
            for name, tool_def in self.tool_definitions.items()
            if tool_def.category == category and tool_def.enabled
        ]

    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用

        Args:
            tool_name: 工具名称

        Returns:
            工具是否可用
        """
        available_tools = self.get_available_tools()
        return tool_name in available_tools

    def get_constraint_config(
        self, state: Optional[AgentState] = None, mode: Optional[ToolCallMode] = None
    ) -> Dict[str, Any]:
        """获取约束解码配置

        Args:
            state: 智能体状态
            mode: 调用模式

        Returns:
            约束解码配置
        """
        state = state or self.current_state
        mode = mode or self.call_mode

        available_tools = self.get_available_tools(state, mode)

        # 构建约束解码配置
        config = {
            "mode": mode.value,
            "state": state.value,
            "available_tools": available_tools,
            "tool_schemas": self._get_tool_schemas(available_tools),
            "response_prefill": self._get_response_prefill(mode, available_tools),
        }

        return config

    def _get_tool_schemas(self, tool_names: List[str]) -> List[Dict[str, Any]]:
        """获取工具的JSON Schema

        Args:
            tool_names: 工具名称列表

        Returns:
            工具Schema列表
        """
        schemas = []
        for tool_name in tool_names:
            if tool_name in self.tool_definitions:
                tool_def = self.tool_definitions[tool_name]
                schema = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_def.description,
                        "parameters": tool_def.parameters,
                    },
                }
                schemas.append(schema)

        return schemas

    def _get_response_prefill(
        self, mode: ToolCallMode, available_tools: List[str]
    ) -> Optional[str]:
        """获取响应预填充内容

        Args:
            mode: 调用模式
            available_tools: 可用工具列表

        Returns:
            预填充内容
        """
        if mode == ToolCallMode.REQUIRED and available_tools:
            # 必需模式：预填充工具调用开始
            return '{"tool_calls": [{"type": "function", "function": {"name": "'

        elif mode == ToolCallMode.SPECIFIED and len(available_tools) == 1:
            # 指定模式且只有一个工具：预填充该工具调用
            tool_name = available_tools[0]
            return f'{{"tool_calls": [{{"type": "function", "function": {{"name": "{tool_name}", "arguments": "'

        return None

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效

        Returns:
            缓存是否有效
        """
        if not self._cache_timestamp:
            return False

        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self.cache_ttl

    def _clear_availability_cache(self):
        """清除可用性缓存"""
        self._availability_cache.clear()
        self._cache_timestamp = None

    def enable_tool(self, tool_name: str):
        """启用工具

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.tool_definitions:
            self.tool_definitions[tool_name].enabled = True
            self._clear_availability_cache()
            logger.info(f"启用工具: {tool_name}")
        else:
            logger.warning(f"工具不存在: {tool_name}")

    def disable_tool(self, tool_name: str):
        """禁用工具

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.tool_definitions:
            self.tool_definitions[tool_name].enabled = False
            self._clear_availability_cache()
            logger.info(f"禁用工具: {tool_name}")
        else:
            logger.warning(f"工具不存在: {tool_name}")

    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """获取工具定义

        Args:
            tool_name: 工具名称

        Returns:
            工具定义或None
        """
        return self.tool_definitions.get(tool_name)

    def get_state_info(self) -> Dict[str, Any]:
        """获取状态机信息

        Returns:
            状态机信息
        """
        return {
            "current_state": self.current_state.value,
            "current_agent": self.current_agent,
            "call_mode": self.call_mode.value,
            "total_tools": len(self.tool_definitions),
            "enabled_tools": len(
                [t for t in self.tool_definitions.values() if t.enabled]
            ),
            "available_tools": len(self.get_available_tools()),
            "cache_valid": self._is_cache_valid(),
            "cache_entries": len(self._availability_cache),
        }

    def export_config(self) -> Dict[str, Any]:
        """导出配置

        Returns:
            配置字典
        """
        return {
            "tool_definitions": {
                name: {
                    "name": tool_def.name,
                    "category": tool_def.category,
                    "description": tool_def.description,
                    "enabled": tool_def.enabled,
                    "priority": tool_def.priority,
                }
                for name, tool_def in self.tool_definitions.items()
            },
            "state_transitions": {
                state.value: [
                    {
                        "from_state": trans.from_state.value,
                        "to_state": trans.to_state.value,
                        "allowed_tools": list(trans.allowed_tools),
                        "call_mode": trans.call_mode.value,
                    }
                    for trans in transitions
                ]
                for state, transitions in self.state_transitions.items()
            },
            "current_state": self.current_state.value,
            "current_agent": self.current_agent,
            "call_mode": self.call_mode.value,
        }


# 全局工具状态机实例
_tool_state_machine: Optional[ToolStateMachine] = None


def get_tool_state_machine() -> ToolStateMachine:
    """获取全局工具状态机实例

    Returns:
        工具状态机实例
    """
    global _tool_state_machine
    if _tool_state_machine is None:
        _tool_state_machine = ToolStateMachine()
    return _tool_state_machine


def set_agent_state(agent_name: str, state: AgentState):
    """设置智能体状态的便捷函数

    Args:
        agent_name: 智能体名称
        state: 新状态
    """
    state_machine = get_tool_state_machine()
    state_machine.set_agent_state(agent_name, state)


def get_available_tools_for_agent(
    agent_name: str, state: AgentState, mode: ToolCallMode = ToolCallMode.AUTO
) -> List[str]:
    """获取智能体可用工具的便捷函数

    Args:
        agent_name: 智能体名称
        state: 智能体状态
        mode: 调用模式

    Returns:
        可用工具列表
    """
    state_machine = get_tool_state_machine()
    state_machine.set_agent_state(agent_name, state)
    state_machine.set_call_mode(mode)
    return state_machine.get_available_tools()


def get_constraint_config_for_llm(
    agent_name: str, state: AgentState, mode: ToolCallMode = ToolCallMode.AUTO
) -> Dict[str, Any]:
    """获取LLM约束解码配置的便捷函数

    Args:
        agent_name: 智能体名称
        state: 智能体状态
        mode: 调用模式

    Returns:
        约束解码配置
    """
    state_machine = get_tool_state_machine()
    state_machine.set_agent_state(agent_name, state)
    state_machine.set_call_mode(mode)
    return state_machine.get_constraint_config()
