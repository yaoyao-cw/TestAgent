#!/usr/bin/env python3
"""
增强MCP服务器管理器
集成增强客户端，提供更好的错误处理和监控
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from .server_manager import MCPServerManager
from .enhanced_client import EnhancedMCPClient, RetryConfig, ToolCallResult
from .config import MCPConfig, load_mcp_config
from ..exceptions import MCPIntegrationException

logger = logging.getLogger(__name__)


@dataclass
class ServerHealthStatus:
    """服务器健康状态"""
    server_name: str
    is_healthy: bool
    last_check_time: datetime
    consecutive_failures: int
    last_error: Optional[str] = None
    response_time: float = 0.0


class EnhancedMCPServerManager(MCPServerManager):
    """增强MCP服务器管理器
    
    在原有服务器管理器基础上添加：
    1. 使用增强客户端
    2. 更好的错误处理和重试机制
    3. 服务器健康监控
    4. 性能统计和分析
    5. 自动故障转移
    """
    
    def __init__(self, config: Optional[MCPConfig] = None):
        """初始化增强服务器管理器
        
        Args:
            config: MCP配置
        """
        # 不调用父类初始化，重新实现
        self.config = config or load_mcp_config()
        self.clients: Dict[str, EnhancedMCPClient] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        self.running = False
        
        # 健康状态监控
        self.health_status: Dict[str, ServerHealthStatus] = {}
        self.health_check_interval = 30  # 健康检查间隔（秒）
        
        # 性能统计
        self.global_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_servers": 0,
            "healthy_servers": 0,
            "average_response_time": 0.0,
            "start_time": datetime.now()
        }
        
        # 故障转移配置
        self.failover_enabled = True
        self.preferred_servers: Dict[str, List[str]] = {}  # 工具 -> 服务器优先级列表
        
        # 全局钩子
        self.global_pre_call_hooks: List[Callable] = []
        self.global_post_call_hooks: List[Callable] = []
        self.global_error_hooks: List[Callable] = []
        
        logger.info("增强MCP服务器管理器初始化完成")
    
    async def start(self):
        """启动管理器"""
        if self.running:
            logger.warning("增强MCP服务器管理器已在运行")
            return
        
        logger.info("启动增强MCP服务器管理器")
        self.running = True
        self.global_stats["start_time"] = datetime.now()
        
        # 连接所有启用的服务器
        await self.connect_all_servers()
        
        # 启动健康检查
        self.health_check_task = asyncio.create_task(self._enhanced_health_check_loop())
        
        logger.info("增强MCP服务器管理器启动完成")
    
    async def connect_all_servers(self):
        """连接所有启用的服务器"""
        enabled_servers = self.config.get_enabled_servers()
        
        if not enabled_servers:
            logger.info("没有启用的MCP服务器")
            return
        
        logger.info(f"连接 {len(enabled_servers)} 个MCP服务器")
        self.global_stats["total_servers"] = len(enabled_servers)
        
        # 并发连接所有服务器
        connection_tasks = []
        for server_name, server_config in enabled_servers.items():
            task = asyncio.create_task(self._connect_enhanced_server(server_name, server_config))
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
                self._update_health_status(server_name, False, str(result))
            elif result:
                successful_connections += 1
                self._update_health_status(server_name, True)
        
        self.global_stats["healthy_servers"] = successful_connections
        logger.info(f"成功连接 {successful_connections}/{len(enabled_servers)} 个MCP服务器")
    
    async def _connect_enhanced_server(self, server_name: str, server_config) -> bool:
        """连接单个增强服务器
        
        Args:
            server_name: 服务器名称
            server_config: 服务器配置
            
        Returns:
            是否连接成功
        """
        try:
            # 创建重试配置
            retry_config = RetryConfig(
                max_attempts=server_config.retry_attempts if hasattr(server_config, 'retry_attempts') else 3,
                base_delay=server_config.retry_delay if hasattr(server_config, 'retry_delay') else 1.0
            )
            
            # 创建增强客户端
            client = EnhancedMCPClient(server_name, server_config, retry_config)
            
            # 添加全局钩子
            for hook in self.global_pre_call_hooks:
                client.add_pre_call_hook(hook)
            for hook in self.global_post_call_hooks:
                client.add_post_call_hook(hook)
            for hook in self.global_error_hooks:
                client.add_error_hook(hook)
            
            # 连接
            success = await client.connect()
            
            if success:
                self.clients[server_name] = client
                logger.info(f"增强MCP服务器连接成功: {server_name} ({server_config.connection_type})")
                return True
            else:
                logger.error(f"增强MCP服务器连接失败: {server_name}")
                return False
                
        except Exception as e:
            logger.error(f"连接增强MCP服务器异常 {server_name}: {e}")
            return False
    
    async def call_tool_with_failover(self, 
                                    tool_name: str, 
                                    arguments: Dict[str, Any],
                                    preferred_server: Optional[str] = None) -> ToolCallResult:
        """带故障转移的工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            preferred_server: 首选服务器
            
        Returns:
            标准化工具调用结果
        """
        start_time = datetime.now()
        
        # 更新全局统计
        self.global_stats["total_calls"] += 1
        
        # 确定服务器调用顺序
        server_order = self._get_server_order_for_tool(tool_name, preferred_server)
        
        if not server_order:
            return ToolCallResult(
                success=False,
                tool_name=tool_name,
                server_name="none",
                error="没有可用的服务器",
                error_type="no_available_servers",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
        
        last_result = None
        
        # 按顺序尝试服务器
        for server_name in server_order:
            if server_name not in self.clients:
                continue
            
            client = self.clients[server_name]
            
            # 检查服务器健康状态
            if not self._is_server_healthy(server_name):
                logger.debug(f"跳过不健康的服务器: {server_name}")
                continue
            
            try:
                logger.info(f"尝试在服务器 {server_name} 上调用工具: {tool_name}")
                result = await client.call_tool_with_retry(tool_name, arguments)
                
                if result.success:
                    # 成功调用
                    self.global_stats["successful_calls"] += 1
                    self._update_global_response_time((datetime.now() - start_time).total_seconds())
                    
                    logger.info(f"工具调用成功: {tool_name} on {server_name}")
                    return result
                else:
                    # 工具调用失败，但服务器响应正常
                    last_result = result
                    logger.warning(f"工具调用失败: {tool_name} on {server_name}: {result.error}")
                    
                    # 如果是工具不存在的错误，不需要尝试其他服务器
                    if "不存在" in result.error or "not found" in result.error.lower():
                        break
                    
            except Exception as e:
                logger.error(f"服务器 {server_name} 调用异常: {e}")
                self._update_health_status(server_name, False, str(e))
                continue
        
        # 所有服务器都失败了
        self.global_stats["failed_calls"] += 1
        
        if last_result:
            return last_result
        else:
            return ToolCallResult(
                success=False,
                tool_name=tool_name,
                server_name="multiple",
                error="所有服务器都无法处理该工具调用",
                error_type="all_servers_failed",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def _get_server_order_for_tool(self, 
                                 tool_name: str, 
                                 preferred_server: Optional[str] = None) -> List[str]:
        """获取工具调用的服务器顺序
        
        Args:
            tool_name: 工具名称
            preferred_server: 首选服务器
            
        Returns:
            服务器名称列表（按优先级排序）
        """
        # 获取有该工具的服务器
        available_servers = []
        for server_name, client in self.clients.items():
            if client.connected and tool_name in client.list_tools():
                available_servers.append(server_name)
        
        if not available_servers:
            return []
        
        # 排序逻辑
        server_order = []
        
        # 1. 首选服务器（如果指定且可用）
        if preferred_server and preferred_server in available_servers:
            server_order.append(preferred_server)
            available_servers.remove(preferred_server)
        
        # 2. 配置的优先级服务器
        if tool_name in self.preferred_servers:
            for server_name in self.preferred_servers[tool_name]:
                if server_name in available_servers:
                    server_order.append(server_name)
                    available_servers.remove(server_name)
        
        # 3. 按健康状态和性能排序剩余服务器
        remaining_servers = sorted(
            available_servers,
            key=lambda s: (
                self._is_server_healthy(s),  # 健康的服务器优先
                -self.health_status.get(s, ServerHealthStatus(s, False, datetime.now(), 0)).response_time  # 响应时间短的优先
            ),
            reverse=True
        )
        
        server_order.extend(remaining_servers)
        
        return server_order
    
    def _is_server_healthy(self, server_name: str) -> bool:
        """检查服务器是否健康
        
        Args:
            server_name: 服务器名称
            
        Returns:
            是否健康
        """
        if server_name not in self.health_status:
            return True  # 默认认为健康
        
        status = self.health_status[server_name]
        
        # 如果连续失败次数过多，认为不健康
        if status.consecutive_failures >= 3:
            return False
        
        # 如果最近检查失败，认为不健康
        if not status.is_healthy:
            return False
        
        return True
    
    def _update_health_status(self, 
                            server_name: str, 
                            is_healthy: bool, 
                            error_message: Optional[str] = None,
                            response_time: float = 0.0):
        """更新服务器健康状态
        
        Args:
            server_name: 服务器名称
            is_healthy: 是否健康
            error_message: 错误信息
            response_time: 响应时间
        """
        if server_name not in self.health_status:
            self.health_status[server_name] = ServerHealthStatus(
                server_name=server_name,
                is_healthy=is_healthy,
                last_check_time=datetime.now(),
                consecutive_failures=0 if is_healthy else 1,
                last_error=error_message,
                response_time=response_time
            )
        else:
            status = self.health_status[server_name]
            status.is_healthy = is_healthy
            status.last_check_time = datetime.now()
            status.last_error = error_message
            status.response_time = response_time
            
            if is_healthy:
                status.consecutive_failures = 0
            else:
                status.consecutive_failures += 1
    
    def _update_global_response_time(self, response_time: float):
        """更新全局平均响应时间
        
        Args:
            response_time: 响应时间
        """
        if self.global_stats["successful_calls"] > 0:
            total_time = (self.global_stats["average_response_time"] * 
                         (self.global_stats["successful_calls"] - 1) + response_time)
            self.global_stats["average_response_time"] = total_time / self.global_stats["successful_calls"]
        else:
            self.global_stats["average_response_time"] = response_time
    
    async def _enhanced_health_check_loop(self):
        """增强健康检查循环"""
        while self.running:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                if not self.clients:
                    continue
                
                logger.debug("执行增强MCP服务器健康检查")
                
                # 并发检查所有客户端
                health_tasks = []
                for server_name, client in self.clients.items():
                    task = asyncio.create_task(self._enhanced_health_check(server_name, client))
                    health_tasks.append(task)
                
                await asyncio.gather(*health_tasks, return_exceptions=True)
                
                # 更新全局健康统计
                healthy_count = sum(1 for status in self.health_status.values() if status.is_healthy)
                self.global_stats["healthy_servers"] = healthy_count
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"增强健康检查异常: {e}")
    
    async def _enhanced_health_check(self, server_name: str, client: EnhancedMCPClient):
        """增强健康检查单个客户端
        
        Args:
            server_name: 服务器名称
            client: 增强客户端
        """
        try:
            start_time = datetime.now()
            is_healthy = await client.health_check()
            response_time = (datetime.now() - start_time).total_seconds()
            
            self._update_health_status(server_name, is_healthy, None, response_time)
            
            if not is_healthy:
                logger.warning(f"MCP服务器 {server_name} 健康检查失败")
                
                # 尝试重连
                server_config = self.config.get_server(server_name)
                if server_config and server_config.auto_restart:
                    logger.info(f"尝试重连MCP服务器: {server_name}")
                    await self.reconnect_server(server_name)
                
        except Exception as e:
            logger.error(f"检查MCP服务器健康状态异常 {server_name}: {e}")
            self._update_health_status(server_name, False, str(e))
    
    def add_global_pre_call_hook(self, hook: Callable):
        """添加全局前置钩子
        
        Args:
            hook: 钩子函数
        """
        self.global_pre_call_hooks.append(hook)
        
        # 为现有客户端添加钩子
        for client in self.clients.values():
            client.add_pre_call_hook(hook)
    
    def add_global_post_call_hook(self, hook: Callable):
        """添加全局后置钩子
        
        Args:
            hook: 钩子函数
        """
        self.global_post_call_hooks.append(hook)
        
        # 为现有客户端添加钩子
        for client in self.clients.values():
            client.add_post_call_hook(hook)
    
    def add_global_error_hook(self, hook: Callable):
        """添加全局错误钩子
        
        Args:
            hook: 钩子函数
        """
        self.global_error_hooks.append(hook)
        
        # 为现有客户端添加钩子
        for client in self.clients.values():
            client.add_error_hook(hook)
    
    def set_tool_server_preference(self, tool_name: str, server_order: List[str]):
        """设置工具的服务器优先级
        
        Args:
            tool_name: 工具名称
            server_order: 服务器优先级列表
        """
        self.preferred_servers[tool_name] = server_order
        logger.info(f"设置工具 {tool_name} 的服务器优先级: {server_order}")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """获取综合状态报告
        
        Returns:
            综合状态信息
        """
        # 基础状态
        status = {
            "running": self.running,
            "global_stats": self.global_stats.copy(),
            "health_summary": {
                "total_servers": len(self.clients),
                "healthy_servers": sum(1 for s in self.health_status.values() if s.is_healthy),
                "unhealthy_servers": sum(1 for s in self.health_status.values() if not s.is_healthy),
                "average_response_time": self.global_stats["average_response_time"]
            },
            "server_details": {},
            "tool_distribution": {},
            "failure_analysis": {}
        }
        
        # 格式化时间
        if "start_time" in status["global_stats"]:
            status["global_stats"]["start_time"] = status["global_stats"]["start_time"].isoformat()
            status["global_stats"]["uptime_seconds"] = (datetime.now() - self.global_stats["start_time"]).total_seconds()
        
        # 服务器详细信息
        for server_name, client in self.clients.items():
            client_status = client.get_status()
            health_status = self.health_status.get(server_name)
            
            status["server_details"][server_name] = {
                "client_status": client_status,
                "health_status": {
                    "is_healthy": health_status.is_healthy if health_status else True,
                    "consecutive_failures": health_status.consecutive_failures if health_status else 0,
                    "last_check_time": health_status.last_check_time.isoformat() if health_status else None,
                    "last_error": health_status.last_error if health_status else None,
                    "response_time": health_status.response_time if health_status else 0.0
                },
                "performance_stats": client.get_performance_stats(),
                "failure_analysis": client.get_failure_analysis()
            }
        
        # 工具分布统计
        tool_servers = {}
        for server_name, client in self.clients.items():
            if client.connected:
                for tool_name in client.list_tools():
                    if tool_name not in tool_servers:
                        tool_servers[tool_name] = []
                    tool_servers[tool_name].append(server_name)
        
        status["tool_distribution"] = {
            "total_unique_tools": len(tool_servers),
            "tools_per_server": {
                server_name: len(client.list_tools()) 
                for server_name, client in self.clients.items() 
                if client.connected
            },
            "tool_server_mapping": tool_servers,
            "redundant_tools": {
                tool_name: servers 
                for tool_name, servers in tool_servers.items() 
                if len(servers) > 1
            }
        }
        
        return status
    
    def export_configuration(self) -> Dict[str, Any]:
        """导出配置
        
        Returns:
            配置信息
        """
        return {
            "mcp_config": self.config.to_dict() if hasattr(self.config, 'to_dict') else {},
            "preferred_servers": self.preferred_servers.copy(),
            "health_check_interval": self.health_check_interval,
            "failover_enabled": self.failover_enabled,
            "global_hooks_count": {
                "pre_call": len(self.global_pre_call_hooks),
                "post_call": len(self.global_post_call_hooks),
                "error": len(self.global_error_hooks)
            }
        }
    
    # 重写父类方法以使用增强功能
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具（重写父类方法）"""
        if server_name in self.clients:
            # 使用指定服务器
            client = self.clients[server_name]
            result = await client.call_tool_with_retry(tool_name, arguments)
            return result.__dict__
        else:
            # 使用故障转移
            result = await self.call_tool_with_failover(tool_name, arguments, server_name)
            return result.__dict__


