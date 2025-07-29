#!/usr/bin/env python3
"""
全局错误处理器

提供统一的错误处理、记录和恢复机制
"""

import logging
import sys
import traceback
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

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
from .network_error_classifier import get_network_error_classifier
from .error_notification_service import get_error_notification_service
from .resilience import RetryManager, CircuitBreaker, get_retry_manager

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

        # 新增组件
        self.network_classifier = get_network_error_classifier()
        self.notification_service = get_error_notification_service()
        self.error_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000

        # 集成新的弹性组件
        self.retry_manager = get_retry_manager()
        logger.info("错误处理器已集成重试管理器和熔断器组件")

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

        # 增强网络错误处理
        processed_error = self._process_network_error(error, context)

        # 记录错误
        error_info = self._log_error(processed_error, context)

        # 更新错误统计
        self._update_error_stats(processed_error)

        # 执行错误回调
        self._execute_error_callback(processed_error, context)

        # 尝试恢复
        recovery_result = self._attempt_recovery(processed_error, context)

        # 发送用户通知
        self._send_user_notification(processed_error, context)

        # 记录到历史
        self._add_to_history(processed_error, context, recovery_result)

        return {
            "error_info": error_info,
            "recovery_result": recovery_result,
            "context": context,
            "processed_error": processed_error,
        }

    def _log_error(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """记录错误信息"""
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
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

    def _process_network_error(
        self, error: Exception, context: Dict[str, Any]
    ) -> Exception:
        """处理网络错误，进行智能分类"""
        import requests.exceptions as req_exc

        # 检查是否是网络相关错误
        if isinstance(error, (req_exc.RequestException, ConnectionError, TimeoutError)):
            try:
                # 使用网络错误分类器创建更详细的异常
                classified_error = self.network_classifier.create_network_exception(
                    error, context
                )
                logger.info(
                    f"Network error classified as: {classified_error.__class__.__name__}"
                )
                return classified_error
            except Exception as e:
                logger.warning(f"Failed to classify network error: {e}")
                return error

        return error

    def _send_user_notification(self, error: Exception, context: Dict[str, Any]):
        """发送用户通知"""
        if isinstance(error, TestAgentException):
            try:
                user_id = context.get("user_id", "anonymous")
                # 异步发送通知（这里简化为同步调用）
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        self.notification_service.notify_user(error, user_id, context)
                    )
                except RuntimeError:
                    # 如果没有事件循环，创建一个新的
                    asyncio.run(
                        self.notification_service.notify_user(error, user_id, context)
                    )
            except Exception as e:
                logger.error(f"Failed to send user notification: {e}")

    def _add_to_history(
        self, error: Exception, context: Dict[str, Any], recovery_result: Dict[str, Any]
    ):
        """添加到错误历史"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "context": context,
            "recovery_attempted": recovery_result.get("recovered", False),
            "recovery_strategy": recovery_result.get("strategy"),
        }

        if isinstance(error, TestAgentException):
            history_entry.update(
                {
                    "error_code": error.error_code,
                    "category": error.category.value,
                    "severity": error.severity.value,
                }
            )

        self.error_history.append(history_entry)

        # 限制历史记录大小
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size :]

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        from datetime import datetime, timedelta

        # 基础统计
        stats = {
            "error_count": self.error_count.copy(),
            "circuit_breakers": self.circuit_breakers.copy(),
            "total_errors": sum(self.error_count.values()),
            "history_size": len(self.error_history),
        }

        # 最近24小时的错误统计
        if self.error_history:
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_errors = [
                entry
                for entry in self.error_history
                if datetime.fromisoformat(entry["timestamp"]) > recent_cutoff
            ]

            stats["recent_24h"] = {
                "total": len(recent_errors),
                "by_type": {},
                "by_severity": {},
                "recovery_rate": 0,
            }

            # 按类型统计
            for entry in recent_errors:
                error_type = entry["error_type"]
                stats["recent_24h"]["by_type"][error_type] = (
                    stats["recent_24h"]["by_type"].get(error_type, 0) + 1
                )

            # 按严重程度统计
            for entry in recent_errors:
                severity = entry.get("severity", "unknown")
                stats["recent_24h"]["by_severity"][severity] = (
                    stats["recent_24h"]["by_severity"].get(severity, 0) + 1
                )

            # 恢复成功率
            recovered_count = sum(
                1 for entry in recent_errors if entry.get("recovery_attempted")
            )
            if recent_errors:
                stats["recent_24h"]["recovery_rate"] = recovered_count / len(
                    recent_errors
                )

        return stats

    def get_error_history(
        self, limit: int = 100, error_type: str = None
    ) -> List[Dict[str, Any]]:
        """获取错误历史"""
        history = self.error_history

        # 按错误类型过滤
        if error_type:
            history = [entry for entry in history if entry["error_type"] == error_type]

        # 返回最近的记录
        return history[-limit:] if limit else history

    def clear_error_history(self):
        """清空错误历史"""
        self.error_history.clear()
        logger.info("Error history cleared")

    def diagnose_recurring_errors(self) -> Dict[str, Any]:
        """诊断重复出现的错误"""
        from collections import Counter
        from datetime import datetime, timedelta

        if not self.error_history:
            return {"recurring_errors": [], "recommendations": []}

        # 分析最近24小时的错误
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_errors = [
            entry
            for entry in self.error_history
            if datetime.fromisoformat(entry["timestamp"]) > recent_cutoff
        ]

        # 统计错误频率
        error_counter = Counter(entry["error_type"] for entry in recent_errors)

        # 识别重复错误（出现3次以上）
        recurring_errors = [
            {
                "error_type": error_type,
                "count": count,
                "frequency": count / len(recent_errors),
            }
            for error_type, count in error_counter.items()
            if count >= 3
        ]

        # 生成建议
        recommendations = []
        for error_info in recurring_errors:
            error_type = error_info["error_type"]
            count = error_info["count"]

            if "Network" in error_type:
                recommendations.append(
                    f"网络错误 {error_type} 出现 {count} 次，建议检查网络连接稳定性"
                )
            elif "Timeout" in error_type:
                recommendations.append(
                    f"超时错误 {error_type} 出现 {count} 次，建议增加超时时间或优化性能"
                )
            elif "Authentication" in error_type:
                recommendations.append(
                    f"认证错误 {error_type} 出现 {count} 次，建议检查认证配置"
                )
            else:
                recommendations.append(
                    f"错误 {error_type} 频繁出现 {count} 次，建议深入调查根本原因"
                )

        return {
            "recurring_errors": recurring_errors,
            "recommendations": recommendations,
            "analysis_period": "24小时",
            "total_recent_errors": len(recent_errors),
        }

    def execute_with_retry(
        self, func: Callable, *args, policy_name: str = "standard", **kwargs
    ):
        """使用重试机制执行函数"""
        try:
            execution = self.retry_manager.execute_with_retry(
                func, *args, policy=policy_name, **kwargs
            )
            if execution.success:
                return execution.final_result
            else:
                # 记录重试失败
                self.handle_error(
                    execution.final_exception,
                    {
                        "retry_attempts": execution.attempt_count,
                        "retry_result": execution.result.value,
                        "total_duration": execution.total_duration,
                    },
                )
                raise execution.final_exception
        except Exception as e:
            logger.error(f"重试执行失败: {e}")
            raise

    async def aexecute_with_retry(
        self, func: Callable, *args, policy_name: str = "standard", **kwargs
    ):
        """异步使用重试机制执行函数"""
        try:
            execution = await self.retry_manager.aexecute_with_retry(
                func, *args, policy=policy_name, **kwargs
            )
            if execution.success:
                return execution.final_result
            else:
                # 记录重试失败
                self.handle_error(
                    execution.final_exception,
                    {
                        "retry_attempts": execution.attempt_count,
                        "retry_result": execution.result.value,
                        "total_duration": execution.total_duration,
                    },
                )
                raise execution.final_exception
        except Exception as e:
            logger.error(f"异步重试执行失败: {e}")
            raise

    def get_retry_stats(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        return self.retry_manager.get_stats()

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """获取熔断器统计信息"""
        return self.retry_manager.circuit_breaker_registry.get_all_stats()

    def reset_circuit_breaker(self, service: str):
        """重置指定服务的熔断器"""
        # 重置旧的熔断器实现
        if service in self.circuit_breakers:
            self.circuit_breakers[service] = {
                "failure_count": 0,
                "last_failure_time": 0,
                "state": "closed",
            }
            logger.info(f"旧熔断器已重置: {service}")

        # 重置新的熔断器实现
        circuit_breaker = self.retry_manager.circuit_breaker_registry.get(service)
        if circuit_breaker:
            circuit_breaker.reset()
            logger.info(f"新熔断器已重置: {service}")
        else:
            logger.warning(f"未找到熔断器: {service}")

    def register_retry_policy(self, name: str, policy):
        """注册重试策略"""
        self.retry_manager.register_policy(name, policy)
        logger.info(f"已注册重试策略: {name}")


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
