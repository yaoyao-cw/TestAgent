#!/usr/bin/env python3
"""
监控和健康检查API路由
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from ...core.monitoring import (
        get_metrics_collector,
        get_system_monitor,
        get_health_checker,
        get_profiler,
    )
    from ...core.error_handler import get_error_handler
    from ...config.logging_config import get_logger
except ImportError as e:
    # 如果导入失败，提供模拟实现
    def get_metrics_collector():
        return None

    def get_system_monitor():
        return None

    def get_health_checker():
        return None

    def get_profiler():
        return None

    def get_error_handler():
        return None

    def get_logger(name):
        import logging

        return logging.getLogger(name)


logger = get_logger("monitoring_api")

router = APIRouter()


# 响应模型
class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="整体健康状态")
    checks: Dict[str, Dict[str, Any]] = Field(..., description="各项检查结果")
    timestamp: str = Field(..., description="检查时间")


class MetricsResponse(BaseModel):
    """指标响应"""

    metrics: List[Dict[str, Any]] = Field(..., description="指标数据")
    count: int = Field(..., description="指标数量")
    timestamp: str = Field(..., description="查询时间")


class PerformanceStatsResponse(BaseModel):
    """性能统计响应"""

    stats: Dict[str, Dict[str, Any]] = Field(..., description="性能统计")
    timestamp: str = Field(..., description="统计时间")


class SystemStatsResponse(BaseModel):
    """系统统计响应"""

    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    process_stats: Dict[str, Any] = Field(..., description="进程统计")
    timestamp: str = Field(..., description="统计时间")


class ErrorStatsResponse(BaseModel):
    """错误统计响应"""

    error_count: Dict[str, int] = Field(..., description="错误计数")
    circuit_breakers: Dict[str, Dict[str, Any]] = Field(..., description="熔断器状态")
    total_errors: int = Field(..., description="总错误数")
    timestamp: str = Field(..., description="统计时间")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """健康检查端点"""
    try:
        health_checker = get_health_checker()
        if not health_checker:
            raise HTTPException(status_code=503, detail="健康检查器不可用")

        # 运行健康检查
        check_results = health_checker.run_health_checks()

        # 确定整体状态
        overall_status = "healthy"
        if any(result.get("status") == "error" for result in check_results.values()):
            overall_status = "error"
        elif any(
            result.get("status") == "unhealthy" for result in check_results.values()
        ):
            overall_status = "unhealthy"
        elif any(
            result.get("status") == "warning" for result in check_results.values()
        ):
            overall_status = "warning"

        return HealthCheckResponse(
            status=overall_status,
            checks=check_results,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/health/{check_name}")
async def specific_health_check(check_name: str):
    """特定健康检查"""
    try:
        health_checker = get_health_checker()
        if not health_checker:
            raise HTTPException(status_code=503, detail="健康检查器不可用")

        # 运行所有检查并返回特定检查结果
        check_results = health_checker.run_health_checks()

        if check_name not in check_results:
            raise HTTPException(
                status_code=404, detail=f"健康检查项不存在: {check_name}"
            )

        return {
            "check_name": check_name,
            "result": check_results[check_name],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"特定健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    name_filter: Optional[str] = Query(None, description="指标名称过滤"),
    limit: int = Query(100, description="返回数量限制", ge=1, le=1000),
):
    """获取系统指标"""
    try:
        metrics_collector = get_metrics_collector()
        if not metrics_collector:
            raise HTTPException(status_code=503, detail="指标收集器不可用")

        # 获取指标数据
        metrics = metrics_collector.get_metrics(name_filter, limit)

        # 转换为字典格式
        metrics_data = []
        for metric in metrics:
            metrics_data.append(
                {
                    "name": metric.name,
                    "value": metric.value,
                    "timestamp": metric.timestamp.isoformat(),
                    "tags": metric.tags,
                    "unit": metric.unit,
                }
            )

        return MetricsResponse(
            metrics=metrics_data,
            count=len(metrics_data),
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取指标失败: {str(e)}")


@router.get("/metrics/custom")
async def get_custom_metrics():
    """获取自定义指标"""
    try:
        metrics_collector = get_metrics_collector()
        if not metrics_collector:
            raise HTTPException(status_code=503, detail="指标收集器不可用")

        custom_metrics = metrics_collector.get_custom_metrics()

        return {
            "custom_metrics": custom_metrics,
            "count": len(custom_metrics),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取自定义指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取自定义指标失败: {str(e)}")


@router.get("/performance", response_model=PerformanceStatsResponse)
async def get_performance_stats(
    operation: Optional[str] = Query(None, description="操作名称过滤")
):
    """获取性能统计"""
    try:
        metrics_collector = get_metrics_collector()
        if not metrics_collector:
            raise HTTPException(status_code=503, detail="指标收集器不可用")

        # 获取性能统计
        stats = metrics_collector.get_performance_stats(operation)

        # 转换为字典格式
        stats_data = {}
        for op_name, stat in stats.items():
            stats_data[op_name] = {
                "total_calls": stat.total_calls,
                "total_time": stat.total_time,
                "min_time": stat.min_time if stat.min_time != float("inf") else 0,
                "max_time": stat.max_time,
                "avg_time": stat.avg_time,
                "error_count": stat.error_count,
                "success_rate": stat.success_rate,
                "last_call_time": (
                    stat.last_call_time.isoformat() if stat.last_call_time else None
                ),
            }

        return PerformanceStatsResponse(
            stats=stats_data, timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能统计失败: {str(e)}")


@router.get("/system", response_model=SystemStatsResponse)
async def get_system_stats():
    """获取系统统计信息"""
    try:
        import psutil

        # CPU使用率
        cpu_usage = psutil.cpu_percent(interval=1)

        # 内存使用情况
        memory = psutil.virtual_memory()

        # 磁盘使用情况
        disk = psutil.disk_usage("/")
        disk_usage = (disk.used / disk.total) * 100

        # 进程信息
        process = psutil.Process()
        process_stats = {
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "memory_rss": process.memory_info().rss,
            "num_threads": process.num_threads(),
            "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
        }

        # 添加文件描述符数量（如果支持）
        try:
            process_stats["num_fds"] = process.num_fds()
        except AttributeError:
            # Windows doesn't support num_fds
            pass

        return SystemStatsResponse(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk_usage,
            process_stats=process_stats,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统统计失败: {str(e)}")


@router.get("/errors", response_model=ErrorStatsResponse)
async def get_error_stats():
    """获取错误统计"""
    try:
        error_handler = get_error_handler()
        if not error_handler:
            raise HTTPException(status_code=503, detail="错误处理器不可用")

        error_stats = error_handler.get_error_stats()

        return ErrorStatsResponse(
            error_count=error_stats["error_count"],
            circuit_breakers=error_stats["circuit_breakers"],
            total_errors=error_stats["total_errors"],
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"获取错误统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取错误统计失败: {str(e)}")


@router.get("/profiler/active")
async def get_active_profiles():
    """获取活跃的性能分析"""
    try:
        profiler = get_profiler()
        if not profiler:
            raise HTTPException(status_code=503, detail="性能分析器不可用")

        active_profiles = profiler.get_active_profiles()

        return {
            "active_profiles": active_profiles,
            "count": len(active_profiles),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取活跃分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取活跃分析失败: {str(e)}")


@router.post("/circuit-breaker/{service}/reset")
async def reset_circuit_breaker(service: str):
    """重置熔断器"""
    try:
        error_handler = get_error_handler()
        if not error_handler:
            raise HTTPException(status_code=503, detail="错误处理器不可用")

        error_handler.reset_circuit_breaker(service)

        return {
            "success": True,
            "message": f"熔断器已重置: {service}",
            "service": service,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"重置熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置熔断器失败: {str(e)}")


@router.delete("/metrics")
async def clear_metrics():
    """清除指标数据"""
    try:
        metrics_collector = get_metrics_collector()
        if not metrics_collector:
            raise HTTPException(status_code=503, detail="指标收集器不可用")

        metrics_collector.clear_metrics()

        return {
            "success": True,
            "message": "指标数据已清除",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"清除指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"清除指标失败: {str(e)}")


@router.get("/status")
async def get_service_status():
    """获取服务整体状态"""
    try:
        # 获取各种状态信息
        health_checker = get_health_checker()
        error_handler = get_error_handler()

        status_info = {
            "service": "TestAgent",
            "version": "1.0.0",  # 应该从配置或版本文件获取
            "uptime": None,  # 可以添加启动时间跟踪
            "timestamp": datetime.now().isoformat(),
        }

        # 健康状态
        if health_checker:
            health_status = health_checker.get_health_status()
            overall_healthy = health_checker.is_healthy()
            status_info["health"] = {
                "overall": "healthy" if overall_healthy else "unhealthy",
                "checks": len(health_status),
                "details": health_status,
            }

        # 错误统计
        if error_handler:
            error_stats = error_handler.get_error_stats()
            status_info["errors"] = {
                "total": error_stats["total_errors"],
                "types": len(error_stats["error_count"]),
                "circuit_breakers": len(error_stats["circuit_breakers"]),
            }

        # 系统资源
        try:
            import psutil

            status_info["resources"] = {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": (
                    psutil.disk_usage("/").used / psutil.disk_usage("/").total
                )
                * 100,
            }
        except:
            pass

        return status_info

    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")