# 全局增强管理器实例
_enhanced_mcp_manager: Optional[EnhancedMCPServerManager] = None


def get_enhanced_mcp_manager() -> EnhancedMCPServerManager:
    """获取增强MCP管理器实例
    
    Returns:
        增强MCP管理器实例
    """
    global _enhanced_mcp_manager
    if _enhanced_mcp_manager is None:
        _enhanced_mcp_manager = EnhancedMCPServerManager()
    return _enhanced_mcp_manager


async def initialize_enhanced_mcp_manager():
    """初始化增强MCP管理器"""
    manager = get_enhanced_mcp_manager()
    await manager.start()
    return manager


async def shutdown_enhanced_mcp_manager():
    """关闭增强MCP管理器"""
    global _enhanced_mcp_manager
    if _enhanced_mcp_manager:
        await _enhanced_mcp_manager.stop()
        _enhanced_mcp_manager = None


# 便捷函数
async def call_mcp_tool_with_failover(tool_name: str, 
                                    arguments: Dict[str, Any],
                                    preferred_server: Optional[str] = None) -> ToolCallResult:
    """带故障转移的MCP工具调用便捷函数
    
    Args:
        tool_name: 工具名称
        arguments: 工具参数
        preferred_server: 首选服务器
        
    Returns:
        工具调用结果
    """
    manager = get_enhanced_mcp_manager()
    return await manager.call_tool_with_failover(tool_name, arguments, preferred_server)


def get_mcp_comprehensive_status() -> Dict[str, Any]:
    """获取MCP综合状态的便捷函数
    
    Returns:
        综合状态信息
    """
    manager = get_enhanced_mcp_manager()
    return manager.get_comprehensive_status()