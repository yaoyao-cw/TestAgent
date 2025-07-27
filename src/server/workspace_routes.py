"""工作空间相关API路由

提供任务工作空间管理的REST API接口。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.workspace import workspace_manager
from ..models.types import TaskType
from ..models.workspace import FileReference, TaskMetadata, TaskStatus


# API请求/响应模型
class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    title: str
    description: str
    task_type: TaskType


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    title: str
    description: str
    task_type: str
    status: str
    created_at: str
    updated_at: str
    workspace_path: str
    current_step: int
    total_steps: int
    active_agent: Optional[str]
    error_count: int


class FileResponse(BaseModel):
    """文件响应"""

    path: str
    type: str
    size: int
    created_by: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


class UpdateTaskStatusRequest(BaseModel):
    """更新任务状态请求"""

    status: TaskStatus


class CreateFileRequest(BaseModel):
    """创建文件请求"""

    step_number: int
    agent_type: str
    task_type: str
    content: str
    file_type: str = "md"


class UpdateTodoRequest(BaseModel):
    """更新待办事项请求"""

    content: str


# 创建路由器
router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: CreateTaskRequest):
    """创建新任务工作空间"""
    try:
        metadata = workspace_manager.create_task_workspace(
            title=request.title,
            description=request.description,
            task_type=request.task_type,
        )

        return TaskResponse(
            task_id=metadata.task_id,
            title=metadata.title,
            description=metadata.description,
            task_type=metadata.task_type.value,
            status=metadata.status.value,
            created_at=metadata.created_at.isoformat(),
            updated_at=metadata.updated_at.isoformat(),
            workspace_path=metadata.workspace_path,
            current_step=metadata.current_step,
            total_steps=metadata.total_steps,
            active_agent=metadata.active_agent,
            error_count=metadata.error_count,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}",
        )


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks():
    """列出所有任务"""
    try:
        tasks = workspace_manager.list_tasks()

        return [
            TaskResponse(
                task_id=task.task_id,
                title=task.title,
                description=task.description,
                task_type=task.task_type.value,
                status=task.status.value,
                created_at=task.created_at.isoformat(),
                updated_at=task.updated_at.isoformat(),
                workspace_path=task.workspace_path,
                current_step=task.current_step,
                total_steps=task.total_steps,
                active_agent=task.active_agent,
                error_count=task.error_count,
            )
            for task in tasks
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}",
        )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取指定任务信息"""
    try:
        metadata = workspace_manager.load_task_metadata(task_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return TaskResponse(
            task_id=metadata.task_id,
            title=metadata.title,
            description=metadata.description,
            task_type=metadata.task_type.value,
            status=metadata.status.value,
            created_at=metadata.created_at.isoformat(),
            updated_at=metadata.updated_at.isoformat(),
            workspace_path=metadata.workspace_path,
            current_step=metadata.current_step,
            total_steps=metadata.total_steps,
            active_agent=metadata.active_agent,
            error_count=metadata.error_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务信息失败: {str(e)}",
        )


@router.put("/tasks/{task_id}/status")
async def update_task_status(task_id: str, request: UpdateTaskStatusRequest):
    """更新任务状态"""
    try:
        success = workspace_manager.update_task_status(task_id, request.status)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return {"message": "任务状态更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新任务状态失败: {str(e)}",
        )


@router.get("/tasks/{task_id}/files", response_model=List[FileResponse])
async def get_task_files(task_id: str):
    """获取任务所有文件"""
    try:
        files = workspace_manager.get_task_files(task_id)

        return [
            FileResponse(
                path=file_ref.path,
                type=file_ref.type.value,
                size=file_ref.size,
                created_by=file_ref.created_by,
                created_at=file_ref.created_at.isoformat(),
                updated_at=file_ref.updated_at.isoformat(),
                metadata=file_ref.metadata,
            )
            for file_ref in files
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务文件失败: {str(e)}",
        )


@router.post("/tasks/{task_id}/files")
async def create_agent_file(task_id: str, request: CreateFileRequest):
    """创建智能体输出文件"""
    try:
        from ..models.types import AgentType
        from ..models.workspace import FileType

        # 转换字符串到枚举
        agent_type = AgentType(request.agent_type)
        file_type = FileType(request.file_type)

        filename = workspace_manager.create_agent_file(
            task_id=task_id,
            step_number=request.step_number,
            agent_type=agent_type,
            task_type=request.task_type,
            content=request.content,
            file_type=file_type,
        )

        if not filename:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return {"filename": filename, "message": "文件创建成功"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"参数错误: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建文件失败: {str(e)}",
        )


@router.put("/tasks/{task_id}/todo")
async def update_todo(task_id: str, request: UpdateTodoRequest):
    """更新任务待办事项"""
    try:
        success = workspace_manager.update_todo_file(task_id, request.content)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return {"message": "待办事项更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新待办事项失败: {str(e)}",
        )


@router.post("/tasks/{task_id}/errors")
async def append_error_log(task_id: str, error_message: str):
    """追加错误日志"""
    try:
        success = workspace_manager.append_error_log(task_id, error_message)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return {"message": "错误日志添加成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加错误日志失败: {str(e)}",
        )


@router.get("/tasks/{task_id}/recovery")
async def get_task_recovery_info(task_id: str):
    """获取任务恢复信息"""
    try:
        recovery_info = workspace_manager.get_task_recovery_info(task_id)
        if not recovery_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        # 转换为可序列化的格式
        task_metadata = recovery_info["task_metadata"]
        latest_files = recovery_info["latest_files"]

        return {
            "task_metadata": {
                "task_id": task_metadata.task_id,
                "title": task_metadata.title,
                "status": task_metadata.status.value,
                "current_step": task_metadata.current_step,
                "error_count": task_metadata.error_count,
            },
            "latest_files": {
                agent: {
                    "path": file_ref.path,
                    "type": file_ref.type.value,
                    "updated_at": file_ref.updated_at.isoformat(),
                }
                for agent, file_ref in latest_files.items()
            },
            "todo_content": recovery_info["todo_content"],
            "error_log": recovery_info["error_log"],
            "can_resume": recovery_info["can_resume"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取恢复信息失败: {str(e)}",
        )


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务工作空间"""
    try:
        success = workspace_manager.delete_task(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"任务不存在: {task_id}"
            )

        return {"message": "任务删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}",
        )
