#!/usr/bin/env python3
"""
性能监控和指标收集系统

提供系统性能监控、指标收集和健康检查功能
"""

import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import psutil

logger = logging.getLogger("monitoring")


@dataclass
class Metric:
    """指标数据结构"""

    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class PerformanceStats:
    """性能统计数据"""

    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    error_count: int = 0
    success_rate: float = 100.0
    last_call_time: Optional[datetime] = None


class MetricsCollector:
    """指标收集器"""

    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.performance_stats: Dict[str, PerformanceStats] = defaultdict(
            PerformanceStats
        )
        self.custom_metrics: Dict[str, float] = {}
        self.lock = threading.Lock()

    def record_metric(
        self, name: str, value: float, tags: Dict[str, str] = None, unit: str = ""
    ):
        """记录指标"""
        with self.lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {},
                unit=unit,
            )
            self.metrics.append(metric)

    def record_performance(self, operation: str, duration: float, success: bool = True):
        """记录性能指标"""
        with self.lock:
            stats = self.performance_stats[operation]
            stats.total_calls += 1
            stats.total_time += duration
            stats.min_time = min(stats.min_time, duration)
            stats.max_time = max(stats.max_time, duration)
            stats.avg_time = stats.total_time / stats.total_calls
            stats.last_call_time = datetime.now()

            if not success:
                stats.error_count += 1

            stats.success_rate = (
                (stats.total_calls - stats.error_count) / stats.total_calls
            ) * 100

    def set_custom_metric(self, name: str, value: float):
        """设置自定义指标"""
        with self.lock:
            self.custom_metrics[name] = value

    def get_metrics(self, name_filter: str = None, limit: int = 100) -> List[Metric]:
        """获取指标数据"""
        with self.lock:
            metrics = list(self.metrics)

            if name_filter:
                metrics = [m for m in metrics if name_filter in m.name]

            return metrics[-limit:]

    def get_performance_stats(
        self, operation: str = None
    ) -> Dict[str, PerformanceStats]:
        """获取性能统计"""
        with self.lock:
            if operation:
                return {
                    operation: self.performance_stats.get(operation, PerformanceStats())
                }
            return dict(self.performance_stats)

    def get_custom_metrics(self) -> Dict[str, float]:
        """获取自定义指标"""
        with self.lock:
            return self.custom_metrics.copy()

    def clear_metrics(self):
        """清除指标数据"""
        with self.lock:
            self.metrics.clear()
            self.performance_stats.clear()
            self.custom_metrics.clear()


