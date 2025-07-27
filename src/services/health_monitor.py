"""
服务健康检查和监控系统

实现所有外部服务的健康检查机制，创建服务可用性监控和告警系统，
建立服务降级和故障转移策略。
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..config.logging_config import get_logger

logger = get_logger("health_monitor")


class HealthStatus(Enum):
    """健康状态枚举"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    service_name: str
    status: HealthStatus
    response_time: float
    timestamp: datetime
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """是否健康"""
        return self.status == HealthStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """是否可用（健康或降级）"""
        return self.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]


@dataclass
class ServiceMetrics:
    """服务指标"""

    service_name: str
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    avg_response_time: float = 0.0
    last_check_time: Optional[datetime] = None
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100

    def update_metrics(self, result: HealthCheckResult):
        """更新指标"""
        self.total_checks += 1
        self.last_check_time = result.timestamp

        if result.is_healthy:
            self.successful_checks += 1
            self.consecutive_failures = 0
        else:
            self.failed_checks += 1
            self.consecutive_failures += 1
            self.last_failure_time = result.timestamp

        # 更新平均响应时间
        if self.total_checks == 1:
            self.avg_response_time = result.response_time
        else:
            self.avg_response_time = (
                self.avg_response_time * (self.total_checks - 1) + result.response_time
            ) / self.total_checks

        # 更新正常运行时间百分比
        self.uptime_percentage = self.success_rate


class HealthChecker(ABC):
    """健康检查器抽象基类"""

    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """执行健康检查"""
        pass


