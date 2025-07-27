#!/usr/bin/env python3
"""
MCP SSE客户端实现
支持通过Server-Sent Events连接到MCP服务器
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
import aiohttp
from aiohttp_sse_client import client as sse_client

from mcp import ClientSession
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse

from ..exceptions import MCPIntegrationException
from .config import MCPServerConfig

logger = logging.getLogger(__name__)


class SSETransport:
    """SSE传输层实现"""

    def __init__(self, url: str, headers: Dict[str, str] = None, timeout: int = 30):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.sse_client = None
        self.connected = False
        self._read_queue = asyncio.Queue()
        self._write_queue = asyncio.Queue()
        self._read_task: Optional[asyncio.Task] = None
        self._write_task: Optional[asyncio.Task] = None

    async def connect(self):
        """建立SSE连接"""
        try:
            logger.info(f"连接到SSE服务器: {self.url}")

            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

            # 建立SSE连接
            self.sse_client = sse_client.EventSource(
                self.url, session=self.session, headers=self.headers
            )

            await self.sse_client.connect()

            # 启动读写任务
            self._read_task = asyncio.create_task(self._read_loop())
            self._write_task = asyncio.create_task(self._write_loop())

            self.connected = True
            logger.info(f"SSE连接建立成功: {self.url}")

        except Exception as e:
            logger.error(f"SSE连接失败: {e}")
            await self.disconnect()
            raise MCPIntegrationException(f"SSE连接失败: {e}")

    async def disconnect(self):
        """断开SSE连接"""
        try:
            self.connected = False

            # 取消任务
            if self._read_task:
                self._read_task.cancel()
                try:
                    await self._read_task
                except asyncio.CancelledError:
                    pass

            if self._write_task:
                self._write_task.cancel()
                try:
                    await self._write_task
                except asyncio.CancelledError:
                    pass

            # 关闭SSE客户端
            if self.sse_client:
                await self.sse_client.close()
                self.sse_client = None

            # 关闭HTTP会话
            if self.session:
                await self.session.close()
                self.session = None

            logger.info("SSE连接已断开")

        except Exception as e:
            logger.error(f"断开SSE连接失败: {e}")

    async def _read_loop(self):
        """读取循环"""
        try:
            async for event in self.sse_client:
                if event.type == "message":
                    try:
                        # 解析JSON-RPC消息
                        message_data = json.loads(event.data)
                        await self._read_queue.put(message_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析SSE消息失败: {e}")
                elif event.type == "error":
                    logger.error(f"SSE错误事件: {event.data}")
                    break

        except Exception as e:
            logger.error(f"SSE读取循环异常: {e}")
            self.connected = False

    async def _write_loop(self):
        """写入循环"""
        try:
            while self.connected:
                try:
                    # 从写入队列获取消息
                    message = await asyncio.wait_for(
                        self._write_queue.get(), timeout=1.0
                    )

                    # 通过HTTP POST发送消息
                    if self.session:
                        async with self.session.post(
                            self.url, json=message, headers=self.headers
                        ) as response:
                            if response.status != 200:
                                logger.error(f"发送消息失败: HTTP {response.status}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"发送消息异常: {e}")

        except Exception as e:
            logger.error(f"SSE写入循环异常: {e}")

    async def read(self) -> Dict[str, Any]:
        """读取消息"""
        if not self.connected:
            raise MCPIntegrationException("SSE连接未建立")

        try:
            message = await asyncio.wait_for(
                self._read_queue.get(), timeout=self.timeout
            )
            return message
        except asyncio.TimeoutError:
            raise MCPIntegrationException("读取消息超时")

    async def write(self, message: Dict[str, Any]):
        """写入消息"""
        if not self.connected:
            raise MCPIntegrationException("SSE连接未建立")

        await self._write_queue.put(message)


class MCPSSEClient:
    """MCP SSE客户端"""

    def __init__(self, server_name: str, server_config: MCPServerConfig):
        self.server_name = server_name
        self.server_config = server_config
        self.transport: Optional[SSETransport] = None
        self.session: Optional[ClientSession] = None
        self.connected = False
        self.tools: Dict[str, Any] = {}
        self.resources: Dict[str, Any] = {}
        self.connection_time: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None

        if server_config.connection_type != "sse":
            raise ValueError("服务器配置必须是SSE类型")

    async def connect(self) -> bool:
        """连接到MCP服务器"""
        try:
            logger.info(f"连接到MCP SSE服务器: {self.server_name}")

            # 创建SSE传输层
            self.transport = SSETransport(
                url=self.server_config.url,
                headers=self.server_config.headers,
                timeout=self.server_config.timeout,
            )

            # 建立连接
            await self.transport.connect()

            # 创建MCP会话
            self.session = ClientSession(self.transport.read, self.transport.write)

            # 初始化会话
            await self.session.initialize()

            # 获取工具和资源列表
            await self._load_tools()
            await self._load_resources()

            self.connected = True
            self.connection_time = datetime.now()
            self.last_activity = datetime.now()

            logger.info(f"成功连接到MCP SSE服务器: {self.server_name}")
            logger.info(f"可用工具: {list(self.tools.keys())}")
            logger.info(f"可用资源: {list(self.resources.keys())}")

            return True

        except Exception as e:
            logger.error(f"连接MCP SSE服务器失败 {self.server_name}: {e}")
            self.connected = False
            await self.disconnect()
            raise MCPIntegrationException(
                f"连接MCP SSE服务器失败 {self.server_name}: {e}"
            )

    async def disconnect(self):
        """断开连接"""
        try:
            if self.session:
                await self.session.close()
                self.session = None

            if self.transport:
                await self.transport.disconnect()
                self.transport = None

            self.connected = False
            self.connection_time = None
            logger.info(f"已断开MCP SSE服务器连接: {self.server_name}")

        except Exception as e:
            logger.error(f"断开MCP SSE服务器连接失败 {self.server_name}: {e}")

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
                raise MCPIntegrationException(
                    f"MCP SSE服务器 {self.server_name} 未连接"
                )

            if tool_name not in self.tools:
                raise MCPIntegrationException(f"工具 {tool_name} 不存在")

            logger.info(f"调用MCP SSE工具: {tool_name} (参数: {arguments})")

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

            logger.info(f"MCP SSE工具调用成功: {tool_name}")
            return tool_result

        except Exception as e:
            logger.error(f"调用MCP SSE工具失败 {tool_name}: {e}")
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
                raise MCPIntegrationException(
                    f"MCP SSE服务器 {self.server_name} 未连接"
                )

            if resource_uri not in self.resources:
                raise MCPIntegrationException(f"资源 {resource_uri} 不存在")

            logger.info(f"读取MCP SSE资源: {resource_uri}")

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

            logger.info(f"MCP SSE资源读取成功: {resource_uri}")
            return resource_result

        except Exception as e:
            logger.error(f"读取MCP SSE资源失败 {resource_uri}: {e}")
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
            "connection_type": "sse",
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
            "url": self.server_config.url,
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
            logger.error(f"MCP SSE服务器健康检查失败 {self.server_name}: {e}")
            self.connected = False
            return False