class SystemMonitor:
    """系统监控器"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 30  # 30秒

    def start_monitoring(self):
        """开始系统监控"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("System monitoring started")

    def stop_monitoring(self):
        """停止系统监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("System monitoring stopped")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitor_interval)

    def _collect_system_metrics(self):
        """收集系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics_collector.record_metric("system.cpu.usage", cpu_percent, unit="%")

        # 内存使用情况
        memory = psutil.virtual_memory()
        self.metrics_collector.record_metric(
            "system.memory.usage", memory.percent, unit="%"
        )
        self.metrics_collector.record_metric(
            "system.memory.available", memory.available, unit="bytes"
        )
        self.metrics_collector.record_metric(
            "system.memory.used", memory.used, unit="bytes"
        )

        # 磁盘使用情况
        disk = psutil.disk_usage("/")
        disk_percent = (disk.used / disk.total) * 100
        self.metrics_collector.record_metric(
            "system.disk.usage", disk_percent, unit="%"
        )
        self.metrics_collector.record_metric(
            "system.disk.free", disk.free, unit="bytes"
        )

        # 网络IO
        net_io = psutil.net_io_counters()
        self.metrics_collector.record_metric(
            "system.network.bytes_sent", net_io.bytes_sent, unit="bytes"
        )
        self.metrics_collector.record_metric(
            "system.network.bytes_recv", net_io.bytes_recv, unit="bytes"
        )

        # 进程信息
        process = psutil.Process()
        self.metrics_collector.record_metric(
            "process.cpu.usage", process.cpu_percent(), unit="%"
        )
        self.metrics_collector.record_metric(
            "process.memory.usage", process.memory_percent(), unit="%"
        )
        self.metrics_collector.record_metric(
            "process.memory.rss", process.memory_info().rss, unit="bytes"
        )

        # 文件描述符
        try:
            self.metrics_collector.record_metric(
                "process.fd.count", process.num_fds(), unit="count"
            )
        except AttributeError:
            # Windows doesn't have num_fds
            pass

        # 线程数
        self.metrics_collector.record_metric(
            "process.threads.count", process.num_threads(), unit="count"
        )


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.health_status: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_health_check(self, name: str, check_func: Callable):
        """注册健康检查"""
        self.health_checks[name] = check_func

    def run_health_checks(self) -> Dict[str, Dict[str, Any]]:
        """运行所有健康检查"""
        results = {}

        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = check_func()
                duration = time.time() - start_time

                if isinstance(result, bool):
                    status = "healthy" if result else "unhealthy"
                    details = {}
                elif isinstance(result, dict):
                    status = result.get("status", "unknown")
                    details = result.get("details", {})
                else:
                    status = "unknown"
                    details = {"result": str(result)}

                results[name] = {
                    "status": status,
                    "details": details,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                results[name] = {
                    "status": "error",
                    "details": {"error": str(e)},
                    "duration": 0,
                    "timestamp": datetime.now().isoformat(),
                }

        with self.lock:
            self.health_status = results

        return results

    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """获取健康状态"""
        with self.lock:
            return self.health_status.copy()

    def is_healthy(self) -> bool:
        """检查整体健康状态"""
        with self.lock:
            if not self.health_status:
                return True  # 没有检查项时认为健康

            return all(
                status.get("status") in ["healthy", "warning"]
                for status in self.health_status.values()
            )


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.active_profiles: Dict[str, float] = {}
        self.lock = threading.Lock()

    @contextmanager
    def profile(self, operation: str, tags: Dict[str, str] = None):
        """性能分析上下文管理器"""
        start_time = time.time()
        success = True

        with self.lock:
            self.active_profiles[operation] = start_time

        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time

            with self.lock:
                self.active_profiles.pop(operation, None)

            # 记录性能指标
            self.metrics_collector.record_performance(operation, duration, success)
            self.metrics_collector.record_metric(
                f"performance.{operation}.duration", duration, tags=tags, unit="seconds"
            )

    def get_active_profiles(self) -> Dict[str, float]:
        """获取活跃的性能分析"""
        current_time = time.time()
        with self.lock:
            return {
                operation: current_time - start_time
                for operation, start_time in self.active_profiles.items()
            }


def monitor_performance(operation: str = None, tags: Dict[str, str] = None):
    """性能监控装饰器"""

    def decorator(func):
        op_name = operation or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with _profiler.profile(op_name, tags):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def record_metric(name: str, value: float, tags: Dict[str, str] = None, unit: str = ""):
    """记录指标的便捷函数"""
    _metrics_collector.record_metric(name, value, tags, unit)


def set_custom_metric(name: str, value: float):
    """设置自定义指标的便捷函数"""
    _metrics_collector.set_custom_metric(name, value)


# 全局实例
_metrics_collector = MetricsCollector()
_system_monitor = SystemMonitor(_metrics_collector)
_health_checker = HealthChecker()
_profiler = PerformanceProfiler(_metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器"""
    return _metrics_collector


def get_system_monitor() -> SystemMonitor:
    """获取系统监控器"""
    return _system_monitor


def get_health_checker() -> HealthChecker:
    """获取健康检查器"""
    return _health_checker


def get_profiler() -> PerformanceProfiler:
    """获取性能分析器"""
    return _profiler


# 默认健康检查
def basic_health_check() -> Dict[str, Any]:
    """基础健康检查"""
    try:
        # 检查内存使用率
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return {
                "status": "warning",
                "details": {
                    "memory_usage": f"{memory.percent}%",
                    "message": "High memory usage",
                },
            }

        # 检查磁盘使用率
        disk = psutil.disk_usage("/")
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > 90:
            return {
                "status": "warning",
                "details": {
                    "disk_usage": f"{disk_percent:.1f}%",
                    "message": "High disk usage",
                },
            }

        return {
            "status": "healthy",
            "details": {
                "memory_usage": f"{memory.percent}%",
                "disk_usage": f"{disk_percent:.1f}%",
            },
        }

    except Exception as e:
        return {"status": "error", "details": {"error": str(e)}}


def database_health_check() -> Dict[str, Any]:
    """数据库健康检查"""
    try:
        # 这里应该检查数据库连接
        # 暂时返回健康状态
        return {"status": "healthy", "details": {"connection": "ok"}}
    except Exception as e:
        return {"status": "unhealthy", "details": {"error": str(e)}}


def llm_service_health_check() -> Dict[str, Any]:
    """LLM服务健康检查"""
    try:
        # 这里应该检查LLM服务连接
        # 暂时返回健康状态
        return {"status": "healthy", "details": {"service": "available"}}
    except Exception as e:
        return {"status": "unhealthy", "details": {"error": str(e)}}


# 注册默认健康检查
_health_checker.register_health_check("basic", basic_health_check)
_health_checker.register_health_check("database", database_health_check)
_health_checker.register_health_check("llm_service", llm_service_health_check)


def initialize_monitoring():
    """初始化监控系统"""
    try:
        # 启动系统监控
        _system_monitor.start_monitoring()

        # 运行初始健康检查
        _health_checker.run_health_checks()

        logger.info("Monitoring system initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize monitoring system: {e}")
        return False


def shutdown_monitoring():
    """关闭监控系统"""
    try:
        _system_monitor.stop_monitoring()
        logger.info("Monitoring system shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down monitoring system: {e}")
