#!/usr/bin/env python3
"""
任务相关API路由
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import (APIRouter, BackgroundTasks, Body, Depends, HTTPException,
                     Query)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...config.logging_config import get_logger
from ...graph.workflow_manager import get_workflow_manager
from ...models.execution import ExecutionPlan
from ...models.types import TaskType

logger = get_logger("tasks_api")

router = APIRouter()


# 请求模型
class TaskSubmissionRequest(BaseModel):
    """任务提交请求"""

    task_type: str = Field(..., description="任务类型")
    task_topic: str = Field(..., description="任务主题")
    context: Optional[str] = Field(None, description="任务上下文")
    code_snippets: Optional[List[str]] = Field(None, description="代码片段")
    requirements: Optional[List[str]] = Field(None, description="需求列表")
    locale: str = Field("zh-CN", description="语言设置")
    timeout: Optional[int] = Field(300, description="超时时间（秒）")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class TaskStatusRequest(BaseModel):
    """任务状态查询请求"""

    task_id: str = Field(..., description="任务ID")


# 响应模型
class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="状态消息")
    created_at: str = Field(..., description="创建时间")
    estimated_duration: Optional[int] = Field(None, description="预估执行时间")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: Optional[float] = Field(None, description="进度百分比")
    current_step: Optional[str] = Field(None, description="当前步骤")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    execution_time: Optional[float] = Field(None, description="执行时间")
    logs: Optional[List[str]] = Field(None, description="执行日志")


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: List[TaskStatusResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总任务数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


# 依赖注入
async def get_workflow_manager_dep():
    """获取工作流管理器依赖"""
    return get_workflow_manager()


# 后台任务执行
async def execute_task_background(task_id: str, request: TaskSubmissionRequest):
    """后台执行任务"""
    try:
        logger.info(f"开始执行任务: {task_id}")

        # 获取工作流管理器
        workflow_manager = get_workflow_manager()

        # 准备初始状态
        initial_state = {
            "task_type": request.task_type,
            "task_topic": request.task_topic,
            "locale": request.locale,
            "context": request.context or "",
            "code_snippets": request.code_snippets or [],
            "requirements": request.requirements or [],
            "observations": [],
        }

        # 准备配置
        config = request.config or {}
        if "configurable" not in config:
            config["configurable"] = {}
        config["configurable"]["thread_id"] = task_id

        # 执行工作流
        result = await workflow_manager.execute_workflow(
            initial_state=initial_state,
            execution_id=task_id,
            config=config,
            timeout=request.timeout or 300,
        )

        logger.info(f"任务执行完成: {task_id}")

    except Exception as e:
        logger.error(f"任务执行失败 {task_id}: {e}")
        # 更新执行状态为失败
        workflow_manager = get_workflow_manager()
        if task_id in workflow_manager.executions:
            execution = workflow_manager.executions[task_id]
            execution.status = "failed"
            execution.error = str(e)
            execution.end_time = datetime.now()


@router.post("/submit", response_model=TaskResponse)
async def submit_task(
    request: TaskSubmissionRequest,
    background_tasks: BackgroundTasks,
    workflow_manager=Depends(get_workflow_manager_dep),
):
    """提交新任务"""
    try:
        # 验证任务类型
        valid_task_types = [task_type.value for task_type in TaskType]
        if request.task_type not in valid_task_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的任务类型: {request.task_type}。有效类型: {valid_task_types}",
            )

        # 生成任务ID
        task_id = f"task_{uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

        # 添加后台任务
        background_tasks.add_task(execute_task_background, task_id, request)

        logger.info(f"任务已提交: {task_id}")

        return TaskResponse(
            task_id=task_id,
            status="submitted",
            message="任务已提交并开始处理",
            created_at=datetime.now().isoformat(),
            estimated_duration=request.timeout,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str, workflow_manager=Depends(get_workflow_manager_dep)
):
    """获取任务状态"""
    try:
        # 获取执行状态
        execution_status = workflow_manager.get_execution_status(task_id)

        if not execution_status:
            raise HTTPException(status_code=404, detail=f"未找到任务: {task_id}")

        # 构建响应
        response = TaskStatusResponse(
            task_id=task_id,
            status=execution_status.get("status", "unknown"),
            progress=execution_status.get("progress", 0.0),
            current_step=execution_status.get("current_step"),
            created_at=execution_status.get("start_time", datetime.now().isoformat()),
            updated_at=execution_status.get("end_time") or datetime.now().isoformat(),
            execution_time=execution_status.get("duration_seconds", 0),
            logs=execution_status.get("logs", []),
        )

        # 添加结果或错误信息
        if execution_status.get("status") == "completed":
            final_state = execution_status.get("final_state", {})
            response.result = {
                "report": final_state.get("report", {}),
                "review": final_state.get("review", {}),
                "observations": final_state.get("observations", []),
            }
        elif execution_status.get("status") == "failed":
            response.error = execution_status.get("error", "未知错误")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: str, workflow_manager=Depends(get_workflow_manager_dep)
):
    """流式获取任务状态"""

    async def generate_status_stream():
        """生成状态流"""
        try:
            while True:
                # 获取当前状态
                execution_status = workflow_manager.get_execution_status(task_id)

                if not execution_status:
                    yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
                    break

                # 构建状态数据
                status_data = {
                    "task_id": task_id,
                    "status": execution_status.get("status", "unknown"),
                    "progress": execution_status.get("progress", 0.0),
                    "current_step": execution_status.get("current_step"),
                    "timestamp": datetime.now().isoformat(),
                }

                # 发送状态更新
                yield f"data: {json.dumps(status_data)}\n\n"

                # 如果任务完成，发送最终结果并结束
                if execution_status.get("status") in [
                    "completed",
                    "failed",
                    "cancelled",
                ]:
                    if execution_status.get("status") == "completed":
                        final_state = execution_status.get("final_state", {})
                        result_data = {
                            "task_id": task_id,
                            "status": "completed",
                            "result": {
                                "report": final_state.get("report", {}),
                                "review": final_state.get("review", {}),
                            },
                            "timestamp": datetime.now().isoformat(),
                        }
                        yield f"data: {json.dumps(result_data)}\n\n"

                    yield "data: [DONE]\n\n"
                    break

                # 等待一段时间再检查
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"流式状态更新失败: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_status_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    workflow_manager=Depends(get_workflow_manager_dep),
):
    """列出任务"""
    try:
        # 获取执行列表
        executions = workflow_manager.list_executions(status_filter=status)

        # 分页
        total = len(executions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_executions = executions[start_idx:end_idx]

        # 构建任务列表
        tasks = []
        for execution in paginated_executions:
            task = TaskStatusResponse(
                task_id=execution.get("execution_id", ""),
                status=execution.get("status", "unknown"),
                progress=execution.get("progress", 0.0),
                current_step=execution.get("current_step"),
                created_at=execution.get("start_time", ""),
                updated_at=execution.get("end_time", "") or datetime.now().isoformat(),
                execution_time=execution.get("duration_seconds", 0),
                logs=execution.get("logs", []),
            )

            # 添加错误信息
            if execution.get("status") == "failed" and "error" in execution:
                task.error = execution["error"]

            # 添加结果信息
            if execution.get("status") == "completed" and "final_state" in execution:
                final_state = execution["final_state"]
                task.result = {
                    "report": final_state.get("report", {}),
                    "review": final_state.get("review", {}),
                }

            tasks.append(task)

        return TaskListResponse(
            tasks=tasks, total=total, page=page, page_size=page_size
        )

    except Exception as e:
        logger.error(f"列出任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出任务失败: {str(e)}")


@router.delete("/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str, workflow_manager=Depends(get_workflow_manager_dep)):
    """取消任务"""
    try:
        # 取消执行
        result = workflow_manager.cancel_execution(task_id)

        if not result:
            raise HTTPException(
                status_code=404, detail=f"未找到任务或任务无法取消: {task_id}"
            )

        logger.info(f"任务已取消: {task_id}")

        return TaskResponse(
            task_id=task_id,
            status="cancelled",
            message="任务已取消",
            created_at=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    workflow_manager=Depends(get_workflow_manager_dep),
):
    """重试任务"""
    try:
        # 获取原始执行状态
        execution_status = workflow_manager.get_execution_status(task_id)

        if not execution_status:
            raise HTTPException(status_code=404, detail=f"未找到任务: {task_id}")

        # 检查是否可以重试
        if execution_status.get("status") not in ["failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"只有失败或取消的任务可以重试，当前状态: {execution_status.get('status')}",
            )

        # 生成新任务ID
        new_task_id = f"retry_{task_id}_{int(datetime.now().timestamp())}"

        # 从原始状态中提取任务请求信息
        original_state = execution_status.get("initial_state", {})

        retry_request = TaskSubmissionRequest(
            task_type=original_state.get("task_type", "test_case_generation"),
            task_topic=original_state.get("task_topic", "重试任务"),
            context=original_state.get("context"),
            code_snippets=original_state.get("code_snippets"),
            requirements=original_state.get("requirements"),
            locale=original_state.get("locale", "zh-CN"),
            timeout=300,
        )

        # 添加后台任务
        background_tasks.add_task(execute_task_background, new_task_id, retry_request)

        logger.info(f"任务已重试: {task_id} -> {new_task_id}")

        return TaskResponse(
            task_id=new_task_id,
            status="submitted",
            message=f"任务 {task_id} 已重试，新任务ID: {new_task_id}",
            created_at=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试任务失败: {str(e)}")


@router.get("/{task_id}/result")
async def get_task_result(
    task_id: str,
    format: str = Query("json", description="结果格式: json, markdown, html"),
    workflow_manager=Depends(get_workflow_manager_dep),
):
    """获取任务结果"""
    try:
        # 获取执行状态
        execution_status = workflow_manager.get_execution_status(task_id)

        if not execution_status:
            raise HTTPException(status_code=404, detail=f"未找到任务: {task_id}")

        if execution_status.get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"任务尚未完成，当前状态: {execution_status.get('status')}",
            )

        # 获取最终状态
        final_state = execution_status.get("final_state", {})

        if format == "json":
            return {
                "task_id": task_id,
                "status": "completed",
                "result": {
                    "report": final_state.get("report", {}),
                    "review": final_state.get("review", {}),
                    "observations": final_state.get("observations", []),
                },
                "execution_time": execution_status.get("duration_seconds", 0),
            }

        elif format == "markdown":
            # 生成Markdown格式的报告
            report = final_state.get("report", {})
            markdown_content = f"""# 任务执行报告

