"""工具模块"""


# 延迟导入以避免循环依赖
def get_python_repl():
    from .python_repl import PythonREPL

    return PythonREPL


def get_document_retrieval_tool():
    from .document_retrieval import (
        DocumentRetrievalTool,
        document_search_tool,
        keyword_search_tool,
    )

    return DocumentRetrievalTool, document_search_tool, keyword_search_tool


def get_web_search_tool():
    from .web_search import WebSearchTool, web_search_tool, webpage_content_tool

    return WebSearchTool, web_search_tool, webpage_content_tool


def get_decorators():
    from .decorators import (
        tool,
        rate_limit,
        validate_input,
        cache_result,
        get_tool_registry,
        list_available_tools,
        get_tool_metrics,
        get_tool_info,
    )

    return (
        tool,
        rate_limit,
        validate_input,
        cache_result,
        get_tool_registry,
        list_available_tools,
        get_tool_metrics,
        get_tool_info,
    )


def get_tool_manager():
    from .tool_manager import ToolManager, get_tool_manager

    return ToolManager, get_tool_manager


def get_mcp_tools():
    from ..mcp import MCPToolAdapter, get_mcp_adapter

    return MCPToolAdapter, get_mcp_adapter


# 直接导入不依赖其他模块的组件
from .python_repl import PythonREPL
from .decorators import (
    tool,
    rate_limit,
    validate_input,
    cache_result,
    get_tool_registry,
    list_available_tools,
    get_tool_metrics,
    get_tool_info,
)
from .tool_manager import ToolManager, get_tool_manager

# 工具状态机和约束解码组件
from .state_machine import (
    ToolStateMachine,
    AgentState,
    ToolCallMode,
    ToolDefinition,
    get_tool_state_machine,
    set_agent_state,
    get_available_tools_for_agent,
    get_constraint_config_for_llm,
)
from .constraint_decoder import (
    ConstraintDecoder,
    TokenConstraint,
    get_constraint_decoder,
    apply_tool_constraints,
    get_tool_call_prefill,
)
from .enhanced_tool_manager import (
    EnhancedToolManager,
    ToolExecutionContext,
    get_enhanced_tool_manager,
    set_tool_context,
    execute_tool_with_context,
    get_available_tools_for_current_context,
    get_llm_constraint_config,
)

__all__ = [
    # 核心工具类
    "PythonREPL",
    "DocumentRetrievalTool",
    "WebSearchTool",
    "ToolManager",
    # 工具装饰器函数
    "document_search_tool",
    "keyword_search_tool",
    "web_search_tool",
    "webpage_content_tool",
    # 装饰器
    "tool",
    "rate_limit",
    "validate_input",
    "cache_result",
    # 工具管理函数
    "get_tool_registry",
    "list_available_tools",
    "get_tool_metrics",
    "get_tool_info",
    "get_tool_manager",
    # 工具状态机组件
    "ToolStateMachine",
    "AgentState",
    "ToolCallMode",
    "ToolDefinition",
    "get_tool_state_machine",
    "set_agent_state",
    "get_available_tools_for_agent",
    "get_constraint_config_for_llm",
    # 约束解码组件
    "ConstraintDecoder",
    "TokenConstraint",
    "get_constraint_decoder",
    "apply_tool_constraints",
    "get_tool_call_prefill",
    # 增强工具管理器
    "EnhancedToolManager",
    "ToolExecutionContext",
    "get_enhanced_tool_manager",
    "set_tool_context",
    "execute_tool_with_context",
    "get_available_tools_for_current_context",
    "get_llm_constraint_config",
]
