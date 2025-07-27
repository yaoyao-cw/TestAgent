"""
外部服务集成模块

提供统一的外部服务接入和管理功能，包括：
- LiteLLM统一接口
- Redis缓存服务
- 服务健康检查和监控
- 服务降级和故障转移
"""

from .health_monitor import (
    HealthStatus,
    ServiceHealthMonitor,
    get_health_monitor,
    check_service_health,
    register_health_check,
)

from .service_registry import (
    ServiceInfo,
    ServiceRegistry,
    get_service_registry,
    register_service,
    get_service,
    list_services,
)

from .litellm_service import LiteLLMService, get_litellm_service, LiteLLMConfig

from .redis_service import RedisService, get_redis_service, RedisConfig

from .external_service_manager import (
    ExternalServiceManager,
    get_external_service_manager,
    ServiceStatus,
)

from .config_loader import ServiceConfigLoader, get_service_config_loader

from .startup import (
    initialize_external_services,
    shutdown_external_services,
    startup,
    shutdown,
)

__all__ = [
    # 健康监控
    "HealthStatus",
    "ServiceHealthMonitor",
    "get_health_monitor",
    "check_service_health",
    "register_health_check",
    # 服务注册
    "ServiceInfo",
    "ServiceRegistry",
    "get_service_registry",
    "register_service",
    "get_service",
    "list_services",
    # LiteLLM服务
    "LiteLLMService",
    "get_litellm_service",
    "LiteLLMConfig",
    # Redis服务
    "RedisService",
    "get_redis_service",
    "RedisConfig",
    # 外部服务管理
    "ExternalServiceManager",
    "get_external_service_manager",
    "ServiceStatus",
    # 配置加载
    "ServiceConfigLoader",
    "get_service_config_loader",
    # 启动和关闭
    "initialize_external_services",
    "shutdown_external_services",
    "startup",
    "shutdown",
]
