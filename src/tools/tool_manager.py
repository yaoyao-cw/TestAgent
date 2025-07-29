"""工具管理器模块"""

import asyncio
from typing import Dict, Any, List, Optional, Type, Union
from dataclasses import dataclass
from datetime import datetime

from .python_repl import PythonREPL
from .web_search import WebSearchTool
from .document_retrieval import DocumentRetrievalTool
from .workflow_tools import WorkflowTools
from .decorators import tool_registry, ToolRegistry
from ..config.logging_config import get_logger
from ..exceptions import ToolException, MCPIntegrationException
from ..mcp import get_mcp_adapter, get_mcp_manager

logger = get_logger("tool_manager")


@dataclass
class ToolConfig:
    """工具配置"""

    name: str
    tool_class: Type
    config: Dict[str, Any]
    enabled: bool = True
    category: str = "general"
    description: str = ""


class ToolManager:
    """工具管理器，负责管理和协调所有工具"""

    def __init__(self):
        """初始化工具管理器"""
        self.tools: Dict[str, Any] = {}
        self.tool_configs: Dict[str, ToolConfig] = {}
        self.registry = tool_registry
        self._initialized = False
        self.mcp_adapter = None
        self.mcp_manager = None

        logger.info("Tool manager initialized")

    def register_tool_config(self, config: ToolConfig):
        """注册工具配置

        Args:
            config: 工具配置
        """
        self.tool_configs[config.name] = config
        logger.info(f"Registered tool config: {config.name}")

    async def initialize_tools(self):
        """初始化所有工具"""
        if self._initialized:
            return

        try:
            # 初始化基础工具
            await self._initialize_basic_tools()

            # 初始化配置的工具
            for name, config in self.tool_configs.items():
                if config.enabled:
                    await self._initialize_tool(name, config)

            self._initialized = True
            logger.info(f"Initialized {len(self.tools)} tools")

        except Exception as e:
            logger.error(f"Failed to initialize tools: {e}")
            raise ToolException(f"工具初始化失败: {e}")

    async def _initialize_basic_tools(self):
        """初始化基础工具"""
        # Python REPL工具
        python_repl = PythonREPL(timeout=30, max_output_length=10000)
        self.tools["python_repl"] = python_repl

        # Web搜索工具
        web_search = WebSearchTool(timeout=30, max_results=10)
        self.tools["web_search"] = web_search

        # 工作流工具
        workflow_tools = WorkflowTools()
        self.tools["workflow"] = workflow_tools

        # 初始化MCP工具
        await self._initialize_mcp_tools()

        logger.info("Basic tools initialized")

    async def _initialize_mcp_tools(self):
        """初始化MCP工具"""
        try:
            # 获取MCP管理器和适配器
            self.mcp_manager = get_mcp_manager()
            self.mcp_adapter = get_mcp_adapter()

            # 启动MCP管理器
            await self.mcp_manager.start()

            # 将MCP适配器添加到工具列表
            self.tools["mcp"] = self.mcp_adapter

            logger.info("MCP tools initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize MCP tools: {e}")
            # MCP工具初始化失败不应该阻止整个系统启动

    async def _initialize_tool(self, name: str, config: ToolConfig):
        """初始化单个工具

        Args:
            name: 工具名称
            config: 工具配置
        """
        try:
            tool_instance = config.tool_class(**config.config)
            self.tools[name] = tool_instance
            logger.info(f"Initialized tool: {name}")

        except Exception as e:
            logger.error(f"Failed to initialize tool {name}: {e}")
            if config.enabled:
                raise ToolException(f"必需工具 {name} 初始化失败: {e}")

    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具实例

        Args:
            name: 工具名称

        Returns:
            工具实例或None
        """
        if not self._initialized:
            raise ToolException("工具管理器未初始化")

        return self.tools.get(name)

    def list_tools(
        self, category: Optional[str] = None, enabled_only: bool = True
    ) -> Dict[str, Any]:
        """列出工具

        Args:
            category: 工具类别过滤
            enabled_only: 是否只列出启用的工具

        Returns:
            工具信息字典
        """
        if not self._initialized:
            raise ToolException("工具管理器未初始化")

        result = {}

        for name, tool in self.tools.items():
            config = self.tool_configs.get(name)

            # 过滤条件
            if enabled_only and config and not config.enabled:
                continue

            if category and config and config.category != category:
                continue

            # 获取工具信息
            tool_info = {
                "name": name,
                "type": type(tool).__name__,
                "enabled": config.enabled if config else True,
                "category": config.category if config else "basic",
                "description": config.description if config else "",
            }

            # 如果工具有get_tool_info方法，获取详细信息
            if hasattr(tool, "get_tool_info"):
                try:
                    detailed_info = tool.get_tool_info()
                    tool_info.update(detailed_info)
                except Exception as e:
                    logger.warning(f"Failed to get tool info for {name}: {e}")

            result[name] = tool_info

        return result

    async def execute_tool(
        self, tool_name: str, method_name: str, *args, **kwargs
    ) -> Dict[str, Any]:
        """执行工具方法

        Args:
            tool_name: 工具名称
            method_name: 方法名称
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        try:
            tool = self.get_tool(tool_name)
            if not tool:
                return {
                    "success": False,
                    "error": f"工具 {tool_name} 不存在",
                    "tool_name": tool_name,
                    "method_name": method_name,
                }

            if not hasattr(tool, method_name):
                return {
                    "success": False,
                    "error": f"工具 {tool_name} 没有方法 {method_name}",
                    "tool_name": tool_name,
                    "method_name": method_name,
                }

            method = getattr(tool, method_name)

            # 执行方法
            start_time = datetime.now()

            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)

            execution_time = (datetime.now() - start_time).total_seconds()

            # 包装结果
            if isinstance(result, dict) and "success" in result:
                # 如果结果已经是标准格式，直接返回
                result["execution_time"] = execution_time
                result["tool_name"] = tool_name
                result["method_name"] = method_name
                return result
            else:
                # 包装为标准格式
                return {
                    "success": True,
                    "result": result,
                    "execution_time": execution_time,
                    "tool_name": tool_name,
                    "method_name": method_name,
                }

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}.{method_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "method_name": method_name,
                "execution_time": 0,
            }

    def get_tool_metrics(self) -> Dict[str, Any]:
        """获取工具指标

        Returns:
            工具指标摘要
        """
        return self.registry.get_metrics_summary()

    def get_tool_registry(self) -> ToolRegistry:
        """获取工具注册表

        Returns:
            工具注册表实例
        """
        return self.registry

    async def health_check(self) -> Dict[str, Any]:
        """健康检查

        Returns:
            健康检查结果
        """
        if not self._initialized:
            return {"healthy": False, "error": "工具管理器未初始化", "tools": {}}

        tool_health = {}
        overall_healthy = True

        for name, tool in self.tools.items():
            try:
                # 基本健康检查
                if hasattr(tool, "health_check"):
                    health = await tool.health_check()
                else:
                    # 简单检查工具是否可用
                    health = {"healthy": True, "status": "available"}

                tool_health[name] = health

                if not health.get("healthy", True):
                    overall_healthy = False

            except Exception as e:
                tool_health[name] = {"healthy": False, "error": str(e)}
                overall_healthy = False

        return {
            "healthy": overall_healthy,
            "initialized": self._initialized,
            "total_tools": len(self.tools),
            "tools": tool_health,
            "metrics": self.get_tool_metrics(),
        }

    async def shutdown(self):
        """关闭工具管理器"""
        logger.info("Shutting down tool manager")

        # 首先关闭MCP管理器
        if self.mcp_manager:
            try:
                await self.mcp_manager.stop()
                logger.info("MCP manager stopped")
            except Exception as e:
                logger.warning(f"Failed to stop MCP manager: {e}")

        for name, tool in self.tools.items():
            try:
                if hasattr(tool, "close"):
                    if asyncio.iscoroutinefunction(tool.close):
                        await tool.close()
                    else:
                        tool.close()
                elif hasattr(tool, "shutdown"):
                    if asyncio.iscoroutinefunction(tool.shutdown):
                        await tool.shutdown()
                    else:
                        tool.shutdown()

                logger.info(f"Closed tool: {name}")

            except Exception as e:
                logger.warning(f"Failed to close tool {name}: {e}")

        self.tools.clear()
        self.mcp_adapter = None
        self.mcp_manager = None
        self._initialized = False
        logger.info("Tool manager shutdown complete")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize_tools()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.shutdown()