class ServiceHealthMonitor:
    """服务健康监控器"""

    def __init__(self, check_interval: int = 30, timeout: int = 10):
        self.check_interval = check_interval
        self.timeout = timeout
        self._checkers: Dict[str, HealthChecker] = {}
        self._metrics: Dict[str, ServiceMetrics] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable[[str, HealthCheckResult], None]] = []
        self._executor = ThreadPoolExecutor(max_workers=10)

    def register_checker(self, service_name: str, checker: HealthChecker):
        """注册健康检查器"""
        self._checkers[service_name] = checker
        self._metrics[service_name] = ServiceMetrics(service_name)
        logger.info(f"已注册健康检查器: {service_name}")

    def unregister_checker(self, service_name: str):
        """注销健康检查器"""
        if service_name in self._checkers:
            del self._checkers[service_name]
            logger.info(f"已注销健康检查器: {service_name}")

    def add_alert_callback(self, callback: Callable[[str, HealthCheckResult], None]):
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    async def check_service(self, service_name: str) -> Optional[HealthCheckResult]:
        """检查单个服务健康状态"""
        if service_name not in self._checkers:
            logger.warning(f"服务 {service_name} 未注册健康检查器")
            return None

        checker = self._checkers[service_name]
        start_time = time.time()

        try:
            # 使用超时执行健康检查
            result = await asyncio.wait_for(
                checker.check_health(), timeout=self.timeout
            )

            # 更新指标
            self._metrics[service_name].update_metrics(result)
            self._last_results[service_name] = result

            # 如果状态变为不健康，触发告警
            if not result.is_healthy:
                await self._trigger_alerts(service_name, result)

            return result

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                message=f"健康检查超时 ({self.timeout}s)",
            )

            self._metrics[service_name].update_metrics(result)
            self._last_results[service_name] = result
            await self._trigger_alerts(service_name, result)

            return result

        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=datetime.now(),
                message=f"健康检查失败: {str(e)}",
            )

            self._metrics[service_name].update_metrics(result)
            self._last_results[service_name] = result
            await self._trigger_alerts(service_name, result)

            logger.error(f"服务 {service_name} 健康检查失败: {e}")
            return result

    async def check_all_services(self) -> Dict[str, HealthCheckResult]:
        """检查所有服务健康状态"""
        results = {}

        # 并发执行所有健康检查
        tasks = []
        for service_name in self._checkers.keys():
            task = asyncio.create_task(self.check_service(service_name))
            tasks.append((service_name, task))

        # 等待所有检查完成
        for service_name, task in tasks:
            try:
                result = await task
                if result:
                    results[service_name] = result
            except Exception as e:
                logger.error(f"检查服务 {service_name} 时发生错误: {e}")

        return results

    def get_service_status(self, service_name: str) -> Optional[HealthCheckResult]:
        """获取服务最新状态"""
        return self._last_results.get(service_name)

    def get_service_metrics(self, service_name: str) -> Optional[ServiceMetrics]:
        """获取服务指标"""
        return self._metrics.get(service_name)

    def get_all_statuses(self) -> Dict[str, HealthCheckResult]:
        """获取所有服务状态"""
        return self._last_results.copy()

    def get_all_metrics(self) -> Dict[str, ServiceMetrics]:
        """获取所有服务指标"""
        return self._metrics.copy()

    def is_service_healthy(self, service_name: str) -> bool:
        """检查服务是否健康"""
        result = self.get_service_status(service_name)
        return result.is_healthy if result else False

    def is_service_available(self, service_name: str) -> bool:
        """检查服务是否可用"""
        result = self.get_service_status(service_name)
        return result.is_available if result else False

    def get_healthy_services(self) -> List[str]:
        """获取健康的服务列表"""
        healthy_services = []
        for service_name, result in self._last_results.items():
            if result.is_healthy:
                healthy_services.append(service_name)
        return healthy_services

    def get_unhealthy_services(self) -> List[str]:
        """获取不健康的服务列表"""
        unhealthy_services = []
        for service_name, result in self._last_results.items():
            if not result.is_healthy:
                unhealthy_services.append(service_name)
        return unhealthy_services

    async def start_monitoring(self):
        """开始监控"""
        if self._running:
            logger.warning("健康监控已在运行")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"健康监控已启动，检查间隔: {self.check_interval}秒")

    async def stop_monitoring(self):
        """停止监控"""
        if not self._running:
            return

        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        self._executor.shutdown(wait=True)
        logger.info("健康监控已停止")

    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环发生错误: {e}")
                await asyncio.sleep(5)  # 错误后短暂等待

    async def _trigger_alerts(self, service_name: str, result: HealthCheckResult):
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(service_name, result)
                else:
                    # 在线程池中执行同步回调
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        self._executor, callback, service_name, result
                    )
            except Exception as e:
                logger.error(f"执行告警回调时发生错误: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        total_services = len(self._checkers)
        healthy_services = len(self.get_healthy_services())
        unhealthy_services = len(self.get_unhealthy_services())

        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "health_percentage": (
                (healthy_services / total_services * 100) if total_services > 0 else 0
            ),
            "monitoring_active": self._running,
            "check_interval": self.check_interval,
            "last_check_time": max(
                (result.timestamp for result in self._last_results.values()),
                default=None,
            ),
        }


# 全局健康监控器实例
_health_monitor: Optional[ServiceHealthMonitor] = None


def get_health_monitor() -> ServiceHealthMonitor:
    """获取全局健康监控器实例"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = ServiceHealthMonitor()
    return _health_monitor


async def check_service_health(service_name: str) -> Optional[HealthCheckResult]:
    """检查服务健康状态的便捷函数"""
    monitor = get_health_monitor()
    return await monitor.check_service(service_name)


def register_health_check(service_name: str, checker: HealthChecker):
    """注册健康检查的便捷函数"""
    monitor = get_health_monitor()
    monitor.register_checker(service_name, checker)


# 默认告警回调
async def default_alert_callback(service_name: str, result: HealthCheckResult):
    """默认告警回调"""
    if result.status == HealthStatus.UNHEALTHY:
        logger.error(f"服务告警: {service_name} 不健康 - {result.message}")
    elif result.status == HealthStatus.DEGRADED:
        logger.warning(f"服务告警: {service_name} 性能降级 - {result.message}")


# 注册默认告警回调
get_health_monitor().add_alert_callback(default_alert_callback)
