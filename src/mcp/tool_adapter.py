#!/usr/bin/env python3
"""
MCP工具适配器
将MCP工具适配为TestAgent可用的工具
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from ..exceptions import MCPIntegrationException
from .server_manager import MCPServerManager, get_mcp_manager

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """MCP工具适配器"""

    def __init__(self, manager: Optional[MCPServerManager] = None):
        self.manager = manager or get_mcp_manager()
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._last_cache_update: Optional[datetime] = None
        self.cache_ttl = 300  # 缓存5分钟

    def _update_tool_cache(self):
        """更新工具缓存"""
        try:
            now = datetime.now()

            # 检查缓存是否需要更新
            if (
                self._last_cache_update
                and (now - self._last_cache_update).seconds < self.cache_ttl
            ):
                return

            logger.debug("更新MCP工具缓存")

            self._tool_cache.clear()

            # 获取所有可用工具
            available_tools = self.manager.get_available_tools()

            for server_name, tool_names in available_tools.items():
                for tool_name in tool_names:
                    # 获取工具详细信息
                    tool_info = self.manager.get_tool_info(server_name, tool_name)
                    if tool_info:
                        # 创建唯一的工具标识符
                        tool_id = f"{server_name}.{tool_name}"

                        self._tool_cache[tool_id] = {
                            "server_name": server_name,
                            "tool_name": tool_name,
                            "description": tool_info.get("description", ""),
                            "input_schema": tool_info.get("inputSchema", {}),
                            "full_name": tool_id,
                        }

            self._last_cache_update = now
            logger.debug(f"更新了 {len(self._tool_cache)} 个MCP工具")

        except Exception as e:
            logger.error(f"更新MCP工具缓存失败: {e}")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用的MCP工具"""
        self._update_tool_cache()
        return list(self._tool_cache.values())

    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取工具信息"""
        self._update_tool_cache()

        # 支持完整名称（server.tool）和简单名称（tool）
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]

        # 如果是简单名称，查找匹配的工具
        for tool_id, tool_info in self._tool_cache.items():
            if tool_info["tool_name"] == tool_name:
                return tool_info

        return None

    def search_tools(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索工具"""
        self._update_tool_cache()

        keyword = keyword.lower()
        matching_tools = []

        for tool_info in self._tool_cache.values():
            # 在工具名称和描述中搜索
            if (
                keyword in tool_info["tool_name"].lower()
                or keyword in tool_info["description"].lower()
            ):
                matching_tools.append(tool_info)

        return matching_tools

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用MCP工具"""
        try:
            # 获取工具信息
            tool_info = self.get_tool_by_name(tool_name)
            if not tool_info:
                raise MCPIntegrationException(f"工具 {tool_name} 不存在")

            server_name = tool_info["server_name"]
            actual_tool_name = tool_info["tool_name"]

            logger.info(f"调用MCP工具: {server_name}.{actual_tool_name}")

            # 验证参数
            self._validate_arguments(tool_info, arguments)

            # 调用工具
            result = await self.manager.call_tool(
                server_name, actual_tool_name, arguments
            )

            # 包装结果
            return {
                "tool_name": tool_name,
                "server_name": server_name,
                "success": result.get("success", False),
                "result": result.get("result"),
                "error": result.get("error"),
                "timestamp": result.get("timestamp"),
                "execution_time": self._calculate_execution_time(result),
            }

        except Exception as e:
            logger.error(f"调用MCP工具失败 {tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _validate_arguments(self, tool_info: Dict[str, Any], arguments: Dict[str, Any]):
        """验证工具参数"""
        try:
            input_schema = tool_info.get("input_schema", {})

            # 如果没有schema，跳过验证
            if not input_schema:
                return

            # 简单的参数验证
            required_props = input_schema.get("required", [])
            properties = input_schema.get("properties", {})

            # 检查必需参数
            for prop in required_props:
                if prop not in arguments:
                    raise MCPIntegrationException(f"缺少必需参数: {prop}")

            # 检查参数类型（简单验证）
            for prop, value in arguments.items():
                if prop in properties:
                    prop_type = properties[prop].get("type")
                    if prop_type and not self._check_type(value, prop_type):
                        raise MCPIntegrationException(
                            f"参数 {prop} 类型错误，期望: {prop_type}"
                        )

        except Exception as e:
            logger.warning(f"参数验证失败: {e}")
            # 不阻止工具调用，只记录警告

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)

        return True  # 未知类型，跳过检查

    def _calculate_execution_time(self, result: Dict[str, Any]) -> Optional[float]:
        """计算执行时间"""
        try:
            if "timestamp" in result:
                # 这里可以实现更复杂的执行时间计算
                # 目前返回None，表示未计算
                pass
        except Exception:
            pass
        return None

    def create_tool_function(self, tool_name: str) -> Callable:
        """创建工具函数"""

        async def tool_function(**kwargs):
            return await self.call_tool(tool_name, kwargs)

        # 获取工具信息用于函数文档
        tool_info = self.get_tool_by_name(tool_name)
        if tool_info:
            tool_function.__name__ = tool_info["tool_name"]
            tool_function.__doc__ = tool_info["description"]

        return tool_function

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具的JSON Schema"""
        tool_info = self.get_tool_by_name(tool_name)
        if tool_info:
            return {
                "name": tool_info["tool_name"],
                "description": tool_info["description"],
                "parameters": tool_info.get("input_schema", {}),
            }
        return None

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取适用于LLM的工具描述"""
        tools = []

        for tool_info in self.get_available_tools():
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_info["full_name"],
                    "description": tool_info["description"],
                    "parameters": tool_info.get("input_schema", {}),
                },
            }
            tools.append(tool_schema)

        return tools

    def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """获取特定服务器的工具"""
        self._update_tool_cache()

        server_tools = []
        for tool_info in self._tool_cache.values():
            if tool_info["server_name"] == server_name:
                server_tools.append(tool_info)

        return server_tools

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._update_tool_cache()

        servers = set()
        for tool_info in self._tool_cache.values():
            servers.add(tool_info["server_name"])

        return {
            "total_tools": len(self._tool_cache),
            "total_servers": len(servers),
            "servers": list(servers),
            "cache_last_updated": (
                self._last_cache_update.isoformat() if self._last_cache_update else None
            ),
        }


# 全局适配器实例
_mcp_adapter: Optional[MCPToolAdapter] = None


def get_mcp_adapter() -> MCPToolAdapter:
    """获取MCP工具适配器实例"""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPToolAdapter()
    return _mcp_adapter
