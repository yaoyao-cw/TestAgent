"""工作空间相关数据模型"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .types import AgentType, TaskType


class TaskStatus(Enum):
    """任务状态枚举"""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

    def __str__(self) -> str:
        return self.value


class FileType(Enum):
    """文件类型枚举"""

    MARKDOWN = "md"
    JSON = "json"
    PYTHON = "py"
    TEXT = "txt"
    LOG = "log"
    YAML = "yaml"

    def __str__(self) -> str:
        return self.value


class FileReference(BaseModel):
    """文件引用模型"""

    path: str = Field(..., description="文件路径")
    type: FileType = Field(..., description="文件类型")
    size: int = Field(..., description="文件大小（字节）")
    checksum: str = Field(..., description="文件校验和")
    created_by: str = Field(..., description="创建者（智能体类型）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文件元数据")

    class Config:
        use_enum_values = True


class TaskMetadata(BaseModel):
    """任务元数据模型"""

    task_id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(..., description="任务描述")
    task_type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    workspace_path: str = Field(..., description="工作空间路径")
    files: List[FileReference] = Field(default_factory=list, description="文件列表")
    current_step: int = Field(default=0, description="当前步骤")
    total_steps: int = Field(default=0, description="总步骤数")
    active_agent: Optional[str] = Field(None, description="当前活跃智能体")
    error_count: int = Field(default=0, description="错误计数")

    class Config:
        use_enum_values = False  # Keep enum objects, not just values


class WorkspaceState(BaseModel):
    """工作空间状态模型"""

    current_task_id: Optional[str] = Field(None, description="当前任务ID")
    current_step: int = Field(default=0, description="当前步骤")
    last_file_output_path: Optional[str] = Field(None, description="最后输出文件路径")
    active_agent: Optional[str] = Field(None, description="当前活跃智能体")
    error_count: int = Field(default=0, description="错误计数")
    cache_keys: List[str] = Field(default_factory=list, description="缓存键列表")

    def update_current_task(self, task_id: str, step: int = 0):
        """更新当前任务"""
        self.current_task_id = task_id
        self.current_step = step
        self.error_count = 0

    def increment_step(self):
        """增加步骤计数"""
        self.current_step += 1

    def set_active_agent(self, agent_type: AgentType):
        """设置活跃智能体"""
        self.active_agent = agent_type.value

    def add_error(self):
        """增加错误计数"""
        self.error_count += 1

    def set_last_output(self, file_path: str):
        """设置最后输出文件路径"""
        self.last_file_output_path = file_path

    def add_cache_key(self, key: str):
        """添加缓存键"""
        if key not in self.cache_keys:
            self.cache_keys.append(key)

    def clear_cache_keys(self):
        """清空缓存键"""
        self.cache_keys.clear()


class TaskRecoveryInfo(BaseModel):
    """任务恢复信息模型"""

    task_metadata: TaskMetadata = Field(..., description="任务元数据")
    latest_files: Dict[str, FileReference] = Field(..., description="各智能体最新文件")
    todo_content: str = Field(..., description="待办事项内容")
    error_log: str = Field(..., description="错误日志")
    can_resume: bool = Field(..., description="是否可以恢复")

    def get_last_completed_step(self) -> int:
        """获取最后完成的步骤"""
        if not self.latest_files:
            return 0

        max_step = 0
        for file_ref in self.latest_files.values():
            step_number = file_ref.metadata.get("step_number", 0)
            if step_number > max_step:
                max_step = step_number

        return max_step

    def get_next_agent_suggestion(self) -> Optional[str]:
        """获取下一个建议的智能体"""
        # 基于文件命名规范和任务状态推断下一个智能体
        last_step = self.get_last_completed_step()

        # 简单的智能体顺序逻辑
        agent_sequence = [
            "coordinator",
            "planner",
            "researcher",
            "tester",
            "coder",
            "executor",
            "reviewer",
            "reporter",
        ]

        # 查找最后活跃的智能体
        last_agent_index = -1
        for i, agent in enumerate(agent_sequence):
            if agent in self.latest_files:
                last_agent_index = i

        # 返回下一个智能体
        if last_agent_index >= 0 and last_agent_index < len(agent_sequence) - 1:
            return agent_sequence[last_agent_index + 1]

        return None


class GlobalState(BaseModel):
    """全局状态管理器"""

    workspace_state: WorkspaceState = Field(default_factory=WorkspaceState)
    task_metadata: Optional[TaskMetadata] = Field(None, description="当前任务元数据")

    def initialize_task(self, task_metadata: TaskMetadata):
        """初始化任务"""
        self.task_metadata = task_metadata
        self.workspace_state.update_current_task(task_metadata.task_id)

    def get_current_task_id(self) -> Optional[str]:
        """获取当前任务ID"""
        return self.workspace_state.current_task_id

    def get_current_step(self) -> int:
        """获取当前步骤"""
        return self.workspace_state.current_step

    def update_step(self, step: int):
        """更新步骤"""
        self.workspace_state.current_step = step
        if self.task_metadata:
            self.task_metadata.current_step = step

    def set_active_agent(self, agent_type: AgentType):
        """设置活跃智能体"""
        self.workspace_state.set_active_agent(agent_type)
        if self.task_metadata:
            self.task_metadata.active_agent = agent_type.value

    def add_error(self, error_message: str):
        """添加错误"""
        self.workspace_state.add_error()
        if self.task_metadata:
            self.task_metadata.error_count += 1

    def set_last_output(self, file_path: str):
        """设置最后输出"""
        self.workspace_state.set_last_output(file_path)

    def is_task_active(self) -> bool:
        """检查任务是否活跃"""
        return self.task_metadata is not None and self.task_metadata.status in [
            TaskStatus.CREATED,
            TaskStatus.IN_PROGRESS,
        ]

    def get_task_context(self) -> str:
        """获取任务上下文信息"""
        if not self.task_metadata:
            return "无活跃任务"

        context_parts = [
            f"任务ID: {self.task_metadata.task_id}",
            f"任务标题: {self.task_metadata.title}",
            f"任务类型: {self.task_metadata.task_type.value}",
            f"任务状态: {self.task_metadata.status.value}",
            f"当前步骤: {self.task_metadata.current_step}/{self.task_metadata.total_steps}",
        ]

        if self.task_metadata.active_agent:
            context_parts.append(f"活跃智能体: {self.task_metadata.active_agent}")

        if self.task_metadata.error_count > 0:
            context_parts.append(f"错误计数: {self.task_metadata.error_count}")

        return "\n".join(context_parts)
