#!/usr/bin/env python3
"""
系统管理API路由
"""

import os
import psutil
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from ...config.settings import get_settings
from ...config.logging_config import get_logger
from ...graph.workflow_manager import get_workflow_manager
from ...tools.tool_manager import get_tool_manager
from ...mcp.server_manager import get_mcp_manager

logger = get_logger("system_api")

router = APIRouter()


# 请求和响应模型
class SystemStatus(BaseModel):
    """系统状态"""

    status: str = Field(..., description="系统状态")
    version: str = Field(..., description="版本号")
    uptime: float = Field(..., description="运行时间（秒）")
    timestamp: str = Field(..., description="时间戳")


class ComponentStatus(BaseModel):
    """组件状态"""

    name: str = Field(..., description="组件名称")
    status: str = Field(..., description="状态")
    healthy: bool = Field(..., description="是否健康")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")
    last_check: str = Field(..., description="最后检查时间")


class SystemResources(BaseModel):
    """系统资源"""

    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    network_io: Dict[str, int] = Field(..., description="网络IO")
    process_count: int = Field(..., description="进程数量")


class ExecutionStats(BaseModel):
    """执行统计"""

    total_tasks: int = Field(..., description="总任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    pending_tasks: int = Field(..., description="待处理任务数")
    running_tasks: int = Field(..., description="运行中任务数")
    average_execution_time: float = Field(..., description="平均执行时间")


class SystemHealthResponse(BaseModel):
    """系统健康响应"""

    system: SystemStatus = Field(..., description="系统状态")
    components: List[ComponentStatus] = Field(..., description="组件状态")
    resources: SystemResources = Field(..., description="系统资源")
    execution_stats: ExecutionStats = Field(..., description="执行统计")


class CleanupRequest(BaseModel):
    """清理请求"""

    older_than_days: int = Field(30, description="清理多少天前的数据")
    include_completed: bool = Field(False, description="是否包括已完成的任务")
    include_logs: bool = Field(True, description="是否包括日志文件")
    include_cache: bool = Field(True, description="是否包括缓存")


class CleanupResponse(BaseModel):
    """清理响应"""

    message: str = Field(..., description="清理消息")
    cleaned_items: Dict[str, int] = Field(..., description="清理的项目数量")
    freed_space: int = Field(..., description="释放的空间（字节）")


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""

    config_key: str = Field(..., description="配置键")
    config_value: Any = Field(..., description="配置值")
    restart_required: bool = Field(False, description="是否需要重启")


# 系统启动时间
_start_time = datetime.now()


# 依赖注入
async def get_workflow_manager_dep():
    """获取工作流管理器依赖"""
    return get_workflow_manager()


async def get_tool_manager_dep():
    """获取工具管理器依赖"""
    return get_tool_manager()


async def get_mcp_manager_dep():
    """获取MCP管理器依赖"""
    try:
        return get_mcp_manager()
    except Exception:
        return None


@router.get("/status", response_model=SystemHealthResponse)
async def get_system_status(
    workflow_manager=Depends(get_workflow_manager_dep),
    tool_manager=Depends(get_tool_manager_dep),
    mcp_manager=Depends(get_mcp_manager_dep),
):
    """获取系统状态"""
    try:
        # 系统基本状态
        uptime = (datetime.now() - _start_time).total_seconds()
        system_status = SystemStatus(
            status="healthy",
            version="1.0.0",
            uptime=uptime,
            timestamp=datetime.now().isoformat(),
        )

        # 组件状态检查
        components = []

        # 检查工作流管理器
        try:
            workflow_status = workflow_manager.get_workflow_status()
            components.append(
                ComponentStatus(
                    name="workflow_manager",
                    status=workflow_status.get("status", "unknown"),
                    healthy=workflow_status.get("status") == "ready",
                    details=workflow_status,
                    last_check=datetime.now().isoformat(),
                )
            )
        except Exception as e:
            components.append(
                ComponentStatus(
                    name="workflow_manager",
                    status="error",
                    healthy=False,
                    details={"error": str(e)},
                    last_check=datetime.now().isoformat(),
                )
            )

        # 检查工具管理器
        try:
            tool_health = await tool_manager.health_check()
            components.append(
                ComponentStatus(
                    name="tool_manager",
                    status="healthy" if tool_health["healthy"] else "unhealthy",
                    healthy=tool_health["healthy"],
                    details=tool_health,
                    last_check=datetime.now().isoformat(),
                )
            )
        except Exception as e:
            components.append(
                ComponentStatus(
                    name="tool_manager",
                    status="error",
                    healthy=False,
                    details={"error": str(e)},
                    last_check=datetime.now().isoformat(),
                )
            )

        # 检查MCP管理器
        if mcp_manager:
            try:
                mcp_status = mcp_manager.get_all_servers_status()
                healthy_servers = sum(
                    1
                    for status in mcp_status.values()
                    if status.get("connected", False)
                )
                components.append(
                    ComponentStatus(
                        name="mcp_manager",
                        status="healthy" if healthy_servers > 0 else "degraded",
                        healthy=healthy_servers > 0,
                        details={
                            "total_servers": len(mcp_status),
                            "healthy_servers": healthy_servers,
                            "servers": mcp_status,
                        },
                        last_check=datetime.now().isoformat(),
                    )
                )
            except Exception as e:
                components.append(
                    ComponentStatus(
                        name="mcp_manager",
                        status="error",
                        healthy=False,
                        details={"error": str(e)},
                        last_check=datetime.now().isoformat(),
                    )
                )
        else:
            components.append(
                ComponentStatus(
                    name="mcp_manager",
                    status="disabled",
                    healthy=True,
                    details={"message": "MCP管理器未启用"},
                    last_check=datetime.now().isoformat(),
                )
            )

        # 系统资源
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        network = psutil.net_io_counters()

        resources = SystemResources(
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=(disk.used / disk.total) * 100,
            network_io={
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
            },
            process_count=len(psutil.pids()),
        )

        # 执行统计
        try:
            executions = workflow_manager.list_executions()
            total_tasks = len(executions)
            completed_tasks = sum(
                1 for e in executions if e.get("status") == "completed"
            )
            failed_tasks = sum(1 for e in executions if e.get("status") == "failed")
            pending_tasks = sum(1 for e in executions if e.get("status") == "pending")
            running_tasks = sum(1 for e in executions if e.get("status") == "running")

            # 计算平均执行时间
            completed_executions = [
                e
                for e in executions
                if e.get("status") == "completed" and e.get("duration_seconds")
            ]
            avg_time = (
                sum(e["duration_seconds"] for e in completed_executions)
                / len(completed_executions)
                if completed_executions
                else 0
            )

            execution_stats = ExecutionStats(
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                pending_tasks=pending_tasks,
                running_tasks=running_tasks,
                average_execution_time=avg_time,
            )
        except Exception as e:
            logger.error(f"获取执行统计失败: {e}")
            execution_stats = ExecutionStats(
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                pending_tasks=0,
                running_tasks=0,
                average_execution_time=0,
            )

        # 检查整体健康状态
        unhealthy_components = [c for c in components if not c.healthy]
        if unhealthy_components:
            system_status.status = (
                "degraded"
                if len(unhealthy_components) < len(components)
                else "unhealthy"
            )

        return SystemHealthResponse(
            system=system_status,
            components=components,
            resources=resources,
            execution_stats=execution_stats,
        )

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_system(
    request: CleanupRequest, workflow_manager=Depends(get_workflow_manager_dep)
):
    """清理系统"""
    try:
        cleaned_items = {}
        freed_space = 0

        # 清理过期任务
        if request.older_than_days > 0:
            cutoff_date = datetime.now() - timedelta(days=request.older_than_days)

            # 获取需要清理的执行
            executions = workflow_manager.list_executions()
            old_executions = []

            for execution in executions:
                try:
                    start_time = datetime.fromisoformat(execution.get("start_time", ""))
                    if start_time < cutoff_date:
                        # 检查是否包括已完成的任务
                        if (
                            request.include_completed
                            or execution.get("status") != "completed"
                        ):
                            old_executions.append(execution["execution_id"])
                except Exception:
                    continue

            # 删除旧执行
            for execution_id in old_executions:
                try:
                    workflow_manager.delete_execution(execution_id)
                except Exception as e:
                    logger.warning(f"删除执行失败 {execution_id}: {e}")

            cleaned_items["tasks"] = len(old_executions)

        # 清理日志文件
        if request.include_logs:
            log_dir = "logs"
            if os.path.exists(log_dir):
                log_files_cleaned = 0
                for filename in os.listdir(log_dir):
                    file_path = os.path.join(log_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            file_time = datetime.fromtimestamp(
                                os.path.getmtime(file_path)
                            )
                            if file_time < datetime.now() - timedelta(
                                days=request.older_than_days
                            ):
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                freed_space += file_size
                                log_files_cleaned += 1
                        except Exception as e:
                            logger.warning(f"删除日志文件失败 {file_path}: {e}")

                cleaned_items["log_files"] = log_files_cleaned

        # 清理缓存
        if request.include_cache:
            cache_dir = "data/cache"
            if os.path.exists(cache_dir):
                cache_files_cleaned = 0
                for root, dirs, files in os.walk(cache_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            file_time = datetime.fromtimestamp(
                                os.path.getmtime(file_path)
                            )
                            if file_time < datetime.now() - timedelta(
                                days=request.older_than_days
                            ):
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                freed_space += file_size
                                cache_files_cleaned += 1
                        except Exception as e:
                            logger.warning(f"删除缓存文件失败 {file_path}: {e}")

                cleaned_items["cache_files"] = cache_files_cleaned

        logger.info(f"系统清理完成: {cleaned_items}, 释放空间: {freed_space} 字节")

        return CleanupResponse(
            message="系统清理完成", cleaned_items=cleaned_items, freed_space=freed_space
        )

    except Exception as e:
        logger.error(f"系统清理失败: {e}")
        raise HTTPException(status_code=500, detail=f"系统清理失败: {str(e)}")


@router.get("/metrics")
async def get_system_metrics(
    hours: int = Query(24, description="获取多少小时的指标"),
    workflow_manager=Depends(get_workflow_manager_dep),
):
    """获取系统指标"""
    try:
        # 获取时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # 获取执行历史
        executions = workflow_manager.list_executions()

        # 过滤时间范围内的执行
        filtered_executions = []
        for execution in executions:
            try:
                exec_time = datetime.fromisoformat(execution.get("start_time", ""))
                if start_time <= exec_time <= end_time:
                    filtered_executions.append(execution)
            except Exception:
                continue

        # 计算指标
        metrics = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours,
            },
            "execution_metrics": {
                "total_executions": len(filtered_executions),
                "completed": sum(
                    1 for e in filtered_executions if e.get("status") == "completed"
                ),
                "failed": sum(
                    1 for e in filtered_executions if e.get("status") == "failed"
                ),
                "success_rate": 0,
            },
            "performance_metrics": {
                "average_execution_time": 0,
                "min_execution_time": 0,
                "max_execution_time": 0,
                "total_execution_time": 0,
            },
            "resource_metrics": {
                "current_cpu": psutil.cpu_percent(),
                "current_memory": psutil.virtual_memory().percent,
                "current_disk": (lambda d: (d.used / d.total) * 100)(
                    psutil.disk_usage("/")
                ),
            },
        }

        # 计算成功率
        if metrics["execution_metrics"]["total_executions"] > 0:
            metrics["execution_metrics"]["success_rate"] = (
                metrics["execution_metrics"]["completed"]
                / metrics["execution_metrics"]["total_executions"]
            ) * 100

        # 计算性能指标
        completed_executions = [
            e
            for e in filtered_executions
            if e.get("status") == "completed" and e.get("duration_seconds")
        ]
        if completed_executions:
            durations = [e["duration_seconds"] for e in completed_executions]
            metrics["performance_metrics"]["average_execution_time"] = sum(
                durations
            ) / len(durations)
            metrics["performance_metrics"]["min_execution_time"] = min(durations)
            metrics["performance_metrics"]["max_execution_time"] = max(durations)
            metrics["performance_metrics"]["total_execution_time"] = sum(durations)

        return metrics

    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统指标失败: {str(e)}")


@router.get("/logs")
async def get_system_logs(
    level: str = Query("INFO", description="日志级别"),
    lines: int = Query(100, description="返回行数"),
    component: Optional[str] = Query(None, description="组件过滤"),
):
    """获取系统日志"""
    try:
        # 读取日志文件
        log_file = "logs/testagent.log"

        if not os.path.exists(log_file):
            return {"logs": [], "message": "日志文件不存在"}

        # 读取最后N行
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # 过滤日志
        filtered_logs = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue

            # 级别过滤
            if level.upper() not in line.upper():
                continue

            # 组件过滤
            if component and component.lower() not in line.lower():
                continue

            filtered_logs.append(line)

        return {
            "logs": filtered_logs,
            "total_lines": len(filtered_logs),
            "level_filter": level,
            "component_filter": component,
        }

    except Exception as e:
        logger.error(f"获取系统日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统日志失败: {str(e)}")


@router.post("/config/update")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    try:
        # 获取设置
        settings = get_settings()

        # 验证配置键
        if not hasattr(settings, request.config_key):
            raise HTTPException(
                status_code=400, detail=f"无效的配置键: {request.config_key}"
            )

        # 更新配置
        setattr(settings, request.config_key, request.config_value)

        logger.info(f"配置已更新: {request.config_key} = {request.config_value}")

        return {
            "message": "配置更新成功",
            "config_key": request.config_key,
            "config_value": request.config_value,
            "restart_required": request.restart_required,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/config")
async def get_config():
    """获取配置"""
    try:
        settings = get_settings()

        # 构建配置字典（排除敏感信息）
        config = {}
        sensitive_keys = ["api_key", "secret", "password", "token"]

        for key, value in settings.__dict__.items():
            if not key.startswith("_"):
                # 检查是否是敏感信息
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    config[key] = "***"
                else:
                    config[key] = value

        return {"config": config, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/restart")
async def restart_system():
    """重启系统"""
    try:
        logger.info("收到系统重启请求")

        # 这里可以实现优雅关闭逻辑
        # 在实际部署中，这可能需要与进程管理器（如supervisor）配合

        return {
            "message": "系统重启请求已接收",
            "timestamp": datetime.now().isoformat(),
            "note": "请通过进程管理器重启服务",
        }

    except Exception as e:
        logger.error(f"重启系统失败: {e}")
        raise HTTPException(status_code=500, detail=f"重启系统失败: {str(e)}")
