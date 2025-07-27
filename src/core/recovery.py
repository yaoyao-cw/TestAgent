#!/usr/bin/env python3
"""
错误恢复和降级策略

提供系统错误恢复、服务降级和故障转移机制
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from .exceptions import (
    ConfigurationError,
    LLMError,
    MCPError,
    NetworkError,
    RAGError,
    ResourceError,
    TestAgentException,
    TimeoutError,
)

logger = logging.getLogger("recovery")


class ServiceLevel(Enum):
    """服务级别"""

    FULL = "full"  # 完整服务
    DEGRADED = "degraded"  # 降级服务
    MINIMAL = "minimal"  # 最小服务
    OFFLINE = "offline"  # 离线状态


class RecoveryAction(Enum):
    """恢复动作"""

    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    CIRCUIT_BREAK = "circuit_break"
    RESTART = "restart"
    IGNORE = "ignore"


@dataclass
class RecoveryStrategy:
    """恢复策略"""

    name: str
    action: RecoveryAction
    max_attempts: int = 3
    delay: float = 1.0
    backoff_factor: float = 2.0
    timeout: float = 30.0
    fallback_func: Optional[Callable] = None
    condition_func: Optional[Callable] = None


class RecoveryManager:
    """恢复管理器"""

    def __init__(self):
        self.strategies: Dict[type, List[RecoveryStrategy]] = {}
        self.service_levels: Dict[str, ServiceLevel] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.recovery_history: List[Dict[str, Any]] = []
        self.max_history = 1000

    def register_strategy(self, exception_type: type, strategy: RecoveryStrategy):
        """注册恢复策略"""
        if exception_type not in self.strategies:
            self.strategies[exception_type] = []
        self.strategies[exception_type].append(strategy)
        logger.info(
            f"Registered recovery strategy '{strategy.name}' for {exception_type.__name__}"
        )

    def register_fallback_handler(self, service: str, handler: Callable):
        """注册降级处理器"""
        self.fallback_handlers[service] = handler
        logger.info(f"Registered fallback handler for service: {service}")

    def set_service_level(self, service: str, level: ServiceLevel):
        """设置服务级别"""
        old_level = self.service_levels.get(service, ServiceLevel.FULL)
        self.service_levels[service] = level

        if old_level != level:
            logger.info(
                f"Service level changed for {service}: {old_level.value} -> {level.value}"
            )
            self._record_recovery_event(
                "service_level_change",
                {
                    "service": service,
                    "old_level": old_level.value,
                    "new_level": level.value,
                },
            )

    def get_service_level(self, service: str) -> ServiceLevel:
        """获取服务级别"""
        return self.service_levels.get(service, ServiceLevel.FULL)

    def recover_from_error(
        self, error: Exception, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """从错误中恢复"""
        context = context or {}
        error_type = type(error)

        # 查找匹配的恢复策略
        strategies = self._find_strategies(error_type)

        if not strategies:
            logger.warning(f"No recovery strategy found for {error_type.__name__}")
            return {"recovered": False, "strategy": None}

        # 尝试每个策略
        for strategy in strategies:
            try:
                # 检查策略条件
                if strategy.condition_func and not strategy.condition_func(
                    error, context
                ):
                    continue

                logger.info(f"Attempting recovery with strategy: {strategy.name}")
                result = self._execute_strategy(strategy, error, context)

                if result["success"]:
                    self._record_recovery_event(
                        "recovery_success",
                        {
                            "strategy": strategy.name,
                            "error_type": error_type.__name__,
                            "context": context,
                        },
                    )
                    return result

            except Exception as strategy_error:
                logger.error(
                    f"Recovery strategy '{strategy.name}' failed: {strategy_error}"
                )

        # 所有策略都失败
        self._record_recovery_event(
            "recovery_failed",
            {
                "error_type": error_type.__name__,
                "strategies_tried": [s.name for s in strategies],
                "context": context,
            },
        )

        return {
            "recovered": False,
            "strategy": None,
            "error": "All recovery strategies failed",
        }

    def _find_strategies(self, error_type: type) -> List[RecoveryStrategy]:
        """查找匹配的恢复策略"""
        strategies = []

        # 直接匹配
        if error_type in self.strategies:
            strategies.extend(self.strategies[error_type])

        # 父类匹配
        for registered_type, registered_strategies in self.strategies.items():
            if (
                issubclass(error_type, registered_type)
                and registered_type != error_type
            ):
                strategies.extend(registered_strategies)

        return strategies

    def _execute_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行恢复策略"""
        if strategy.action == RecoveryAction.RETRY:
            return self._execute_retry_strategy(strategy, error, context)
        elif strategy.action == RecoveryAction.FALLBACK:
            return self._execute_fallback_strategy(strategy, error, context)
        elif strategy.action == RecoveryAction.DEGRADE:
            return self._execute_degrade_strategy(strategy, error, context)
        elif strategy.action == RecoveryAction.CIRCUIT_BREAK:
            return self._execute_circuit_break_strategy(strategy, error, context)
        elif strategy.action == RecoveryAction.RESTART:
            return self._execute_restart_strategy(strategy, error, context)
        elif strategy.action == RecoveryAction.IGNORE:
            return self._execute_ignore_strategy(strategy, error, context)
        else:
            return {
                "success": False,
                "message": f"Unknown recovery action: {strategy.action}",
            }

    def _execute_retry_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行重试策略"""
        original_func = context.get("function")
        if not original_func:
            return {"success": False, "message": "No function to retry"}

        delay = strategy.delay

        for attempt in range(strategy.max_attempts):
            try:
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt + 1}/{strategy.max_attempts} after {delay}s"
                    )
                    time.sleep(delay)
                    delay *= strategy.backoff_factor

                # 重新执行原函数
                args = context.get("args", ())
                kwargs = context.get("kwargs", {})
                result = original_func(*args, **kwargs)

                return {"success": True, "result": result, "attempts": attempt + 1}

            except Exception as retry_error:
                if attempt == strategy.max_attempts - 1:
                    return {
                        "success": False,
                        "error": retry_error,
                        "attempts": attempt + 1,
                    }
                continue

        return {"success": False, "message": "Max retry attempts exceeded"}

    def _execute_fallback_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行降级策略"""
        if strategy.fallback_func:
            try:
                args = context.get("args", ())
                kwargs = context.get("kwargs", {})
                result = strategy.fallback_func(*args, **kwargs)
                return {"success": True, "result": result, "fallback": True}
            except Exception as fallback_error:
                return {"success": False, "error": fallback_error}

        # 查找服务降级处理器
        service = context.get("service")
        if service and service in self.fallback_handlers:
            try:
                handler = self.fallback_handlers[service]
                result = handler(error, context)
                return {"success": True, "result": result, "fallback": True}
            except Exception as handler_error:
                return {"success": False, "error": handler_error}

        return {"success": False, "message": "No fallback function available"}

    def _execute_degrade_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行服务降级策略"""
        service = context.get("service", "unknown")
        current_level = self.get_service_level(service)

        # 降级服务级别
        if current_level == ServiceLevel.FULL:
            self.set_service_level(service, ServiceLevel.DEGRADED)
        elif current_level == ServiceLevel.DEGRADED:
            self.set_service_level(service, ServiceLevel.MINIMAL)
        elif current_level == ServiceLevel.MINIMAL:
            self.set_service_level(service, ServiceLevel.OFFLINE)

        return {
            "success": True,
            "action": "service_degraded",
            "new_level": self.get_service_level(service).value,
        }

    def _execute_circuit_break_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行熔断策略"""
        service = context.get("service", "unknown")

        # 这里应该与错误处理器的熔断器集成
        from .error_handler import get_error_handler

        error_handler = get_error_handler()

        # 检查熔断器状态
        if error_handler.is_circuit_breaker_open(service):
            return {
                "success": False,
                "message": f"Circuit breaker is open for service: {service}",
            }

        return {"success": True, "action": "circuit_break_checked"}

    def _execute_restart_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行重启策略"""
        service = context.get("service")
        if not service:
            return {"success": False, "message": "No service specified for restart"}

        # 这里应该实现服务重启逻辑
        logger.warning(f"Service restart requested for: {service}")

        return {"success": True, "action": "restart_requested", "service": service}

    def _execute_ignore_strategy(
        self, strategy: RecoveryStrategy, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行忽略策略"""
        logger.info(f"Ignoring error as per strategy: {error}")
        return {"success": True, "action": "ignored"}

    def _record_recovery_event(self, event_type: str, details: Dict[str, Any]):
        """记录恢复事件"""
        event = {"timestamp": time.time(), "event_type": event_type, "details": details}

        self.recovery_history.append(event)

        # 限制历史记录大小
        if len(self.recovery_history) > self.max_history:
            self.recovery_history = self.recovery_history[-self.max_history :]

    def get_recovery_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取恢复历史"""
        return self.recovery_history[-limit:]

    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "service_levels": {k: v.value for k, v in self.service_levels.items()},
            "fallback_handlers": list(self.fallback_handlers.keys()),
            "recovery_strategies": {
                exc_type.__name__: [s.name for s in strategies]
                for exc_type, strategies in self.strategies.items()
            },
        }


# 全局恢复管理器
_recovery_manager = RecoveryManager()


def get_recovery_manager() -> RecoveryManager:
    """获取恢复管理器"""
    return _recovery_manager


def with_recovery(
    strategies: List[RecoveryStrategy] = None,
    service: str = None,
    context: Dict[str, Any] = None,
):
    """恢复装饰器"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                recovery_context = context or {}
                recovery_context.update(
                    {
                        "function": func,
                        "args": args,
                        "kwargs": kwargs,
                        "service": service,
                    }
                )

                # 如果指定了策略，临时注册
                if strategies:
                    for strategy in strategies:
                        _recovery_manager.register_strategy(type(e), strategy)

                # 尝试恢复
                result = _recovery_manager.recover_from_error(e, recovery_context)

                if result["recovered"]:
                    return result.get("result")
                else:
                    raise

        return wrapper

    return decorator


