"""系统状态数据模型"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import MessagesState
from pydantic import BaseModel

from .execution import ExecutionPlan
from .review import ReviewScore
from .types import TaskType


class TestAgentState(MessagesState):
    """TestAgent系统状态模型"""

    # 基础信息
    locale: str
    task_topic: str
    task_type: Optional[TaskType]

    # 执行状态
    plan_iterations: int
    current_plan: Optional[ExecutionPlan]
    observations: List[str]

    # 资源和工具
    resources: List[Dict[str, Any]]
    rag_results: List[str]

    # 输出结果
    final_report: str
    review_score: Optional[ReviewScore]

    # 控制参数
    auto_accepted_plan: bool
    enable_rag_search: bool
    enable_human_feedback: bool


# 辅助函数来操作状态
def add_observation(state: TestAgentState, observation: str) -> None:
    """添加观察结果"""
    if observation and observation not in state.get("observations", []):
        if "observations" not in state:
            state["observations"] = []
        state["observations"].append(observation)


def add_resource(state: TestAgentState, resource: Dict[str, Any]) -> None:
    """添加资源"""
    if "resources" not in state:
        state["resources"] = []
    if resource not in state["resources"]:
        state["resources"].append(resource)


def clear_observations(state: TestAgentState) -> None:
    """清空观察结果"""
    state["observations"] = []


def get_task_context(state: TestAgentState) -> str:
    """获取任务上下文信息"""
    context_parts = []

    if state.get("task_topic"):
        context_parts.append(f"任务主题: {state['task_topic']}")

    if state.get("task_type"):
        task_type = state["task_type"]
        if hasattr(task_type, "value"):
            context_parts.append(f"任务类型: {task_type.value}")
        else:
            context_parts.append(f"任务类型: {task_type}")

    if state.get("current_plan"):
        plan = state["current_plan"]
        context_parts.append(f"当前计划: {plan.title}")
        completed_steps = len(plan.get_completed_steps())
        total_steps = len(plan.steps)
        context_parts.append(f"执行进度: {completed_steps}/{total_steps}")

    if state.get("observations"):
        context_parts.append(f"观察结果数量: {len(state['observations'])}")

    return "\n".join(context_parts)


def is_task_completed(state: TestAgentState) -> bool:
    """检查任务是否完成"""
    current_plan = state.get("current_plan")
    final_report = state.get("final_report", "")

    return (
        current_plan is not None and current_plan.is_completed() and bool(final_report)
    )


def get_completion_percentage(state: TestAgentState) -> float:
    """获取完成百分比"""
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return 0.0

    completed_steps = len(current_plan.get_completed_steps())
    total_steps = len(current_plan.steps)

    return (completed_steps / total_steps) * 100.0


def create_initial_state() -> TestAgentState:
    """创建初始状态"""
    return {
        "messages": [],
        "locale": "zh-CN",
        "task_topic": "",
        "task_type": None,
        "plan_iterations": 0,
        "current_plan": None,
        "observations": [],
        "resources": [],
        "rag_results": [],
        "final_report": "",
        "review_score": None,
        "auto_accepted_plan": True,
        "enable_rag_search": True,
        "enable_human_feedback": False,
    }


class Resource(BaseModel):
    """资源模型"""

    id: str
    title: str
    description: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = {}

    def __init__(self, **data):
        super().__init__(**data)

    class Config:
        arbitrary_types_allowed = True
