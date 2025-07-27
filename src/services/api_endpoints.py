"""
外部服务API端点

提供外部服务状态和管理的API接口。
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .external_service_manager import get_external_service_manager, ServiceStatus
from .config_loader import get_service_config_loader
from ..config.logging_config import get_logger

logger = get_logger("service_api")

# 创建路由器
router = APIRouter(prefix="/api/services", tags=["外部服务"])


class ServiceStatusResponse(BaseModel):
    """服务状态响应"""

    name: str
    status: str
    health_status: Optional[str] = None
    response_time: Optional[float] = None
    message: Optional[str] = None
    last_check: Optional[str] = None


class ServiceStatisticsResponse(BaseModel):
    """服务统计响应"""

    initialized: bool
    total_services: int
    active_services: int
    failed_services: int
    degraded_services: int
    disabled_services: int
    availability_percentage: float


class HealthSummaryResponse(BaseModel):
    """健康摘要响应"""

    total_services: int
    healthy_services: int
    unhealthy_services: int
    health_percentage: float
    monitoring_active: bool
    check_interval: int


@router.get("/status", response_model=Dict[str, ServiceStatusResponse])
async def get_services_status():
    """获取所有服务状态"""
    try:
        service_manager = get_external_service_manager()

        # 获取服务状态
        service_statuses = {}
        for service_name in ["litellm", "redis"]:
            status = service_manager.get_service_status(service_name)
            health_result = service_manager.health_monitor.get_service_status(
                service_name
            )

            service_statuses[service_name] = ServiceStatusResponse(
                name=service_name,
                status=status.value,
                health_status=health_result.status.value if health_result else None,
                response_time=health_result.response_time if health_result else None,
                message=health_result.message if health_result else None,
                last_check=(
                    health_result.timestamp.isoformat() if health_result else None
                ),
            )

        return service_statuses

    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")


@router.get("/statistics", response_model=ServiceStatisticsResponse)
async def get_services_statistics():
    """获取服务统计信息"""
    try:
        service_manager = get_external_service_manager()
        stats = service_manager.get_service_statistics()

        return ServiceStatisticsResponse(
            initialized=stats["initialized"],
            total_services=stats["total_services"],
            active_services=stats["active_services"],
            failed_services=stats["failed_services"],
            degraded_services=stats["degraded_services"],
            disabled_services=stats["disabled_services"],
            availability_percentage=stats["availability_percentage"],
        )

    except Exception as e:
        logger.error(f"获取服务统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务统计失败: {str(e)}")


@router.get("/health", response_model=HealthSummaryResponse)
async def get_health_summary():
    """获取健康监控摘要"""
    try:
        service_manager = get_external_service_manager()
        summary = service_manager.health_monitor.get_summary()

        return HealthSummaryResponse(
            total_services=summary["total_services"],
            healthy_services=summary["healthy_services"],
            unhealthy_services=summary["unhealthy_services"],
            health_percentage=summary["health_percentage"],
            monitoring_active=summary["monitoring_active"],
            check_interval=summary["check_interval"],
        )

    except Exception as e:
        logger.error(f"获取健康摘要失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康摘要失败: {str(e)}")


@router.get("/config")
async def get_services_config():
    """获取服务配置"""
    try:
        config_loader = get_service_config_loader()
        configs = config_loader.get_all_service_configs()

        # 移除敏感信息
        safe_configs = {}
        for service_name, config in configs.items():
            if service_name == "litellm" and isinstance(config, dict):
                safe_configs[service_name] = {
                    provider: {
                        "provider": cfg.provider,
                        "model": cfg.model,
                        "api_base": cfg.api_base,
                        "temperature": cfg.temperature,
                        "max_tokens": cfg.max_tokens,
                        "timeout": cfg.timeout,
                        "has_api_key": bool(cfg.api_key),
                    }
                    for provider, cfg in config.items()
                }
            elif service_name == "redis" and config:
                safe_configs[service_name] = {
                    "host": config.host,
                    "port": config.port,
                    "db": config.db,
                    "has_password": bool(config.password),
                    "max_connections": config.max_connections,
                    "socket_timeout": config.socket_timeout,
                }
            else:
                safe_configs[service_name] = config

        return safe_configs

    except Exception as e:
        logger.error(f"获取服务配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务配置失败: {str(e)}")


@router.post("/restart/{service_name}")
async def restart_service(service_name: str):
    """重启服务"""
    try:
        service_manager = get_external_service_manager()

        if service_name not in ["litellm", "redis"]:
            raise HTTPException(status_code=400, detail=f"不支持的服务: {service_name}")

        success = await service_manager.restart_service(service_name)

        if success:
            return {"message": f"服务 {service_name} 重启成功"}
        else:
            raise HTTPException(status_code=500, detail=f"服务 {service_name} 重启失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重启服务失败 {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"重启服务失败: {str(e)}")


@router.post("/stop/{service_name}")
async def stop_service(service_name: str):
    """停止服务"""
    try:
        service_manager = get_external_service_manager()

        if service_name not in ["litellm", "redis"]:
            raise HTTPException(status_code=400, detail=f"不支持的服务: {service_name}")

        success = await service_manager.stop_service(service_name)

        if success:
            return {"message": f"服务 {service_name} 停止成功"}
        else:
            raise HTTPException(status_code=500, detail=f"服务 {service_name} 停止失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止服务失败 {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"停止服务失败: {str(e)}")


@router.get("/litellm/providers")
async def get_litellm_providers():
    """获取LiteLLM支持的提供商"""
    try:
        service_manager = get_external_service_manager()
        litellm_service = service_manager.get_service("litellm")

        if not litellm_service:
            raise HTTPException(status_code=404, detail="LiteLLM服务未初始化")

        providers = litellm_service.get_supported_providers()
        return {"providers": providers}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取LiteLLM提供商失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取LiteLLM提供商失败: {str(e)}")


@router.get("/litellm/metrics")
async def get_litellm_metrics():
    """获取LiteLLM指标"""
    try:
        service_manager = get_external_service_manager()
        litellm_service = service_manager.get_service("litellm")

        if not litellm_service:
            raise HTTPException(status_code=404, detail="LiteLLM服务未初始化")

        metrics = litellm_service.get_metrics()

        # 转换为可序列化的格式
        serializable_metrics = {}
        for provider, metric in metrics.items():
            serializable_metrics[provider] = {
                "total_calls": metric.total_calls,
                "successful_calls": metric.successful_calls,
                "failed_calls": metric.failed_calls,
                "success_rate": metric.success_rate,
                "total_tokens": metric.total_tokens,
                "total_cost": metric.total_cost,
                "avg_response_time": metric.avg_response_time,
                "last_call_time": (
                    metric.last_call_time.isoformat() if metric.last_call_time else None
                ),
            }

        return serializable_metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取LiteLLM指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取LiteLLM指标失败: {str(e)}")


@router.get("/redis/metrics")
async def get_redis_metrics():
    """获取Redis指标"""
    try:
        service_manager = get_external_service_manager()
        redis_service = service_manager.get_service("redis")

        if not redis_service:
            raise HTTPException(status_code=404, detail="Redis服务未初始化")

        stats = await redis_service.get_statistics()
        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Redis指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Redis指标失败: {str(e)}")


@router.post("/initialize")
async def initialize_services():
    """初始化所有服务"""
    try:
        service_manager = get_external_service_manager()
        await service_manager.initialize()

        return {"message": "服务初始化完成"}

    except Exception as e:
        logger.error(f"初始化服务失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化服务失败: {str(e)}")


@router.post("/shutdown")
async def shutdown_services():
    """关闭所有服务"""
    try:
        service_manager = get_external_service_manager()
        await service_manager.shutdown()

        return {"message": "服务关闭完成"}

    except Exception as e:
        logger.error(f"关闭服务失败: {e}")
        raise HTTPException(status_code=500, detail=f"关闭服务失败: {str(e)}")


# 导出路由器
__all__ = ["router"]