# 默认恢复策略
def setup_default_recovery_strategies():
    """设置默认恢复策略"""

    # 网络错误恢复策略
    network_retry_strategy = RecoveryStrategy(
        name="network_retry",
        action=RecoveryAction.RETRY,
        max_attempts=3,
        delay=1.0,
        backoff_factor=2.0,
    )
    _recovery_manager.register_strategy(NetworkError, network_retry_strategy)

    # LLM错误恢复策略
    llm_fallback_strategy = RecoveryStrategy(
        name="llm_fallback",
        action=RecoveryAction.FALLBACK,
        fallback_func=lambda *args, **kwargs: {
            "error": "LLM service unavailable",
            "fallback": True,
        },
    )
    _recovery_manager.register_strategy(LLMError, llm_fallback_strategy)

    # 超时错误恢复策略
    timeout_retry_strategy = RecoveryStrategy(
        name="timeout_retry",
        action=RecoveryAction.RETRY,
        max_attempts=2,
        delay=0.5,
        backoff_factor=1.5,
    )
    _recovery_manager.register_strategy(TimeoutError, timeout_retry_strategy)

    # 资源错误恢复策略
    resource_degrade_strategy = RecoveryStrategy(
        name="resource_degrade", action=RecoveryAction.DEGRADE
    )
    _recovery_manager.register_strategy(ResourceError, resource_degrade_strategy)

    # 配置错误恢复策略
    config_fallback_strategy = RecoveryStrategy(
        name="config_fallback",
        action=RecoveryAction.FALLBACK,
        fallback_func=lambda *args, **kwargs: {
            "message": "Using default configuration"
        },
    )
    _recovery_manager.register_strategy(ConfigurationError, config_fallback_strategy)


# 默认降级处理器
def llm_fallback_handler(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """LLM服务降级处理器"""
    return {
        "response": "抱歉，AI服务暂时不可用，请稍后重试。",
        "fallback": True,
        "error": str(error),
    }


def rag_fallback_handler(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """RAG服务降级处理器"""
    return {
        "documents": [],
        "message": "文档检索服务暂时不可用",
        "fallback": True,
        "error": str(error),
    }


def mcp_fallback_handler(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """MCP工具降级处理器"""
    return {
        "result": None,
        "message": "外部工具暂时不可用",
        "fallback": True,
        "error": str(error),
    }


# 注册默认降级处理器
_recovery_manager.register_fallback_handler("llm", llm_fallback_handler)
_recovery_manager.register_fallback_handler("rag", rag_fallback_handler)
_recovery_manager.register_fallback_handler("mcp", mcp_fallback_handler)


def initialize_recovery_system():
    """初始化恢复系统"""
    try:
        setup_default_recovery_strategies()
        logger.info("Recovery system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize recovery system: {e}")
        return False