# 全局工具管理器实例
_tool_manager = None


def get_tool_manager() -> ToolManager:
    """获取全局工具管理器实例

    Returns:
        工具管理器实例
    """
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager


async def initialize_global_tools():
    """初始化全局工具"""
    manager = get_tool_manager()
    await manager.initialize_tools()
    return manager


# 便捷函数
async def execute_python_code(
    code: str, variables: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """执行Python代码的便捷函数

    Args:
        code: Python代码
        variables: 预设变量

    Returns:
        执行结果
    """
    manager = get_tool_manager()
    return await manager.execute_tool("python_repl", "execute_code", code, variables)


async def search_web(
    query: str, engine: str = "auto", max_results: int = 10
) -> Dict[str, Any]:
    """网络搜索的便捷函数

    Args:
        query: 搜索查询
        engine: 搜索引擎
        max_results: 最大结果数量

    Returns:
        搜索结果
    """
    manager = get_tool_manager()
    return await manager.execute_tool(
        "web_search", "search", query, engine, max_results
    )


async def get_webpage_content(url: str, max_length: int = 5000) -> Dict[str, Any]:
    """获取网页内容的便捷函数

    Args:
        url: 网页URL
        max_length: 最大内容长度

    Returns:
        网页内容
    """
    manager = get_tool_manager()
    return await manager.execute_tool(
        "web_search", "get_webpage_content", url, max_length
    )


# MCP工具便捷函数
async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """调用MCP工具的便捷函数

    Args:
        tool_name: MCP工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    manager = get_tool_manager()
    return await manager.execute_tool("mcp", "call_tool", tool_name, arguments)


def get_available_mcp_tools() -> List[Dict[str, Any]]:
    """获取可用MCP工具的便捷函数

    Returns:
        可用的MCP工具列表
    """
    manager = get_tool_manager()
    mcp_adapter = manager.get_tool("mcp")
    if mcp_adapter:
        return mcp_adapter.get_available_tools()
    return []


def search_mcp_tools(keyword: str) -> List[Dict[str, Any]]:
    """搜索MCP工具的便捷函数

    Args:
        keyword: 搜索关键词

    Returns:
        匹配的MCP工具列表
    """
    manager = get_tool_manager()
    mcp_adapter = manager.get_tool("mcp")
    if mcp_adapter:
        return mcp_adapter.search_tools(keyword)
    return []


def get_mcp_tools_for_llm() -> List[Dict[str, Any]]:
    """获取适用于LLM的MCP工具描述

    Returns:
        LLM工具描述列表
    """
    manager = get_tool_manager()
    mcp_adapter = manager.get_tool("mcp")
    if mcp_adapter:
        return mcp_adapter.get_tools_for_llm()
    return []
