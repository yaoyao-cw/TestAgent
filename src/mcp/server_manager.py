#!/usr/bin/env python3
"""
MCP服务器管理器
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..exceptions import MCPIntegrationException
from .config import MCPConfig, load_mcp_config
from .client import create_mcp_client, MCPClient

logger = logging.getLogger(__name__)


class MCPServerManager:
    """MCP服务器管理器"""
    
    def __init__(self, config: Optional[MCPConfig] = None):
        self.config = config or load_mcp_config()
        self.clients: Dict[str, MCPClient] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        self.running = False
        
    async def start(self):
        """启动管理器"""
        if self.running:
            logger.warning("MCP服务器管理器已在运行")
            return
        
        logger.info("启动MCP服务器管理器")
        self.running = True
        
        # 连接所有启用的服务器
        await self.connect_all_servers()
        
        # 启动健康检查
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("MCP服务器管理器启动完成")
    
    async def stop(self):
        """停止管理器"""
        if not self.running:
            return
        
        logger.info("停止MCP服务器管理器")
        self.running = False
        
        # 停止健康检查
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        # 断开所有连接
        await self.disconnect_all_servers()
        
        # 取消所有连接任务
        for task in self.connection_tasks.values():
            task.cancel()
        
        if self.connection_tasks:
            await asyncio.gather(*self.connection_tasks.values(), return_exceptions=True)
        
        self.connection_tasks.clear()
        
        logger.info("MCP服务器管理器已停止")
    
    async def connect_all_servers(self):
        """连接所有启用的服务器"""
        enabled_servers = self.config.get_enabled_servers()
        
        if not enabled_servers:
            logger.info("没有启用的MCP服务器")
            return
        
        logger.info(f"连接 {len(enabled_servers)} 个MCP服务器")
        
        # 并发连接所有服务器
        connection_tasks = []
        for server_name, server_config in enabled_servers.items():
            task = asyncio.create_task(self._connect_server(server_name, server_config))
            connection_tasks.append(task)
            self.connection_tasks[server_name] = task
        
        # 等待所有连接完成
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # 统计连接结果
        successful_connections = 0
        for i, result in enumerate(results):
            server_name = list(enabled_servers.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"连接MCP服务器失败 {server_name}: {result}")
            elif result:
                successful_connections += 1
        
        logger.info(f"成功连接 {successful_connections}/{len(enabled_servers)} 个MCP服务器")
    
    async def _connect_server(self, server_name: str, server_config) -> bool:
        """连接单个服务器"""
        try:
            client = create_mcp_client(server_name, server_config)
            success = await client.connect()
            
            if success:
                self.clients[server_name] = client
                logger.info(f"MCP服务器连接成功: {server_name} ({server_config.connection_type})")
                return True
            else:
                logger.error(f"MCP服务器连接失败: {server_name}")
                return False
                
        except Exception as e:
            logger.error(f"连接MCP服务器异常 {server_name}: {e}")
            return False
    
    async def disconnect_all_servers(self):
        """断开所有服务器连接"""
        if not self.clients:
            return
        
        logger.info(f"断开 {len(self.clients)} 个MCP服务器连接")
        
        # 并发断开所有连接
        disconnect_tasks = []
        for client in self.clients.values():
            task = asyncio.create_task(client.disconnect())
            disconnect_tasks.append(task)
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        self.clients.clear()
        
        logger.info("所有MCP服务器连接已断开")
    
    async def reconnect_server(self, server_name: str) -> bool:
        """重连服务器"""
        try:
            # 断开现有连接
            if server_name in self.clients:
                await self.clients[server_name].disconnect()
                del self.clients[server_name]
            
            # 获取服务器配置
            server_config = self.config.get_server(server_name)
            if not server_config or server_config.disabled:
                logger.warning(f"服务器 {server_name} 未配置或已禁用")
                return False
            
            # 重新连接
            return await self._connect_server(server_name, server_config)
            
        except Exception as e:
            logger.error(f"重连MCP服务器失败 {server_name}: {e}")
            return False
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        try:
            if server_name not in self.clients:
                raise MCPIntegrationException(f"MCP服务器 {server_name} 未连接")
            
            client = self.clients[server_name]
            if not client.connected:
                # 尝试重连
                logger.info(f"MCP服务器 {server_name} 未连接，尝试重连")
                if not await self.reconnect_server(server_name):
                    raise MCPIntegrationException(f"MCP服务器 {server_name} 重连失败")
                client = self.clients[server_name]
            
            return await client.call_tool(tool_name, arguments)
            
        except Exception as e:
            logger.error(f"调用MCP工具失败 {server_name}.{tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "server_name": server_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def read_resource(self, server_name: str, resource_uri: str) -> Dict[str, Any]:
        """读取资源"""
        try:
            if server_name not in self.clients:
                raise MCPIntegrationException(f"MCP服务器 {server_name} 未连接")
            
            client = self.clients[server_name]
            if not client.connected:
                # 尝试重连
                logger.info(f"MCP服务器 {server_name} 未连接，尝试重连")
                if not await self.reconnect_server(server_name):
                    raise MCPIntegrationException(f"MCP服务器 {server_name} 重连失败")
                client = self.clients[server_name]
            
            return await client.read_resource(resource_uri)
            
        except Exception as e:
            logger.error(f"读取MCP资源失败 {server_name}.{resource_uri}: {e}")
            return {
                "uri": resource_uri,
                "server_name": server_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_available_tools(self) -> Dict[str, List[str]]:
        """获取所有可用工具"""
        tools = {}
        for server_name, client in self.clients.items():
            if client.connected:
                tools[server_name] = client.list_tools()
        return tools
    
    def get_available_resources(self) -> Dict[str, List[str]]:
        """获取所有可用资源"""
        resources = {}
        for server_name, client in self.clients.items():
            if client.connected:
                resources[server_name] = client.list_resources()
        return resources
    
    def get_tool_info(self, server_name: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        if server_name in self.clients:
            return self.clients[server_name].get_tool_info(tool_name)
        return None
    
    def get_resource_info(self, server_name: str, resource_uri: str) -> Optional[Dict[str, Any]]:
        """获取资源信息"""
        if server_name in self.clients:
            return self.clients[server_name].get_resource_info(resource_uri)
        return None
    
    def get_server_status(self, server_name: str) -> Optional[Dict[str, Any]]:
        """获取服务器状态"""
        if server_name in self.clients:
            return self.clients[server_name].get_status()
        return None
    
    def get_all_servers_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务器状态"""
        status = {}
        for server_name, client in self.clients.items():
            status[server_name] = client.get_status()
        return status
    
    def list_connected_servers(self) -> List[str]:
        """列出已连接的服务器"""
        return [
            server_name for server_name, client in self.clients.items()
            if client.connected
        ]
    
    def list_all_servers(self) -> List[str]:
        """列出所有配置的服务器"""
        return self.config.list_servers()
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                if not self.clients:
                    continue
                
                logger.debug("执行MCP服务器健康检查")
                
                # 并发检查所有客户端
                health_tasks = []
                for server_name, client in self.clients.items():
                    task = asyncio.create_task(self._check_client_health(server_name, client))
                    health_tasks.append(task)
                
                await asyncio.gather(*health_tasks, return_exceptions=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查异常: {e}")
    
    async def _check_client_health(self, server_name: str, client: MCPClient):
        """检查单个客户端健康状态"""
        try:
            is_healthy = await client.health_check()
            
            if not is_healthy:
                logger.warning(f"MCP服务器 {server_name} 健康检查失败，尝试重连")
                
                # 尝试重连
                server_config = self.config.get_server(server_name)
                if server_config and server_config.auto_restart:
                    await self.reconnect_server(server_name)
                
        except Exception as e:
            logger.error(f"检查MCP服务器健康状态异常 {server_name}: {e}")
    
    async def reload_config(self, config_path: str = None):
        """重新加载配置"""
        try:
            logger.info("重新加载MCP配置")
            
            # 加载新配置
            new_config = load_mcp_config(config_path)
            
            # 停止当前连接
            await self.disconnect_all_servers()
            
            # 更新配置
            self.config = new_config
            
            # 重新连接
            await self.connect_all_servers()
            
            logger.info("MCP配置重新加载完成")
            
        except Exception as e:
            logger.error(f"重新加载MCP配置失败: {e}")
            raise MCPIntegrationException(f"重新加载MCP配置失败: {e}")


# 全局管理器实例
_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """获取MCP管理器实例"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    return _mcp_manager


async def initialize_mcp_manager():
    """初始化MCP管理器"""
    manager = get_mcp_manager()
    await manager.start()
    return manager


async def shutdown_mcp_manager():
    """关闭MCP管理器"""
    global _mcp_manager
    if _mcp_manager:
        await _mcp_manager.stop()
        _mcp_manager = None