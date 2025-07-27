#!/usr/bin/env python3
"""
监控和错误处理系统测试
"""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.error_handler import (ErrorHandler, get_error_handler,
                                    handle_errors, safe_execute)
from src.core.exceptions import (ConfigurationError, ErrorCategory,
                                 ErrorSeverity, LLMError, NetworkError,
                                 TestAgentException)
from src.core.monitoring import (HealthChecker, MetricsCollector,
                                 PerformanceProfiler, SystemMonitor,
                                 monitor_performance, record_metric)
from src.core.recovery import (RecoveryAction, RecoveryManager,
                               RecoveryStrategy, ServiceLevel)


class TestExceptions:
    """测试异常类"""

    def test_test_agent_exception_creation(self):
        """测试TestAgent异常创建"""
        error = TestAgentException(
            "Test error",
            error_code="TEST_001",
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.HIGH,
            details={"key": "value"},
            suggestions=["Try again"],
        )

        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.category == ErrorCategory.PROCESSING
        assert error.severity == ErrorSeverity.HIGH
        assert error.details == {"key": "value"}
        assert error.suggestions == ["Try again"]

    def test_exception_to_dict(self):
        """测试异常转换为字典"""
        error = NetworkError(
            "Network failed", url="http://example.com", status_code=500
        )
        error_dict = error.to_dict()

        assert error_dict["error_code"] == "NetworkError"
        assert error_dict["message"] == "Network failed"
        assert error_dict["category"] == "network"
        assert error_dict["severity"] == "high"
        assert error_dict["details"]["url"] == "http://example.com"
        assert error_dict["details"]["status_code"] == 500

    def test_llm_error_creation(self):
        """测试LLM错误创建"""
        error = LLMError("Model failed", provider="openai", model="gpt-3.5-turbo")

        assert error.details["service"] == "llm"
        assert error.details["provider"] == "openai"
        assert error.details["model"] == "gpt-3.5-turbo"


class TestErrorHandler:
    """测试错误处理器"""

    def setup_method(self):
        """设置测试"""
        self.error_handler = ErrorHandler()

    def test_error_callback_registration(self):
        """测试错误回调注册"""
        callback = Mock()
        self.error_handler.register_error_callback(NetworkError, callback)

        error = NetworkError("Test error")
        self.error_handler.handle_error(error)

        callback.assert_called_once()

    def test_recovery_strategy_registration(self):
        """测试恢复策略注册"""
        strategy = Mock(return_value=True)
        self.error_handler.register_recovery_strategy(NetworkError, strategy)

        error = NetworkError("Test error")
        result = self.error_handler.handle_error(error)

        strategy.assert_called_once()
        assert result["recovery_result"]["recovered"] == True

    def test_circuit_breaker(self):
        """测试熔断器"""
        # 模拟多次网络错误
        for _ in range(6):  # 超过阈值
            error = NetworkError("Network failed")
            error.details = {"service": "test_service"}
            self.error_handler.handle_error(error)

        # 检查熔断器是否开启
        assert self.error_handler.is_circuit_breaker_open("test_service")

        # 重置熔断器
        self.error_handler.reset_circuit_breaker("test_service")
        assert not self.error_handler.is_circuit_breaker_open("test_service")

    def test_handle_errors_decorator(self):
        """测试错误处理装饰器"""

        @handle_errors(NetworkError, reraise=False, default_return="fallback")
        def failing_function():
            raise NetworkError("Network failed")

        result = failing_function()
        assert result == "fallback"

    def test_safe_execute(self):
        """测试安全执行"""

        def failing_function():
            raise NetworkError("Network failed")

        result = safe_execute(failing_function, max_retries=2)

        assert result["success"] == False
        assert result["attempts"] == 3  # 原始尝试 + 2次重试


class TestMetricsCollector:
    """测试指标收集器"""

    def setup_method(self):
        """设置测试"""
        self.collector = MetricsCollector()

    def test_record_metric(self):
        """测试记录指标"""
        self.collector.record_metric("test.metric", 42.0, {"tag": "value"}, "count")

        metrics = self.collector.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "test.metric"
        assert metrics[0].value == 42.0
        assert metrics[0].tags == {"tag": "value"}
        assert metrics[0].unit == "count"

    def test_record_performance(self):
        """测试记录性能指标"""
        self.collector.record_performance("test_operation", 1.5, success=True)
        self.collector.record_performance("test_operation", 2.0, success=False)

        stats = self.collector.get_performance_stats("test_operation")
        operation_stats = stats["test_operation"]

        assert operation_stats.total_calls == 2
        assert operation_stats.total_time == 3.5
        assert operation_stats.avg_time == 1.75
        assert operation_stats.error_count == 1
        assert operation_stats.success_rate == 50.0

    def test_custom_metrics(self):
        """测试自定义指标"""
        self.collector.set_custom_metric("custom.metric", 100.0)

        custom_metrics = self.collector.get_custom_metrics()
        assert custom_metrics["custom.metric"] == 100.0

    def test_metrics_filtering(self):
        """测试指标过滤"""
        self.collector.record_metric("system.cpu", 50.0)
        self.collector.record_metric("system.memory", 60.0)
        self.collector.record_metric("app.requests", 100.0)

        system_metrics = self.collector.get_metrics("system")
        assert len(system_metrics) == 2

        all_metrics = self.collector.get_metrics()
        assert len(all_metrics) == 3


