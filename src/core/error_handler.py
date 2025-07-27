#!/usr/bin/env python3
"""
全局错误处理器

提供统一的错误处理、记录和恢复机制
"""

import logging
import sys
import traceback
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, Union

from .exceptions import (
    ConfigurationError,
    ErrorCategory,
    ErrorSeverity,
    NetworkError,
    ProcessingError,
    ResourceError,
    TestAgentException,
    TimeoutError,
)

logger = logging.getLogger("error_handler")


class ErrorHandler:
    """全局错误处理器"""

    def __init__(self):
        self.error_callbacks: Dict[Type[Exception], Callable] = {}
        self.recovery_strategies: Dict[Type[Exception], Callable] = {}
        self.error_count: Dict[str, int] = {}
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5分钟
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}

    def register_error_callback(
        self, exception_type: Type[Exception], callback: Callable
    ):
        """注册错误回调函数"""
        self.error_callbacks[exception_type] = callback

    def register_recovery_strategy(
        self, exception_type: Type[Exception], strategy: Callable
    ):
        """注册错误恢复策略"""
        self.recovery_strategies[exception_type] = strategy

    def handle_error(
        self, error: Exception, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """处理错误"""
        context = context or {}

        # 记录错误
        error_info = self._log_error(error, context)

        # 更新错误统计
        self._update_error_stats(error)

        # 执行错误回调
        self._execute_error_callback(error, context)

        # 尝试恢复
        recovery_result = self._attempt_recovery(error, context)

        return {
            "error_info": error_info,
            "recovery_result": recovery_result,
            "context": context,
        }

    def _log_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """记录错误信息"""
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
        }

        # 如果是TestAgent自定义异常，记录更多信息
        if isinstance(error, TestAgentException):
            error_info.update(
                {
                    "error_code": error.error_code,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "details": error.details,
                    "suggestions": error.suggestions,
                }
            )

            # 根据严重程度选择日志级别
            if error.severity == ErrorSeverity.CRITICAL:
                logger.critical(f"Critical error: {error.message}", extra=error_info)
            elif error.severity == ErrorSeverity.HIGH:
                logger.error(f"High severity error: {error.message}", extra=error_info)
            elif error.severity == ErrorSeverity.MEDIUM:
                logger.warning(
                    f"Medium severity error: {error.message}", extra=error_info
                )
            else:
                logger.info(f"Low severity error: {error.message}", extra=error_info)
        else:
            logger.error(f"Unhandled error: {error}", extra=error_info)

        return error_info

    def _update_error_stats(self, error: Exception):
        """更新错误统计"""
        error_type = type(error).__name__
        self.error_count[error_type] = self.error_count.get(error_type, 0) + 1

        # 检查是否需要触发熔断器
        if isinstance(error, (NetworkError, TimeoutError)):
            service = getattr(error, "details", {}).get("service", "unknown")
            self._check_circuit_breaker(service)

    def _check_circuit_breaker(self, service: str):
        """检查熔断器状态"""
        import time

        if service not in self.circuit_breakers:
            self.circuit_breakers[service] = {
                "failure_count": 0,
                "last_failure_time": 0,
                "state": "closed",  # closed, open, half-open
            }

        breaker = self.circuit_breakers[service]
        current_time = time.time()

        if breaker["state"] == "closed":
            breaker["failure_count"] += 1
            breaker["last_failure_time"] = current_time

            if breaker["failure_count"] >= self.circuit_breaker_threshold:
                breaker["state"] = "open"
                logger.warning(f"Circuit breaker opened for service: {service}")

        elif breaker["state"] == "open":
            if (
                current_time - breaker["last_failure_time"]
                > self.circuit_breaker_timeout
            ):
                breaker["state"] = "half-open"
                breaker["failure_count"] = 0
                logger.info(f"Circuit breaker half-opened for service: {service}")

    def _execute_error_callback(self, error: Exception, context: Dict[str, Any]):
        """执行错误回调"""
        error_type = type(error)

        # 查找匹配的回调函数
        for exception_type, callback in self.error_callbacks.items():
            if isinstance(error, exception_type):
                try:
                    callback(error, context)
                except Exception as callback_error:
                    logger.error(f"Error in error callback: {callback_error}")

    def _attempt_recovery(
        self, error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """尝试错误恢复"""
        error_type = type(error)
        recovery_result = {"recovered": False, "strategy": None, "message": None}

        # 查找匹配的恢复策略
        for exception_type, strategy in self.recovery_strategies.items():
            if isinstance(error, exception_type):
                try:
                    result = strategy(error, context)
                    recovery_result.update(
                        {
                            "recovered": True,
                            "strategy": strategy.__name__,
                            "result": result,
                        }
                    )
                    logger.info(
                        f"Error recovery successful using strategy: {strategy.__name__}"
                    )
                    break
                except Exception as recovery_error:
                    logger.error(f"Error recovery failed: {recovery_error}")
                    recovery_result["message"] = str(recovery_error)

        return recovery_result

    def is_circuit_breaker_open(self, service: str) -> bool:
        """检查熔断器是否开启"""
        if service not in self.circuit_breakers:
            return False
        return self.circuit_breakers[service]["state"] == "open"

    def reset_circuit_breaker(self, service: str):
        """重置熔断器"""
        if service in self.circuit_breakers:
            self.circuit_breakers[service] = {
                "failure_count": 0,
                "last_failure_time": 0,
                "state": "closed",
            }
            logger.info(f"Circuit breaker reset for service: {service}")

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            "error_count": self.error_count.copy(),
            "circuit_breakers": self.circuit_breakers.copy(),
            "total_errors": sum(self.error_count.values()),
        }


