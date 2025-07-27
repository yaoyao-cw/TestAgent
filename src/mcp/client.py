#!/usr/bin/env python3
"""
MCP客户端实现
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..exceptions import MCPIntegrationException
from .config import MCPServerConfig
from .sse_client import MCPSSEClient

logger = logging.getLogger(__name__)


class MCPStdioClient:
    """MCP Stdio客户端"""

    def __init__(self, server_name: str, server_config: MCPServerConfig):
        self.server_name = server_name
        self.server_config = server_config
        self.session: Optional[ClientSession] = None
        self.process: Optional[subprocess.Popen] = None
        self.connected = False
        self.tools: Dict[str, Any] = {}
        self.resources: Dict[str, Any] = {}
        self.connection_time: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None

        if server_config.connection_type != "stdio":
            raise ValueError("服务器配置必须是stdio类型")

    async def connect(self) -> bool:
        """连接到MCP服务器"""
        try:
            logger.info(f"连接到MCP服务器: {self.server_name}")

            # 创建服务器参数
            server_params = StdioServerParameters(
                command=self.server_config.command,
                args=self.server_config.args,
                env=self.server_config.env,
            )

            # 建立连接
            async with stdio_client(server_params) as (read, write):
                self.session = ClientSession(read, write)

                # 初始化会话
                await self.session.initialize()

                # 获取工具列表
                await self._load_tools()

                # 获取资源列表
                await self._load_resources()

                self.connected = True
                self.connection_time = datetime.now()
                self.last_activity = datetime.now()

                logger.info(f"成功连接到MCP服务器: {self.server_name}")
                logger.info(f"可用工具: {list(self.tools.keys())}")
                logger.info(f"可用资源: {list(self.resources.keys())}")

                return True

        except Exception as e:
            logger.error(f"连接MCP服务器失败 {self.server_name}: {e}")
            self.connected = False
            raise MCPIntegrationException(f"连接MCP服务器失败 {self.server_name}: {e}")

    async def disconnect(self):
        """断开连接"""
        try:
            if self.session:
                await self.session.close()
                self.session = None

            if self.process:
                self.process.terminate()
                self.process = None

            self.connected = False
            self.connection_time = None
            logger.info(f"已断开MCP服务器连接: {self.server_name}")

        except Exception as e:
            logger.error(f"断开MCP服务器连接失败 {self.server_name}: {e}")

    async def _load_tools(self):
        """加载工具列表"""
        try:
            if not self.session:
                return

            # 获取工具列表
            tools_result = await self.session.list_tools()

            self.tools = {}
            for tool in tools_result.tools:
                self.tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }

            logger.debug(f"加载了 {len(self.tools)} 个工具")

        except Exception as e:
            logger.error(f"加载工具列表失败: {e}")

    async def _load_resources(self):
        """加载资源列表"""
        try:
            if not self.session:
                return

            # 获取资源列表
            resources_result = await self.session.list_resources()

            self.resources = {}
            for resource in resources_result.resources:
                self.resources[resource.uri] = {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType,
                }

            logger.debug(f"加载了 {len(self.resources)} 个资源")

        except Exception as e:
            logger.error(f"加载资源列表失败: {e}")

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用工具"""
        try:
            if not self.connected or not self.session:
                raise MCPIntegrationException(f"MCP服务器 {self.server_name} 未连接")

            if tool_name not in self.tools:
                raise MCPIntegrationException(f"工具 {tool_name} 不存在")

            logger.info(f"调用MCP工具: {tool_name} (参数: {arguments})")

            # 调用工具
            result = await self.session.call_tool(tool_name, arguments)

            self.last_activity = datetime.now()

            # 处理结果
            tool_result = {
                "tool_name": tool_name,
                "success": True,
                "result": result.content,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"MCP工具调用成功: {tool_name}")
            return tool_result

        except Exception as e:
            logger.error(f"调用MCP工具失败 {tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def read_resource(self, resource_uri: str) -> Dict[str, Any]:
        """读取资源"""
        try:
            if not self.connected or not self.session:
                raise MCPIntegrationException(f"MCP服务器 {self.server_name} 未连接")

            if resource_uri not in self.resources:
                raise MCPIntegrationException(f"资源 {resource_uri} 不存在")

            logger.info(f"读取MCP资源: {resource_uri}")

            # 读取资源
            result = await self.session.read_resource(resource_uri)

            self.last_activity = datetime.now()

            # 处理结果
            resource_result = {
                "uri": resource_uri,
                "success": True,
                "content": result.contents,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"MCP资源读取成功: {resource_uri}")
            return resource_result

        except Exception as e:
            logger.error(f"读取MCP资源失败 {resource_uri}: {e}")
            return {
                "uri": resource_uri,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        return self.tools.get(tool_name)

    def get_resource_info(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """获取资源信息"""
        return self.resources.get(resource_uri)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())

    def list_resources(self) -> List[str]:
        """列出所有资源"""
        return list(self.resources.keys())

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            "server_name": self.server_name,
            "connected": self.connected,
            "connection_time": (
                self.connection_time.isoformat() if self.connection_time else None
            ),
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
            "tools_count": len(self.tools),
            "resources_count": len(self.resources),
            "tools": list(self.tools.keys()),
            "resources": list(self.resources.keys()),
        }

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self.connected or not self.session:
                return False

            # 尝试列出工具（轻量级操作）
            await self.session.list_tools()
            self.last_activity = datetime.now()
            return True

        except Exception as e:
            logger.error(f"MCP服务器健康检查失败 {self.server_name}: {e}")
            self.connected = False
            return False


# 统一的MCP客户端类型
MCPClient = Union[MCPStdioClient, MCPSSEClient]


def create_mcp_client(server_name: str, server_config: MCPServerConfig) -> MCPClient:
    """创建MCP客户端工厂函数

    Args:
        server_name: 服务器名称
        server_config: 服务器配置

    Returns:
        相应类型的MCP客户端实例

    Raises:
        ValueError: 不支持的连接类型
    """
    if server_config.connection_type == "stdio":
        return MCPStdioClient(server_name, server_config)
    elif server_config.connection_type == "sse":
        return MCPSSEClient(server_name, server_config)
    else:
        raise ValueError(f"不支持的连接类型: {server_config.connection_type}")


# 为了向后兼容，保留原来的MCPClient类名
class MCPClient(MCPStdioClient):
    """MCP客户端（向后兼容）"""

    def __init__(self, server_name: str, server_config: MCPServerConfig):
        # 如果是stdio类型，使用stdio客户端
        if server_config.connection_type == "stdio":
            super().__init__(server_name, server_config)
        else:
            # 对于非stdio类型，建议使用工厂函数
            raise ValueError(
                f"请使用 create_mcp_client() 函数创建 {server_config.connection_type} 类型的客户端"
            )
