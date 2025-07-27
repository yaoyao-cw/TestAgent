#!/usr/bin/env python3
"""
增强MCP客户端
实现工具调用失败处理、重试机制和标准化结果处理
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..exceptions import MCPIntegrationException
from .client import MCPClient, create_mcp_client
from .config import MCPServerConfig

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """重试策略"""

    NONE = "none"  # 不重试
    FIXED = "fixed"  # 固定间隔重试
    EXPONENTIAL = "exponential"  # 指数退避重试
    LINEAR = "linear"  # 线性增长重试


@dataclass
class RetryConfig:
    """重试配置"""

    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_attempts: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    backoff_factor: float = 2.0  # 退避因子
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class FailureRecord:
    """失败记录"""

    timestamp: datetime
    tool_name: str
    error_type: str
    error_message: str
    arguments: Dict[str, Any]
    attempt_count: int
    server_name: str


@dataclass
class ToolCallResult:
    """标准化工具调用结果"""

    success: bool
    tool_name: str
    server_name: str
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time: float = 0.0
    attempt_count: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedMCPClient:
    """增强MCP客户端

    在原有MCP客户端基础上添加：
    1. 智能重试机制
    2. 失败处理和恢复
    3. 标准化结果处理
    4. 性能监控和统计
    """

    def __init__(
        self,
        server_name: str,
        server_config: MCPServerConfig,
        retry_config: Optional[RetryConfig] = None,
    ):
        """初始化增强MCP客户端

        Args:
            server_name: 服务器名称
            server_config: 服务器配置
            retry_config: 重试配置
        """
        self.server_name = server_name
        self.server_config = server_config
        self.retry_config = retry_config or RetryConfig()

        # 创建底层客户端
        self.client: MCPClient = create_mcp_client(server_name, server_config)

        # 失败处理
        self.failure_records: List[FailureRecord] = []
        self.max_failure_records = 1000

        # 性能统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retry_calls": 0,
            "total_execution_time": 0.0,
            "average_execution_time": 0.0,
            "last_success_time": None,
            "last_failure_time": None,
            "consecutive_failures": 0,
            "max_consecutive_failures": 0,
        }

        # 断路器状态
        self.circuit_breaker_enabled = True
        self.circuit_breaker_threshold = 5  # 连续失败阈值
        self.circuit_breaker_timeout = 300  # 断路器超时（秒）
        self.circuit_breaker_open_time: Optional[datetime] = None

        # 工具调用钩子
        self.pre_call_hooks: List[Callable] = []
        self.post_call_hooks: List[Callable] = []
        self.error_hooks: List[Callable] = []

        logger.info(f"增强MCP客户端初始化完成: {server_name}")

    async def connect(self) -> bool:
        """连接到MCP服务器"""
        try:
            success = await self.client.connect()
            if success:
                self._reset_circuit_breaker()
            return success
        except Exception as e:
            await self._handle_connection_error(e)
            return False

    async def disconnect(self):
        """断开连接"""
        await self.client.disconnect()

    async def call_tool_with_retry(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        custom_retry_config: Optional[RetryConfig] = None,
    ) -> ToolCallResult:
        """带重试机制的工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            custom_retry_config: 自定义重试配置

        Returns:
            标准化工具调用结果
        """
        start_time = time.time()
        retry_config = custom_retry_config or self.retry_config

        # 检查断路器状态
        if not self._check_circuit_breaker():
            return ToolCallResult(
                success=False,
                tool_name=tool_name,
                server_name=self.server_name,
                error="断路器开启，服务暂时不可用",
                error_type="circuit_breaker_open",
                execution_time=time.time() - start_time,
            )

        # 更新统计
        self.stats["total_calls"] += 1

        # 执行前置钩子
        await self._execute_pre_call_hooks(tool_name, arguments)

        last_error = None
        attempt_count = 0

        for attempt in range(retry_config.max_attempts):
            attempt_count += 1

            try:
                # 如果不是第一次尝试，等待重试延迟
                if attempt > 0:
                    delay = self._calculate_retry_delay(attempt, retry_config)
                    logger.info(
                        f"工具调用重试 {attempt + 1}/{retry_config.max_attempts}，延迟 {delay:.2f}s: {tool_name}"
                    )
                    await asyncio.sleep(delay)
                    self.stats["retry_calls"] += 1

                # 调用工具
                result = await self.client.call_tool(tool_name, arguments)

                # 处理成功结果
                if result.get("success", False):
                    execution_time = time.time() - start_time

                    # 更新统计
                    self.stats["successful_calls"] += 1
                    self.stats["total_execution_time"] += execution_time
                    self.stats["average_execution_time"] = (
                        self.stats["total_execution_time"]
                        / self.stats["successful_calls"]
                    )
                    self.stats["last_success_time"] = datetime.now()
                    self.stats["consecutive_failures"] = 0

                    # 重置断路器
                    self._reset_circuit_breaker()

                    # 创建标准化结果
                    tool_result = ToolCallResult(
                        success=True,
                        tool_name=tool_name,
                        server_name=self.server_name,
                        result=result.get("result"),
                        execution_time=execution_time,
                        attempt_count=attempt_count,
                        metadata={
                            "original_result": result,
                            "retry_strategy": retry_config.strategy.value,
                        },
                    )

                    # 执行后置钩子
                    await self._execute_post_call_hooks(tool_result)

                    return tool_result

                else:
                    # 工具返回失败结果
                    error_msg = result.get("error", "工具调用返回失败")
                    last_error = MCPIntegrationException(error_msg)

            except Exception as e:
                last_error = e
                logger.warning(f"工具调用尝试 {attempt + 1} 失败: {tool_name}: {e}")

        # 所有重试都失败了
        execution_time = time.time() - start_time

        # 更新失败统计
        self.stats["failed_calls"] += 1
        self.stats["last_failure_time"] = datetime.now()
        self.stats["consecutive_failures"] += 1
        self.stats["max_consecutive_failures"] = max(
            self.stats["max_consecutive_failures"], self.stats["consecutive_failures"]
        )

        # 记录失败
        failure_record = FailureRecord(
            timestamp=datetime.now(),
            tool_name=tool_name,
            error_type=type(last_error).__name__,
            error_message=str(last_error),
            arguments=arguments,
            attempt_count=attempt_count,
            server_name=self.server_name,
        )
        self._record_failure(failure_record)

        # 检查是否需要开启断路器
        self._check_and_open_circuit_breaker()

        # 创建失败结果
        tool_result = ToolCallResult(
            success=False,
            tool_name=tool_name,
            server_name=self.server_name,
            error=str(last_error),
            error_type=type(last_error).__name__,
            execution_time=execution_time,
            attempt_count=attempt_count,
            metadata={
                "retry_strategy": retry_config.strategy.value,
                "max_attempts": retry_config.max_attempts,
            },
        )

        # 执行错误钩子
        await self._execute_error_hooks(tool_result, last_error)

        return tool_result

    def _calculate_retry_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟

        Args:
            attempt: 当前尝试次数（从0开始）
            config: 重试配置

        Returns:
            延迟时间（秒）
        """
        if config.strategy == RetryStrategy.NONE:
            return 0.0

        elif config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay

        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * (attempt + 1)

        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_factor**attempt)

        else:
            delay = config.base_delay

        # 限制最大延迟
        delay = min(delay, config.max_delay)

        # 添加随机抖动
        if config.jitter:
            import random

            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor

        return delay

    def _check_circuit_breaker(self) -> bool:
        """检查断路器状态

        Returns:
            是否可以执行调用
        """
        if not self.circuit_breaker_enabled:
            return True

        if self.circuit_breaker_open_time is None:
            return True

        # 检查断路器是否应该关闭
        if datetime.now() - self.circuit_breaker_open_time > timedelta(
            seconds=self.circuit_breaker_timeout
        ):
            logger.info(f"断路器超时，重新开启服务: {self.server_name}")
            self._reset_circuit_breaker()
            return True

        return False

    def _check_and_open_circuit_breaker(self):
        """检查并开启断路器"""
        if (
            self.circuit_breaker_enabled
            and self.stats["consecutive_failures"] >= self.circuit_breaker_threshold
        ):

            self.circuit_breaker_open_time = datetime.now()
            logger.warning(
                f"断路器开启，连续失败 {self.stats['consecutive_failures']} 次: {self.server_name}"
            )

    def _reset_circuit_breaker(self):
        """重置断路器"""
        if self.circuit_breaker_open_time is not None:
            logger.info(f"断路器重置: {self.server_name}")
        self.circuit_breaker_open_time = None

    def _record_failure(self, failure_record: FailureRecord):
        """记录失败信息

        Args:
            failure_record: 失败记录
        """
        self.failure_records.append(failure_record)

        # 限制记录数量
        if len(self.failure_records) > self.max_failure_records:
            self.failure_records = self.failure_records[-self.max_failure_records :]

    async def _handle_connection_error(self, error: Exception):
        """处理连接错误

        Args:
            error: 连接错误
        """
        logger.error(f"MCP服务器连接错误 {self.server_name}: {error}")

        # 记录连接失败
        failure_record = FailureRecord(
            timestamp=datetime.now(),
            tool_name="connection",
            error_type=type(error).__name__,
            error_message=str(error),
            arguments={},
            attempt_count=1,
            server_name=self.server_name,
        )
        self._record_failure(failure_record)

    async def _execute_pre_call_hooks(self, tool_name: str, arguments: Dict[str, Any]):
        """执行前置钩子

        Args:
            tool_name: 工具名称
            arguments: 工具参数
        """
        for hook in self.pre_call_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(self.server_name, tool_name, arguments)
                else:
                    hook(self.server_name, tool_name, arguments)
            except Exception as e:
                logger.warning(f"前置钩子执行失败: {e}")

    async def _execute_post_call_hooks(self, result: ToolCallResult):
        """执行后置钩子

        Args:
            result: 工具调用结果
        """
        for hook in self.post_call_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(result)
                else:
                    hook(result)
            except Exception as e:
                logger.warning(f"后置钩子执行失败: {e}")

    async def _execute_error_hooks(self, result: ToolCallResult, error: Exception):
        """执行错误钩子

        Args:
            result: 工具调用结果
            error: 错误信息
        """
        for hook in self.error_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(result, error)
                else:
                    hook(result, error)
            except Exception as e:
                logger.warning(f"错误钩子执行失败: {e}")

    def add_pre_call_hook(self, hook: Callable):
        """添加前置钩子

        Args:
            hook: 钩子函数
        """
        self.pre_call_hooks.append(hook)

    def add_post_call_hook(self, hook: Callable):
        """添加后置钩子

        Args:
            hook: 钩子函数
        """
        self.post_call_hooks.append(hook)

    def add_error_hook(self, hook: Callable):
        """添加错误钩子

        Args:
            hook: 钩子函数
        """
        self.error_hooks.append(hook)

    def get_failure_analysis(self) -> Dict[str, Any]:
        """获取失败分析

        Returns:
            失败分析报告
        """
        if not self.failure_records:
            return {"message": "暂无失败记录"}

        # 按错误类型统计
        error_type_stats = {}
        tool_stats = {}

        for record in self.failure_records:
            # 错误类型统计
            if record.error_type not in error_type_stats:
                error_type_stats[record.error_type] = 0
            error_type_stats[record.error_type] += 1

            # 工具统计
            if record.tool_name not in tool_stats:
                tool_stats[record.tool_name] = {"total": 0, "errors": {}}
            tool_stats[record.tool_name]["total"] += 1

            if record.error_type not in tool_stats[record.tool_name]["errors"]:
                tool_stats[record.tool_name]["errors"][record.error_type] = 0
            tool_stats[record.tool_name]["errors"][record.error_type] += 1

        # 最近失败
        recent_failures = sorted(
            self.failure_records, key=lambda x: x.timestamp, reverse=True
        )[:10]

        return {
            "total_failures": len(self.failure_records),
            "error_type_distribution": error_type_stats,
            "tool_failure_stats": tool_stats,
            "recent_failures": [
                {
                    "timestamp": record.timestamp.isoformat(),
                    "tool_name": record.tool_name,
                    "error_type": record.error_type,
                    "error_message": record.error_message,
                    "attempt_count": record.attempt_count,
                }
                for record in recent_failures
            ],
            "circuit_breaker_status": {
                "enabled": self.circuit_breaker_enabled,
                "open": self.circuit_breaker_open_time is not None,
                "open_time": (
                    self.circuit_breaker_open_time.isoformat()
                    if self.circuit_breaker_open_time
                    else None
                ),
                "consecutive_failures": self.stats["consecutive_failures"],
                "threshold": self.circuit_breaker_threshold,
            },
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计

        Returns:
            性能统计信息
        """
        stats = self.stats.copy()

        # 计算成功率
        if stats["total_calls"] > 0:
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"]
            stats["failure_rate"] = stats["failed_calls"] / stats["total_calls"]
            stats["retry_rate"] = stats["retry_calls"] / stats["total_calls"]
        else:
            stats["success_rate"] = 0.0
            stats["failure_rate"] = 0.0
            stats["retry_rate"] = 0.0

        # 格式化时间
        if stats["last_success_time"]:
            stats["last_success_time"] = stats["last_success_time"].isoformat()
        if stats["last_failure_time"]:
            stats["last_failure_time"] = stats["last_failure_time"].isoformat()

        return stats

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retry_calls": 0,
            "total_execution_time": 0.0,
            "average_execution_time": 0.0,
            "last_success_time": None,
            "last_failure_time": None,
            "consecutive_failures": 0,
            "max_consecutive_failures": 0,
        }
        self.failure_records.clear()
        self._reset_circuit_breaker()

        logger.info(f"重置性能统计: {self.server_name}")

    # 代理底层客户端的其他方法
    async def read_resource(self, resource_uri: str) -> Dict[str, Any]:
        """读取资源"""
        return await self.client.read_resource(resource_uri)

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        return self.client.get_tool_info(tool_name)

    def get_resource_info(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """获取资源信息"""
        return self.client.get_resource_info(resource_uri)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return self.client.list_tools()

    def list_resources(self) -> List[str]:
        """列出所有资源"""
        return self.client.list_resources()

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        base_status = self.client.get_status()
        base_status.update(
            {
                "enhanced_features": {
                    "retry_enabled": True,
                    "circuit_breaker_enabled": self.circuit_breaker_enabled,
                    "circuit_breaker_open": self.circuit_breaker_open_time is not None,
                    "failure_records_count": len(self.failure_records),
                },
                "performance_stats": self.get_performance_stats(),
            }
        )
        return base_status

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.error(f"健康检查失败 {self.server_name}: {e}")
            return False

    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self.client.connected