# 全局错误处理器实例
_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return _error_handler


def handle_errors(
    exceptions: Union[Type[Exception], tuple] = Exception,
    reraise: bool = True,
    default_return: Any = None,
    context: Dict[str, Any] = None,
):
    """错误处理装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                error_context = context or {}
                error_context.update(
                    {
                        "function": func.__name__,
                        "args": str(args)[:200],  # 限制长度
                        "kwargs": str(kwargs)[:200],
                    }
                )

                _error_handler.handle_error(e, error_context)

                if reraise:
                    raise
                else:
                    return default_return

        return wrapper

    return decorator


def safe_execute(
    func: Callable,
    *args,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> Dict[str, Any]:
    """安全执行函数，带重试机制"""
    import time

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)
            return {"success": True, "result": result, "attempts": attempt + 1}
        except exceptions as e:
            last_error = e

            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}"
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                logger.error(f"All {max_retries + 1} attempts failed")

    # 处理最终失败
    _error_handler.handle_error(
        last_error,
        {"function": func.__name__, "max_retries": max_retries, "final_attempt": True},
    )

    return {"success": False, "error": last_error, "attempts": max_retries + 1}


@contextmanager
def error_context(context_info: Dict[str, Any]):
    """错误上下文管理器"""
    try:
        yield
    except Exception as e:
        _error_handler.handle_error(e, context_info)
        raise


def setup_global_exception_handler():
    """设置全局异常处理器"""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # 允许Ctrl+C正常退出
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

        # 处理未捕获的异常
        _error_handler.handle_error(
            exc_value, {"type": "uncaught_exception", "exc_type": exc_type.__name__}
        )

    sys.excepthook = handle_exception


# 默认恢复策略
def default_network_recovery(error: NetworkError, context: Dict[str, Any]) -> bool:
    """默认网络错误恢复策略"""
    import time

    # 简单的重试策略
    if context.get("retry_count", 0) < 3:
        time.sleep(2 ** context.get("retry_count", 0))  # 指数退避
        return True
    return False


def default_config_recovery(error: ConfigurationError, context: Dict[str, Any]) -> bool:
    """默认配置错误恢复策略"""
    # 尝试使用默认配置
    logger.info("Attempting to use default configuration")
    return True


def default_resource_recovery(error: ResourceError, context: Dict[str, Any]) -> bool:
    """默认资源错误恢复策略"""
    import gc

    # 尝试垃圾回收释放内存
    gc.collect()
    logger.info("Performed garbage collection for resource recovery")
    return True


# 注册默认恢复策略
_error_handler.register_recovery_strategy(NetworkError, default_network_recovery)
_error_handler.register_recovery_strategy(ConfigurationError, default_config_recovery)
_error_handler.register_recovery_strategy(ResourceError, default_resource_recovery)
