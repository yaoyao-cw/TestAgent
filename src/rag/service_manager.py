"""RAG服务管理器

支持主服务和降级策略的多RAG服务管理
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..exceptions import RAGServiceException
from .adapters import (ChromaDBAdapter, CustomRAGAdapter, QAnythingAdapter,
                       RAGFlowAdapter)
from .interfaces import (Document, RAGServiceInterface, RAGServiceStatus,
                         SearchResult, ServiceHealthInfo)

logger = get_logger("rag_service_manager")


class ServicePriority(Enum):
    """服务优先级枚举"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


@dataclass
class ServiceConfig:
    """服务配置数据类"""

    name: str
    service_type: str
    priority: ServicePriority
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    health_check_interval: int = 60  # 健康检查间隔（秒）
    max_failures: int = 3  # 最大失败次数
    failure_timeout: int = 300  # 失败后的超时时间（秒）

    def __post_init__(self):
        if isinstance(self.priority, str):
            self.priority = ServicePriority(self.priority)


@dataclass
class ServiceStatus:
    """服务状态数据类"""

    name: str
    adapter: Optional[RAGServiceInterface] = None
    last_health_check: Optional[ServiceHealthInfo] = None
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    is_available: bool = True

    @property
    def is_healthy(self) -> bool:
        """检查服务是否健康"""
        if not self.is_available:
            return False

        if self.last_health_check is None:
            return False

        return self.last_health_check.status == RAGServiceStatus.HEALTHY

    @property
    def should_retry(self) -> bool:
        """检查是否应该重试"""
        if self.is_available:
            return True

        if self.last_failure_time is None:
            return True

        # 检查是否超过了失败超时时间
        timeout_duration = timedelta(seconds=300)  # 默认5分钟
        return datetime.now() - self.last_failure_time > timeout_duration