## 任务信息
- 任务ID: {task_id}
- 执行时间: {execution_status.get('duration_seconds', 0)}秒
- 完成时间: {execution_status.get('end_time', '')}

## 执行结果
{report.get('content', '无报告内容')}

## 质量评审
{final_state.get('review', {}).get('content', '无评审内容')}
"""

            return StreamingResponse(
                iter([markdown_content]),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=task_{task_id}_report.md"
                },
            )

        elif format == "html":
            # 生成HTML格式的报告
            report = final_state.get("report", {})
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>任务执行报告 - {task_id}</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2 {{ color: #333; }}
        .info {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>任务执行报告</h1>
    <div class="info">
        <p><strong>任务ID:</strong> {task_id}</p>
        <p><strong>执行时间:</strong> {execution_status.get('duration_seconds', 0)}秒</p>
        <p><strong>完成时间:</strong> {execution_status.get('end_time', '')}</p>
    </div>
    
    <h2>执行结果</h2>
    <div>{report.get('content', '无报告内容')}</div>
    
    <h2>质量评审</h2>
    <div>{final_state.get('review', {}).get('content', '无评审内容')}</div>
</body>
</html>"""

            return StreamingResponse(
                iter([html_content]),
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename=task_{task_id}_report.html"
                },
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的格式: {format}。支持的格式: json, markdown, html",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务结果失败: {str(e)}")
