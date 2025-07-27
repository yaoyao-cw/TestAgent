"""
服务注册中心

提供统一的服务注册和发现功能，支持服务降级和故障转移策略。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
import logging

from .health_monitor import HealthStatus, HealthCheckResult, get_health_monitor
from ..config.logging_config import get_logger

logger = get_logger("service_registry")


class ServiceType(Enum):
    """服务类型"""

    LLM = "llm"
    CACHE = "cache"
    DATABASE = "database"
    RAG = "rag"
    SANDBOX = "sandbox"
    EXTERNAL = "external"


class ServicePriority(Enum):
    """服务优先级"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


@dataclass
class ServiceInfo:
    """服务信息"""

    name: str
    service_type: ServiceType
    priority: ServicePriority
    endpoint: str
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_config(self, config: Dict[str, Any]):
        """更新配置"""
        self.config.update(config)
        self.last_updated = datetime.now()

    def add_tag(self, tag: str):
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.last_updated = datetime.now()

    def remove_tag(self, tag: str):
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_updated = datetime.now()

    def enable(self):
        """启用服务"""
        self.enabled = True
        self.last_updated = datetime.now()

    def disable(self):
        """禁用服务"""
        self.enabled = False
        self.last_updated = datetime.now()


class ServiceRegistry:
    """服务注册中心"""

    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._type_index: Dict[ServiceType, List[str]] = {}
        self._priority_index: Dict[ServicePriority, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._health_monitor = get_health_monitor()

        # 初始化索引
        for service_type in ServiceType:
            self._type_index[service_type] = []
        for priority in ServicePriority:
            self._priority_index[priority] = []

    def register_service(self, service_info: ServiceInfo) -> bool:
        """注册服务"""
        try:
            service_name = service_info.name

            # 如果服务已存在，更新信息
            if service_name in self._services:
                old_service = self._services[service_name]
                self._remove_from_indexes(old_service)

            # 注册服务
            self._services[service_name] = service_info
            self._add_to_indexes(service_info)

            logger.info(
                f"服务已注册: {service_name} ({service_info.service_type.value})"
            )
            return True

        except Exception as e:
            logger.error(f"注册服务失败 {service_info.name}: {e}")
            return False

    def unregister_service(self, service_name: str) -> bool:
        """注销服务"""
        if service_name not in self._services:
            logger.warning(f"尝试注销不存在的服务: {service_name}")
            return False

        try:
            service_info = self._services[service_name]
            self._remove_from_indexes(service_info)
            del self._services[service_name]

            logger.info(f"服务已注销: {service_name}")
            return True

        except Exception as e:
            logger.error(f"注销服务失败 {service_name}: {e}")
            return False

    def get_service(self, service_name: str) -> Optional[ServiceInfo]:
        """获取服务信息"""
        return self._services.get(service_name)

    def list_services(
        self,
        service_type: Optional[ServiceType] = None,
        priority: Optional[ServicePriority] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True,
    ) -> List[ServiceInfo]:
        """列出服务"""
        services = []

        # 根据类型筛选
        if service_type:
            service_names = self._type_index.get(service_type, [])
        else:
            service_names = list(self._services.keys())

        for service_name in service_names:
            service_info = self._services.get(service_name)
            if not service_info:
                continue

            # 检查是否启用
            if enabled_only and not service_info.enabled:
                continue

            # 检查优先级
            if priority and service_info.priority != priority:
                continue

            # 检查标签
            if tags:
                if not all(tag in service_info.tags for tag in tags):
                    continue

            services.append(service_info)

        # 按优先级排序
        priority_order = {
            ServicePriority.PRIMARY: 0,
            ServicePriority.SECONDARY: 1,
            ServicePriority.FALLBACK: 2,
        }
        services.sort(key=lambda s: priority_order.get(s.priority, 999))

        return services

    def get_primary_service(self, service_type: ServiceType) -> Optional[ServiceInfo]:
        """获取主要服务"""
        services = self.list_services(
            service_type=service_type,
            priority=ServicePriority.PRIMARY,
            enabled_only=True,
        )
        return services[0] if services else None

    def get_fallback_services(self, service_type: ServiceType) -> List[ServiceInfo]:
        """获取备用服务"""
        return self.list_services(
            service_type=service_type,
            priority=ServicePriority.FALLBACK,
            enabled_only=True,
        )

    async def get_healthy_service(
        self, service_type: ServiceType, prefer_primary: bool = True
    ) -> Optional[ServiceInfo]:
        """获取健康的服务"""
        services = self.list_services(service_type=service_type, enabled_only=True)

        if prefer_primary:
            # 优先返回主要服务（如果健康）
            primary_services = [
                s for s in services if s.priority == ServicePriority.PRIMARY
            ]
            for service in primary_services:
                if self._health_monitor.is_service_healthy(service.name):
                    return service

        # 返回任何健康的服务
        for service in services:
            if self._health_monitor.is_service_healthy(service.name):
                return service

        return None

    async def get_available_service(
        self, service_type: ServiceType, prefer_primary: bool = True
    ) -> Optional[ServiceInfo]:
        """获取可用的服务（健康或降级）"""
        services = self.list_services(service_type=service_type, enabled_only=True)

        if prefer_primary:
            # 优先返回主要服务（如果可用）
            primary_services = [
                s for s in services if s.priority == ServicePriority.PRIMARY
            ]
            for service in primary_services:
                if self._health_monitor.is_service_available(service.name):
                    return service

        # 返回任何可用的服务
        for service in services:
            if self._health_monitor.is_service_available(service.name):
                return service

        return None

    def enable_service(self, service_name: str) -> bool:
        """启用服务"""
        service_info = self.get_service(service_name)
        if service_info:
            service_info.enable()
            logger.info(f"服务已启用: {service_name}")
            return True
        return False

    def disable_service(self, service_name: str) -> bool:
        """禁用服务"""
        service_info = self.get_service(service_name)
        if service_info:
            service_info.disable()
            logger.info(f"服务已禁用: {service_name}")
            return True
        return False

    def update_service_config(self, service_name: str, config: Dict[str, Any]) -> bool:
        """更新服务配置"""
        service_info = self.get_service(service_name)
        if service_info:
            service_info.update_config(config)
            logger.info(f"服务配置已更新: {service_name}")
            return True
        return False

    def add_service_tag(self, service_name: str, tag: str) -> bool:
        """添加服务标签"""
        service_info = self.get_service(service_name)
        if service_info:
            service_info.add_tag(tag)
            self._update_tag_index(service_info)
            return True
        return False

    def remove_service_tag(self, service_name: str, tag: str) -> bool:
        """移除服务标签"""
        service_info = self.get_service(service_name)
        if service_info:
            service_info.remove_tag(tag)
            self._update_tag_index(service_info)
            return True
        return False

    def get_services_by_tag(self, tag: str) -> List[ServiceInfo]:
        """根据标签获取服务"""
        service_names = self._tag_index.get(tag, [])
        return [
            self._services[name] for name in service_names if name in self._services
        ]

    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        total_services = len(self._services)
        enabled_services = len([s for s in self._services.values() if s.enabled])

        type_counts = {}
        for service_type in ServiceType:
            type_counts[service_type.value] = len(self._type_index[service_type])

        priority_counts = {}
        for priority in ServicePriority:
            priority_counts[priority.value] = len(self._priority_index[priority])

        # 获取健康状态统计
        healthy_services = len(self._health_monitor.get_healthy_services())
        unhealthy_services = len(self._health_monitor.get_unhealthy_services())

        return {
            "total_services": total_services,
            "enabled_services": enabled_services,
            "disabled_services": total_services - enabled_services,
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "type_distribution": type_counts,
            "priority_distribution": priority_counts,
            "health_percentage": (
                (healthy_services / total_services * 100) if total_services > 0 else 0
            ),
        }

    def _add_to_indexes(self, service_info: ServiceInfo):
        """添加到索引"""
        service_name = service_info.name

        # 类型索引
        if service_name not in self._type_index[service_info.service_type]:
            self._type_index[service_info.service_type].append(service_name)

        # 优先级索引
        if service_name not in self._priority_index[service_info.priority]:
            self._priority_index[service_info.priority].append(service_name)

        # 标签索引
        for tag in service_info.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if service_name not in self._tag_index[tag]:
                self._tag_index[tag].append(service_name)

    def _remove_from_indexes(self, service_info: ServiceInfo):
        """从索引中移除"""
        service_name = service_info.name

        # 类型索引
        if service_name in self._type_index[service_info.service_type]:
            self._type_index[service_info.service_type].remove(service_name)

        # 优先级索引
        if service_name in self._priority_index[service_info.priority]:
            self._priority_index[service_info.priority].remove(service_name)

        # 标签索引
        for tag in service_info.tags:
            if tag in self._tag_index and service_name in self._tag_index[tag]:
                self._tag_index[tag].remove(service_name)
                if not self._tag_index[tag]:  # 如果标签下没有服务了，删除标签
                    del self._tag_index[tag]

    def _update_tag_index(self, service_info: ServiceInfo):
        """更新标签索引"""
        service_name = service_info.name

        # 清理旧的标签索引
        for tag, service_names in self._tag_index.items():
            if service_name in service_names and tag not in service_info.tags:
                service_names.remove(service_name)

        # 添加新的标签索引
        for tag in service_info.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if service_name not in self._tag_index[tag]:
                self._tag_index[tag].append(service_name)


# 全局服务注册中心实例
_service_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """获取全局服务注册中心实例"""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry


def register_service(service_info: ServiceInfo) -> bool:
    """注册服务的便捷函数"""
    registry = get_service_registry()
    return registry.register_service(service_info)


def get_service(service_name: str) -> Optional[ServiceInfo]:
    """获取服务的便捷函数"""
    registry = get_service_registry()
    return registry.get_service(service_name)


def list_services(**kwargs) -> List[ServiceInfo]:
    """列出服务的便捷函数"""
    registry = get_service_registry()
    return registry.list_services(**kwargs)
