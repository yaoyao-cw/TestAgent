"""数据模型模块"""

from .types import TaskType, StepType, AgentType, LLMType
from .state import TestAgentState, Resource
from .execution import ExecutionPlan, ExecutionStep
from .review import ReviewScore, TestCaseReview, TestScriptReview, RequirementReview
from .workspace import (
    TaskStatus,
    FileType,
    FileReference,
    TaskMetadata,
    WorkspaceState,
    TaskRecoveryInfo,
    GlobalState,
)

__all__ = [
    # 基础类型
    "TaskType",
    "StepType",
    "AgentType",
    "LLMType",
    # 状态模型
    "TestAgentState",
    "Resource",
    # 执行模型
    "ExecutionPlan",
    "ExecutionStep",
    # 评审模型
    "ReviewScore",
    "TestCaseReview",
    "TestScriptReview",
    "RequirementReview",
    # 工作空间模型
    "TaskStatus",
    "FileType",
    "FileReference",
    "TaskMetadata",
    "WorkspaceState",
    "TaskRecoveryInfo",
    "GlobalState",
]