class RAGServiceManager:
    """RAG服务管理器

    支持多个RAG服务的统一管理，包括：
    - 主服务和降级策略
    - 健康检查和故障转移
    - 动态配置更新和服务重载
    """

    def __init__(self, config: Dict[str, Any] = None):
        """初始化RAG服务管理器

        Args:
            config: 服务配置字典
        """
        self.config = config or {}
        self.services: Dict[str, ServiceStatus] = {}
        self.service_configs: Dict[str, ServiceConfig] = {}

        # 服务优先级列表
        self.primary_services: List[str] = []
        self.secondary_services: List[str] = []
        self.fallback_services: List[str] = []

        # 健康检查任务
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
        self.health_check_running = False

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0

        logger.info("RAG服务管理器初始化完成")

    def add_service(self, service_config: Union[ServiceConfig, Dict[str, Any]]):
        """添加RAG服务

        Args:
            service_config: 服务配置
        """
        if isinstance(service_config, dict):
            service_config = ServiceConfig(**service_config)

        # 创建适配器
        adapter = self._create_adapter(service_config)

        # 创建服务状态
        service_status = ServiceStatus(name=service_config.name, adapter=adapter)

        # 存储配置和状态
        self.service_configs[service_config.name] = service_config
        self.services[service_config.name] = service_status

        # 按优先级分类
        if service_config.priority == ServicePriority.PRIMARY:
            self.primary_services.append(service_config.name)
        elif service_config.priority == ServicePriority.SECONDARY:
            self.secondary_services.append(service_config.name)
        else:
            self.fallback_services.append(service_config.name)

        logger.info(
            f"添加RAG服务: {service_config.name} ({service_config.service_type}, {service_config.priority.value})"
        )

    def _create_adapter(self, service_config: ServiceConfig) -> RAGServiceInterface:
        """创建服务适配器

        Args:
            service_config: 服务配置

        Returns:
            RAGServiceInterface: 服务适配器实例
        """
        adapter_classes = {
            "chromadb": ChromaDBAdapter,
            "ragflow": RAGFlowAdapter,
            "qanything": QAnythingAdapter,
            "custom": CustomRAGAdapter,
            "custom_rag": CustomRAGAdapter,
        }

        adapter_class = adapter_classes.get(service_config.service_type.lower())
        if not adapter_class:
            raise RAGServiceException(
                f"不支持的RAG服务类型: {service_config.service_type}"
            )

        return adapter_class(service_config.name, service_config.config)

    async def initialize_all_services(self) -> Dict[str, bool]:
        """初始化所有服务

        Returns:
            Dict[str, bool]: 各服务初始化结果
        """
        results = {}

        for service_name, service_status in self.services.items():
            try:
                if service_status.adapter and not service_status.adapter.is_initialized:
                    success = await service_status.adapter.initialize()
                    results[service_name] = success

                    if not success:
                        service_status.is_available = False
                        service_status.failure_count += 1
                        service_status.last_failure_time = datetime.now()
                        logger.error(f"服务 {service_name} 初始化失败")
                    else:
                        logger.info(f"服务 {service_name} 初始化成功")
                else:
                    results[service_name] = True

            except Exception as e:
                results[service_name] = False
                service_status.is_available = False
                service_status.failure_count += 1
                service_status.last_failure_time = datetime.now()
                logger.error(f"服务 {service_name} 初始化异常: {e}")

        # 启动健康检查
        await self.start_health_checks()

        return results

    async def start_health_checks(self):
        """启动健康检查任务"""
        if self.health_check_running:
            return

        self.health_check_running = True

        for service_name, service_config in self.service_configs.items():
            if service_config.enabled:
                task = asyncio.create_task(
                    self._health_check_loop(
                        service_name, service_config.health_check_interval
                    )
                )
                self.health_check_tasks[service_name] = task

        logger.info("健康检查任务已启动")

    async def stop_health_checks(self):
        """停止健康检查任务"""
        self.health_check_running = False

        for task in self.health_check_tasks.values():
            task.cancel()

        # 等待所有任务完成
        if self.health_check_tasks:
            await asyncio.gather(
                *self.health_check_tasks.values(), return_exceptions=True
            )

        self.health_check_tasks.clear()
        logger.info("健康检查任务已停止")

    async def _health_check_loop(self, service_name: str, interval: int):
        """健康检查循环

        Args:
            service_name: 服务名称
            interval: 检查间隔（秒）
        """
        while self.health_check_running:
            try:
                await self._perform_health_check(service_name)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"服务 {service_name} 健康检查异常: {e}")
                await asyncio.sleep(interval)

    async def _perform_health_check(self, service_name: str):
        """执行健康检查

        Args:
            service_name: 服务名称
        """
        service_status = self.services.get(service_name)
        if not service_status or not service_status.adapter:
            return

        try:
            health_info = await service_status.adapter.health_check()
            service_status.last_health_check = health_info

            if health_info.status == RAGServiceStatus.HEALTHY:
                # 服务恢复健康
                if not service_status.is_available:
                    logger.info(f"服务 {service_name} 已恢复健康")
                    service_status.is_available = True
                    service_status.failure_count = 0
                    service_status.last_failure_time = None
            else:
                # 服务不健康
                service_status.failure_count += 1
                service_status.last_failure_time = datetime.now()

                service_config = self.service_configs[service_name]
                if service_status.failure_count >= service_config.max_failures:
                    service_status.is_available = False
                    logger.warning(
                        f"服务 {service_name} 标记为不可用，失败次数: {service_status.failure_count}"
                    )

        except Exception as e:
            service_status.failure_count += 1
            service_status.last_failure_time = datetime.now()

            service_config = self.service_configs[service_name]
            if service_status.failure_count >= service_config.max_failures:
                service_status.is_available = False
                logger.warning(f"服务 {service_name} 健康检查失败，标记为不可用: {e}")

    def _get_available_services(self) -> List[str]:
        """获取可用服务列表（按优先级排序）

        Returns:
            List[str]: 可用服务名称列表
        """
        available_services = []

        # 按优先级顺序检查服务
        for service_list in [
            self.primary_services,
            self.secondary_services,
            self.fallback_services,
        ]:
            for service_name in service_list:
                service_status = self.services.get(service_name)
                service_config = self.service_configs.get(service_name)

                if (
                    service_status
                    and service_config
                    and service_config.enabled
                    and (service_status.is_available or service_status.should_retry)
                ):
                    available_services.append(service_name)

        return available_services

    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档（支持降级策略）

        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: 其他查询参数

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        self.request_count += 1
        available_services = self._get_available_services()

        if not available_services:
            self.failure_count += 1
            raise RAGServiceException("没有可用的RAG服务")

        last_error = None

        for service_name in available_services:
            service_status = self.services[service_name]

            try:
                if service_status.adapter:
                    results = await service_status.adapter.retrieve(
                        query, top_k, **kwargs
                    )
                    self.success_count += 1

                    # 在结果中标记服务来源
                    for result in results:
                        result.document.metadata["rag_service"] = service_name

                    logger.info(
                        f"使用服务 {service_name} 检索成功，返回 {len(results)} 个结果"
                    )
                    return results

            except Exception as e:
                last_error = e
                logger.warning(f"服务 {service_name} 检索失败，尝试下一个服务: {e}")

                # 更新失败统计
                service_status.failure_count += 1
                service_status.last_failure_time = datetime.now()

                continue

        # 所有服务都失败了
        self.failure_count += 1
        raise RAGServiceException(f"所有RAG服务都不可用，最后错误: {last_error}")

    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库（支持降级策略）

        Args:
            document: 要添加的文档
            **kwargs: 其他参数

        Returns:
            str: 文档ID
        """
        self.request_count += 1
        available_services = self._get_available_services()

        if not available_services:
            self.failure_count += 1
            raise RAGServiceException("没有可用的RAG服务")

        last_error = None

        for service_name in available_services:
            service_status = self.services[service_name]

            try:
                if service_status.adapter:
                    document_id = await service_status.adapter.add_document(
                        document, **kwargs
                    )
                    self.success_count += 1
                    logger.info(f"使用服务 {service_name} 添加文档成功: {document_id}")
                    return document_id

            except Exception as e:
                last_error = e
                logger.warning(f"服务 {service_name} 添加文档失败，尝试下一个服务: {e}")

                # 更新失败统计
                service_status.failure_count += 1
                service_status.last_failure_time = datetime.now()

                continue

        # 所有服务都失败了
        self.failure_count += 1
        raise RAGServiceException(f"所有RAG服务都不可用，最后错误: {last_error}")

    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库（支持降级策略）

        Args:
            documents: 要添加的文档列表
            **kwargs: 其他参数

        Returns:
            List[str]: 文档ID列表
        """
        self.request_count += 1
        available_services = self._get_available_services()

        if not available_services:
            self.failure_count += 1
            raise RAGServiceException("没有可用的RAG服务")

        last_error = None

        for service_name in available_services:
            service_status = self.services[service_name]

            try:
                if service_status.adapter:
                    document_ids = await service_status.adapter.add_documents(
                        documents, **kwargs
                    )
                    self.success_count += 1
                    logger.info(
                        f"使用服务 {service_name} 批量添加 {len(documents)} 个文档成功"
                    )
                    return document_ids

            except Exception as e:
                last_error = e
                logger.warning(
                    f"服务 {service_name} 批量添加文档失败，尝试下一个服务: {e}"
                )

                # 更新失败统计
                service_status.failure_count += 1
                service_status.last_failure_time = datetime.now()

                continue

        # 所有服务都失败了
        self.failure_count += 1
        raise RAGServiceException(f"所有RAG服务都不可用，最后错误: {last_error}")

    def get_service_status(
        self, service_name: str = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """获取服务状态

        Args:
            service_name: 服务名称，如果为None则返回所有服务状态

        Returns:
            服务状态信息
        """
        if service_name:
            service_status = self.services.get(service_name)
            service_config = self.service_configs.get(service_name)

            if not service_status or not service_config:
                return {"error": f"服务 {service_name} 不存在"}

            return {
                "name": service_name,
                "type": service_config.service_type,
                "priority": service_config.priority.value,
                "enabled": service_config.enabled,
                "available": service_status.is_available,
                "healthy": service_status.is_healthy,
                "failure_count": service_status.failure_count,
                "last_failure_time": (
                    service_status.last_failure_time.isoformat()
                    if service_status.last_failure_time
                    else None
                ),
                "last_health_check": (
                    service_status.last_health_check.__dict__
                    if service_status.last_health_check
                    else None
                ),
            }
        else:
            # 返回所有服务状态
            all_status = []
            for name in self.services.keys():
                all_status.append(self.get_service_status(name))
            return all_status

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        available_count = sum(1 for s in self.services.values() if s.is_available)
        healthy_count = sum(1 for s in self.services.values() if s.is_healthy)

        return {
            "total_services": len(self.services),
            "available_services": available_count,
            "healthy_services": healthy_count,
            "primary_services": len(self.primary_services),
            "secondary_services": len(self.secondary_services),
            "fallback_services": len(self.fallback_services),
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.failure_count,
            "success_rate": self.success_count / max(self.request_count, 1) * 100,
            "health_check_running": self.health_check_running,
        }

    async def reload_service(
        self, service_name: str, new_config: Dict[str, Any] = None
    ) -> bool:
        """重载服务

        Args:
            service_name: 服务名称
            new_config: 新配置（可选）

        Returns:
            bool: 重载是否成功
        """
        if service_name not in self.services:
            logger.error(f"服务 {service_name} 不存在")
            return False

        try:
            # 停止健康检查
            if service_name in self.health_check_tasks:
                self.health_check_tasks[service_name].cancel()
                del self.health_check_tasks[service_name]

            # 更新配置
            if new_config:
                service_config = self.service_configs[service_name]
                service_config.config.update(new_config)

            # 重新创建适配器
            service_config = self.service_configs[service_name]
            new_adapter = self._create_adapter(service_config)

            # 初始化新适配器
            success = await new_adapter.initialize()

            if success:
                # 更新服务状态
                service_status = self.services[service_name]
                service_status.adapter = new_adapter
                service_status.is_available = True
                service_status.failure_count = 0
                service_status.last_failure_time = None

                # 重启健康检查
                if service_config.enabled:
                    task = asyncio.create_task(
                        self._health_check_loop(
                            service_name, service_config.health_check_interval
                        )
                    )
                    self.health_check_tasks[service_name] = task

                logger.info(f"服务 {service_name} 重载成功")
                return True
            else:
                logger.error(f"服务 {service_name} 重载失败：初始化失败")
                return False

        except Exception as e:
            logger.error(f"服务 {service_name} 重载异常: {e}")
            return False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize_all_services()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop_health_checks()