class TestHealthChecker:
    """测试健康检查器"""

    def setup_method(self):
        """设置测试"""
        self.health_checker = HealthChecker()

    def test_register_health_check(self):
        """测试注册健康检查"""

        def test_check():
            return True

        self.health_checker.register_health_check("test", test_check)
        results = self.health_checker.run_health_checks()

        assert "test" in results
        assert results["test"]["status"] == "healthy"

    def test_health_check_with_dict_result(self):
        """测试返回字典的健康检查"""

        def test_check():
            return {"status": "warning", "details": {"message": "High CPU usage"}}

        self.health_checker.register_health_check("test", test_check)
        results = self.health_checker.run_health_checks()

        assert results["test"]["status"] == "warning"
        assert results["test"]["details"]["message"] == "High CPU usage"

    def test_health_check_exception(self):
        """测试健康检查异常"""

        def failing_check():
            raise Exception("Check failed")

        self.health_checker.register_health_check("failing", failing_check)
        results = self.health_checker.run_health_checks()

        assert results["failing"]["status"] == "error"
        assert "Check failed" in results["failing"]["details"]["error"]

    def test_overall_health_status(self):
        """测试整体健康状态"""

        def healthy_check():
            return True

        def unhealthy_check():
            return False

        self.health_checker.register_health_check("healthy", healthy_check)
        self.health_checker.register_health_check("unhealthy", unhealthy_check)

        self.health_checker.run_health_checks()
        assert not self.health_checker.is_healthy()


class TestPerformanceProfiler:
    """测试性能分析器"""

    def setup_method(self):
        """设置测试"""
        self.collector = MetricsCollector()
        self.profiler = PerformanceProfiler(self.collector)

    def test_profile_context_manager(self):
        """测试性能分析上下文管理器"""
        with self.profiler.profile("test_operation"):
            time.sleep(0.1)

        stats = self.collector.get_performance_stats("test_operation")
        assert "test_operation" in stats
        assert stats["test_operation"].total_calls == 1
        assert stats["test_operation"].total_time >= 0.1

    def test_profile_with_exception(self):
        """测试带异常的性能分析"""
        with pytest.raises(ValueError):
            with self.profiler.profile("failing_operation"):
                raise ValueError("Test error")

        stats = self.collector.get_performance_stats("failing_operation")
        assert stats["failing_operation"].error_count == 1
        assert stats["failing_operation"].success_rate == 0.0

    def test_monitor_performance_decorator(self):
        """测试性能监控装饰器"""

        @monitor_performance("decorated_function")
        def test_function():
            time.sleep(0.05)
            return "result"

        result = test_function()
        assert result == "result"

        # 检查是否记录了性能指标
        metrics = self.collector.get_metrics("performance.decorated_function.duration")
        assert len(metrics) == 1
        assert metrics[0].value >= 0.05


class TestRecoveryManager:
    """测试恢复管理器"""

    def setup_method(self):
        """设置测试"""
        self.recovery_manager = RecoveryManager()

    def test_register_strategy(self):
        """测试注册恢复策略"""
        strategy = RecoveryStrategy(
            name="test_retry", action=RecoveryAction.RETRY, max_attempts=3
        )

        self.recovery_manager.register_strategy(NetworkError, strategy)

        # 检查策略是否注册
        assert NetworkError in self.recovery_manager.strategies
        assert len(self.recovery_manager.strategies[NetworkError]) == 1

    def test_service_level_management(self):
        """测试服务级别管理"""
        self.recovery_manager.set_service_level("test_service", ServiceLevel.DEGRADED)

        level = self.recovery_manager.get_service_level("test_service")
        assert level == ServiceLevel.DEGRADED

    def test_fallback_handler_registration(self):
        """测试降级处理器注册"""

        def test_handler(error, context):
            return {"fallback": True}

        self.recovery_manager.register_fallback_handler("test_service", test_handler)

        assert "test_service" in self.recovery_manager.fallback_handlers

    def test_recovery_from_error(self):
        """测试错误恢复"""
        # 注册重试策略
        strategy = RecoveryStrategy(
            name="test_retry", action=RecoveryAction.RETRY, max_attempts=2
        )
        self.recovery_manager.register_strategy(NetworkError, strategy)

        # 模拟可恢复的函数
        call_count = 0

        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Network failed")
            return "success"

        error = NetworkError("Network failed")
        context = {"function": test_function}

        result = self.recovery_manager.recover_from_error(error, context)

        assert result["recovered"] == True
        assert result["result"] == "success"

    def test_recovery_history(self):
        """测试恢复历史记录"""
        # 触发一个恢复事件
        self.recovery_manager._record_recovery_event("test_event", {"key": "value"})

        history = self.recovery_manager.get_recovery_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "test_event"
        assert history[0]["details"]["key"] == "value"


class TestIntegration:
    """集成测试"""

    def test_error_handling_with_monitoring(self):
        """测试错误处理与监控集成"""
        collector = MetricsCollector()
        error_handler = ErrorHandler()

        # 注册错误回调来记录指标
        def error_callback(error, context):
            collector.record_metric("errors.total", 1, {"type": type(error).__name__})

        error_handler.register_error_callback(Exception, error_callback)

        # 触发错误
        error = NetworkError("Test error")
        error_handler.handle_error(error)

        # 检查指标是否记录
        metrics = collector.get_metrics("errors.total")
        assert len(metrics) == 1
        assert metrics[0].tags["type"] == "NetworkError"

    def test_recovery_with_monitoring(self):
        """测试恢复与监控集成"""
        collector = MetricsCollector()
        recovery_manager = RecoveryManager()

        # 注册恢复策略
        strategy = RecoveryStrategy(
            name="test_fallback",
            action=RecoveryAction.FALLBACK,
            fallback_func=lambda: "fallback_result",
        )
        recovery_manager.register_strategy(LLMError, strategy)

        # 触发错误和恢复
        error = LLMError("LLM failed")
        result = recovery_manager.recover_from_error(error)

        assert result["recovered"] == True

        # 检查恢复历史
        history = recovery_manager.get_recovery_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "recovery_success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
