"""
外部服务管理器

统一管理所有外部服务，提供服务降级和故障转移策略。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from .config_loader import get_service_config_loader
from .health_monitor import (HealthStatus, ServiceHealthMonitor,
                             get_health_monitor)
from .litellm_service import (LiteLLMConfig, LiteLLMService,
                              initialize_litellm_service)
from .redis_service import RedisConfig, RedisService, initialize_redis_service
from .service_registry import (ServicePriority, ServiceRegistry, ServiceType,
                               get_service_registry)

logger = get_logger("external_service_manager")


class ServiceStatus(Enum):
    """服务状态"""

    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class ServiceFailoverConfig:
    """服务故障转移配置"""

    max_failures: int = 3
    failure_window: int = 300  # 5分钟
    recovery_timeout: int = 60
    enable_auto_recovery: bool = True
    fallback_services: List[str] = field(default_factory=list)


class ExternalServiceManager:
    """外部服务管理器"""

    def __init__(self):
        self.health_monitor = get_health_monitor()
        self.service_registry = get_service_registry()
        self._services: Dict[str, Any] = {}
        self._service_status: Dict[str, ServiceStatus] = {}
        self._failover_configs: Dict[str, ServiceFailoverConfig] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_times: Dict[str, datetime] = {}
        self._recovery_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False

        # 服务状态变更回调
        self._status_change_callbacks: List[
            Callable[[str, ServiceStatus, ServiceStatus], None]
        ] = []

    async def initialize(self):
        """初始化外部服务管理器"""
        if self._initialized:
            logger.warning("外部服务管理器已初始化")
            return

        try:
            config_loader = get_service_config_loader()

            # 初始化LiteLLM服务
            await self._initialize_litellm_service(config_loader)

            # 初始化Redis服务
            await self._initialize_redis_service(config_loader)

            # 启动健康监控
            await self.health_monitor.start_monitoring()

            # 设置故障转移配置
            self._setup_failover_configs()

            # 添加健康状态变更监听
            self.health_monitor.add_alert_callback(self._on_health_status_change)

            self._initialized = True
            logger.info("外部服务管理器初始化完成")

        except Exception as e:
            logger.error(f"初始化外部服务管理器失败: {e}")
            raise

    async def _initialize_litellm_service(self, config_loader):
        """初始化LiteLLM服务"""
        try:
            # 从配置加载器获取LiteLLM配置
            litellm_configs = config_loader.load_litellm_configs()

            if litellm_configs:
                litellm_service = initialize_litellm_service(litellm_configs)
                self._services["litellm"] = litellm_service
                self._service_status["litellm"] = ServiceStatus.ACTIVE
                logger.info(
                    f"LiteLLM服务已初始化，支持提供商: {list(litellm_configs.keys())}"
                )
            else:
                logger.warning("未找到有效的LLM配置，跳过LiteLLM服务初始化")

        except Exception as e:
            logger.error(f"初始化LiteLLM服务失败: {e}")
            self._service_status["litellm"] = ServiceStatus.FAILED

    async def _initialize_redis_service(self, config_loader):
        """初始化Redis服务"""
        try:
            # 从配置加载器获取Redis配置
            redis_config = config_loader.load_redis_config()

            if redis_config:
                redis_service = initialize_redis_service(redis_config)
                self._services["redis"] = redis_service
                self._service_status["redis"] = ServiceStatus.ACTIVE
                logger.info("Redis服务已初始化")
            else:
                logger.warning("未找到Redis配置，跳过Redis服务初始化")

        except Exception as e:
            logger.error(f"初始化Redis服务失败: {e}")
            self._service_status["redis"] = ServiceStatus.FAILED

    def _setup_failover_configs(self):
        """设置故障转移配置"""
        # LiteLLM故障转移配置
        self._failover_configs["litellm"] = ServiceFailoverConfig(
            max_failures=3,
            failure_window=300,
            recovery_timeout=60,
            enable_auto_recovery=True,
        )

        # Redis故障转移配置
        self._failover_configs["redis"] = ServiceFailoverConfig(
            max_failures=5,
            failure_window=300,
            recovery_timeout=30,
            enable_auto_recovery=True,
        )

    async def _on_health_status_change(self, service_name: str, health_result):
        """健康状态变更处理"""
        current_status = self._service_status.get(service_name, ServiceStatus.UNKNOWN)
        new_status = self._health_status_to_service_status(health_result.status)

        if current_status != new_status:
            await self._handle_status_change(service_name, current_status, new_status)

    def _health_status_to_service_status(
        self, health_status: HealthStatus
    ) -> ServiceStatus:
        """将健康状态转换为服务状态"""
        mapping = {
            HealthStatus.HEALTHY: ServiceStatus.ACTIVE,
            HealthStatus.DEGRADED: ServiceStatus.DEGRADED,
            HealthStatus.UNHEALTHY: ServiceStatus.FAILED,
            HealthStatus.UNKNOWN: ServiceStatus.UNKNOWN,
        }
        return mapping.get(health_status, ServiceStatus.UNKNOWN)

    async def _handle_status_change(
        self, service_name: str, old_status: ServiceStatus, new_status: ServiceStatus
    ):
        """处理服务状态变更"""
        self._service_status[service_name] = new_status

        logger.info(
            f"服务状态变更: {service_name} {old_status.value} -> {new_status.value}"
        )

        # 如果服务失败，处理故障转移
        if new_status == ServiceStatus.FAILED:
            await self._handle_service_failure(service_name)

        # 如果服务恢复，清理故障计数
        elif new_status == ServiceStatus.ACTIVE and old_status in [
            ServiceStatus.FAILED,
            ServiceStatus.DEGRADED,
        ]:
            await self._handle_service_recovery(service_name)

        # 通知状态变更回调
        for callback in self._status_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(service_name, old_status, new_status)
                else:
                    callback(service_name, old_status, new_status)
            except Exception as e:
                logger.error(f"执行状态变更回调失败: {e}")

    async def _handle_service_failure(self, service_name: str):
        """处理服务失败"""
        config = self._failover_configs.get(service_name)
        if not config:
            return

        # 更新失败计数
        self._failure_counts[service_name] = (
            self._failure_counts.get(service_name, 0) + 1
        )
        self._last_failure_times[service_name] = datetime.now()

        failure_count = self._failure_counts[service_name]

        logger.warning(
            f"服务失败: {service_name} (失败次数: {failure_count}/{config.max_failures})"
        )

        # 如果失败次数超过阈值，启动故障转移
        if failure_count >= config.max_failures:
            await self._trigger_failover(service_name)

        # 如果启用自动恢复，启动恢复任务
        if config.enable_auto_recovery:
            await self._start_recovery_task(service_name)

    async def _handle_service_recovery(self, service_name: str):
        """处理服务恢复"""
        # 清理失败计数
        self._failure_counts.pop(service_name, None)
        self._last_failure_times.pop(service_name, None)

        # 取消恢复任务
        if service_name in self._recovery_tasks:
            self._recovery_tasks[service_name].cancel()
            del self._recovery_tasks[service_name]

        logger.info(f"服务已恢复: {service_name}")

    async def _trigger_failover(self, service_name: str):
        """触发故障转移"""
        config = self._failover_configs.get(service_name)
        if not config or not config.fallback_services:
            logger.warning(f"服务 {service_name} 无可用的故障转移选项")
            return

        logger.info(f"触发故障转移: {service_name} -> {config.fallback_services}")

        # 这里可以实现具体的故障转移逻辑
        # 例如切换到备用服务、降级功能等

    async def _start_recovery_task(self, service_name: str):
        """启动恢复任务"""
        if service_name in self._recovery_tasks:
            return  # 恢复任务已在运行

        config = self._failover_configs.get(service_name)
        if not config:
            return

        async def recovery_task():
            try:
                await asyncio.sleep(config.recovery_timeout)

                # 尝试恢复服务
                logger.info(f"尝试恢复服务: {service_name}")

                # 这里可以实现具体的恢复逻辑
                # 例如重新初始化服务、重置连接等

            except asyncio.CancelledError:
                logger.debug(f"恢复任务已取消: {service_name}")
            except Exception as e:
                logger.error(f"恢复任务失败 {service_name}: {e}")
            finally:
                self._recovery_tasks.pop(service_name, None)

        self._recovery_tasks[service_name] = asyncio.create_task(recovery_task())

    def get_service(self, service_name: str) -> Optional[Any]:
        """获取服务实例"""
        return self._services.get(service_name)

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """获取服务状态"""
        return self._service_status.get(service_name, ServiceStatus.UNKNOWN)

    def is_service_available(self, service_name: str) -> bool:
        """检查服务是否可用"""
        status = self.get_service_status(service_name)
        return status in [ServiceStatus.ACTIVE, ServiceStatus.DEGRADED]

    def get_available_services(
        self, service_type: Optional[ServiceType] = None
    ) -> List[str]:
        """获取可用服务列表"""
        available_services = []

        for service_name, status in self._service_status.items():
            if status in [ServiceStatus.ACTIVE, ServiceStatus.DEGRADED]:
                if service_type is None:
                    available_services.append(service_name)
                else:
                    # 检查服务类型
                    service_info = self.service_registry.get_service(service_name)
                    if service_info and service_info.service_type == service_type:
                        available_services.append(service_name)

        return available_services

    async def get_healthy_service(self, service_type: ServiceType) -> Optional[Any]:
        """获取健康的服务实例"""
        service_info = await self.service_registry.get_healthy_service(service_type)
        if service_info:
            return self.get_service(service_info.name)
        return None

    async def get_available_service(self, service_type: ServiceType) -> Optional[Any]:
        """获取可用的服务实例"""
        service_info = await self.service_registry.get_available_service(service_type)
        if service_info:
            return self.get_service(service_info.name)
        return None

    def add_status_change_callback(
        self, callback: Callable[[str, ServiceStatus, ServiceStatus], None]
    ):
        """添加状态变更回调"""
        self._status_change_callbacks.append(callback)

    def remove_status_change_callback(
        self, callback: Callable[[str, ServiceStatus, ServiceStatus], None]
    ):
        """移除状态变更回调"""
        if callback in self._status_change_callbacks:
            self._status_change_callbacks.remove(callback)

    async def restart_service(self, service_name: str) -> bool:
        """重启服务"""
        try:
            logger.info(f"重启服务: {service_name}")

            # 这里可以实现具体的重启逻辑
            # 例如重新初始化服务

            if service_name == "litellm":
                config_loader = get_service_config_loader()
                await self._initialize_litellm_service(config_loader)
            elif service_name == "redis":
                config_loader = get_service_config_loader()
                await self._initialize_redis_service(config_loader)

            return True

        except Exception as e:
            logger.error(f"重启服务失败 {service_name}: {e}")
            return False

    async def stop_service(self, service_name: str) -> bool:
        """停止服务"""
        try:
            logger.info(f"停止服务: {service_name}")

            service = self.get_service(service_name)
            if service and hasattr(service, "close"):
                await service.close()

            self._service_status[service_name] = ServiceStatus.DISABLED
            return True

        except Exception as e:
            logger.error(f"停止服务失败 {service_name}: {e}")
            return False

    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        total_services = len(self._services)
        active_services = len(
            [s for s in self._service_status.values() if s == ServiceStatus.ACTIVE]
        )
        failed_services = len(
            [s for s in self._service_status.values() if s == ServiceStatus.FAILED]
        )
        degraded_services = len(
            [s for s in self._service_status.values() if s == ServiceStatus.DEGRADED]
        )

        service_details = {}
        for service_name, status in self._service_status.items():
            service_details[service_name] = {
                "status": status.value,
                "failure_count": self._failure_counts.get(service_name, 0),
                "last_failure": self._last_failure_times.get(service_name),
                "has_recovery_task": service_name in self._recovery_tasks,
            }

        return {
            "initialized": self._initialized,
            "total_services": total_services,
            "active_services": active_services,
            "failed_services": failed_services,
            "degraded_services": degraded_services,
            "disabled_services": total_services
            - active_services
            - failed_services
            - degraded_services,
            "availability_percentage": (
                (active_services / total_services * 100) if total_services > 0 else 0
            ),
            "service_details": service_details,
            "health_summary": self.health_monitor.get_summary(),
            "registry_stats": self.service_registry.get_service_statistics(),
        }

    async def shutdown(self):
        """关闭服务管理器"""
        logger.info("关闭外部服务管理器")

        # 取消所有恢复任务
        for task in self._recovery_tasks.values():
            task.cancel()

        # 等待所有恢复任务完成
        if self._recovery_tasks:
            await asyncio.gather(*self._recovery_tasks.values(), return_exceptions=True)

        # 停止健康监控
        await self.health_monitor.stop_monitoring()

        # 关闭所有服务
        for service_name, service in self._services.items():
            try:
                if hasattr(service, "close"):
                    await service.close()
            except Exception as e:
                logger.error(f"关闭服务失败 {service_name}: {e}")

        self._initialized = False
        logger.info("外部服务管理器已关闭")


# 全局外部服务管理器实例
_external_service_manager: Optional[ExternalServiceManager] = None


def get_external_service_manager() -> ExternalServiceManager:
    """获取全局外部服务管理器实例"""
    global _external_service_manager
    if _external_service_manager is None:
        _external_service_manager = ExternalServiceManager()
    return _external_service_manager


# 默认状态变更回调
async def default_status_change_callback(
    service_name: str, old_status: ServiceStatus, new_status: ServiceStatus
):
    """默认状态变更回调"""
    if new_status == ServiceStatus.FAILED:
        logger.error(
            f"服务状态变更: {service_name} {old_status.value} -> {new_status.value}"
        )
    elif new_status == ServiceStatus.ACTIVE and old_status == ServiceStatus.FAILED:
        logger.info(
            f"服务恢复: {service_name} {old_status.value} -> {new_status.value}"
        )
    else:
        logger.info(
            f"服务状态变更: {service_name} {old_status.value} -> {new_status.value}"
        )


# 注册默认状态变更回调
get_external_service_manager().add_status_change_callback(
    default_status_change_callback
)
