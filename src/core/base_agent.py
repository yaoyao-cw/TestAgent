"""基础智能体抽象类

实现统一的load->llm->router标准流程，定义智能体节点的基础接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum

from ..models.types import AgentType
from ..models.workspace import GlobalState


class AgentPhase(Enum):
    """智能体执行阶段"""

    LOAD = "load"
    LLM = "llm"
    ROUTER = "router"


@dataclass
class AgentInput:
    """智能体输入数据"""

    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentOutput:
    """智能体输出数据"""

    data: Dict[str, Any]
    next_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """基础智能体抽象类

    定义统一的load->llm->router标准流程，所有智能体节点都应继承此类。
    """

    def __init__(self, agent_type: AgentType, global_state: GlobalState):
        self.agent_type = agent_type
        self.global_state = global_state
        self.current_phase = AgentPhase.LOAD

    @property
    def name(self) -> str:
        """智能体名称"""
        return self.agent_type.value

    @abstractmethod
    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载Prompt模板、工具集和来自上一节点的输入数据

        Args:
            input_data: 输入数据

        Returns:
            加载后的状态数据
        """
        pass

    @abstractmethod
    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：调用大型语言模型进行思考、分析或创作处理

        Args:
            state: 当前状态数据

        Returns:
            LLM处理后的状态数据
        """
        pass

    @abstractmethod
    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据LLM输出和全局状态决定下一步控制权移交

        Args:
            state: 当前状态数据

        Returns:
            路由决策结果
        """
        pass

    def execute(self, input_data: AgentInput) -> AgentOutput:
        """执行智能体的完整流程：load->llm->router

        Args:
            input_data: 输入数据

        Returns:
            执行结果
        """
        try:
            # 更新全局状态
            self.global_state.set_active_agent(self.agent_type)

            # Load阶段
            self.current_phase = AgentPhase.LOAD
            state = self.load(input_data)

            # LLM阶段
            self.current_phase = AgentPhase.LLM
            state = self.llm(state)

            # Router阶段
            self.current_phase = AgentPhase.ROUTER
            output = self.router(state)

            return output

        except Exception as e:
            # 记录错误到全局状态
            error_msg = f"{self.name} 在 {self.current_phase.value} 阶段出错: {str(e)}"
            self.global_state.add_error(error_msg)

            return AgentOutput(data={}, error=error_msg)

    def get_prompt_template(self) -> str:
        """获取智能体的提示词模板

        子类可以重写此方法提供特定的提示词模板
        """
        return f"""你是一个{self.name}智能体。

当前任务上下文：
{self.global_state.get_task_context()}

请根据输入数据执行相应的任务。
"""

    def get_available_tools(self) -> List[str]:
        """获取智能体可用的工具列表

        子类可以重写此方法提供特定的工具集
        """
        return []

    def should_continue(self, state: Dict[str, Any]) -> bool:
        """判断是否应该继续执行

        Args:
            state: 当前状态

        Returns:
            是否继续执行
        """
        return not state.get("completed", False)

    def get_context_from_global_state(self) -> Dict[str, Any]:
        """从全局状态获取上下文信息"""
        return {
            "current_task_id": self.global_state.get_current_task_id(),
            "current_step": self.global_state.get_current_step(),
            "task_context": self.global_state.get_task_context(),
            "is_task_active": self.global_state.is_task_active(),
        }

    def update_global_state(self, updates: Dict[str, Any]):
        """更新全局状态"""
        if "step" in updates:
            self.global_state.update_step(updates["step"])

        if "last_output" in updates:
            self.global_state.set_last_output(updates["last_output"])


class SimpleAgent(BaseAgent):
    """简单智能体实现

    提供基础的智能体实现，适用于简单的处理任务。
    """

    def __init__(
        self,
        agent_type: AgentType,
        global_state: GlobalState,
        prompt_template: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ):
        super().__init__(agent_type, global_state)
        self._prompt_template = prompt_template
        self._tools = tools or []

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载输入数据和上下文"""
        context = self.get_context_from_global_state()

        return {
            "input_data": input_data.data,
            "context": context,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.get_available_tools(),
            "metadata": input_data.metadata or {},
        }

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """默认LLM处理 - 子类应该重写此方法"""
        # 这里应该调用实际的LLM服务
        # 目前返回一个占位符结果
        state["llm_output"] = {
            "content": f"来自{self.name}的处理结果",
            "reasoning": "基础推理过程",
            "action": "default_action",
        }
        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """默认路由逻辑"""
        llm_output = state.get("llm_output", {})

        return AgentOutput(
            data=llm_output,
            next_agent=None,  # 默认不指定下一个智能体
            metadata={"agent": self.name, "phase_completed": True},
        )

    def get_prompt_template(self) -> str:
        """获取提示词模板"""
        if self._prompt_template:
            return self._prompt_template
        return super().get_prompt_template()

    def get_available_tools(self) -> List[str]:
        """获取可用工具"""
        return self._tools


class ReActAgent(BaseAgent):
    """ReAct智能体基类

    实现ReAct(Reason-Act-Observe)循环的智能体，适用于需要多步推理和工具调用的复杂任务。
    """

    def __init__(
        self, agent_type: AgentType, global_state: GlobalState, max_iterations: int = 5
    ):
        super().__init__(agent_type, global_state)
        self.max_iterations = max_iterations

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """实现ReAct循环的LLM处理"""
        iterations = 0
        react_history = []

        while iterations < self.max_iterations and self.should_continue_react(state):
            # Reason阶段：推理
            reasoning = self.reason(state, react_history)

            # Act阶段：行动
            action_result = self.act(state, reasoning)

            # Observe阶段：观察
            observation = self.observe(state, action_result)

            # 记录本轮ReAct
            react_step = {
                "iteration": iterations + 1,
                "reasoning": reasoning,
                "action": action_result,
                "observation": observation,
            }
            react_history.append(react_step)

            # 更新状态
            state["react_history"] = react_history
            state["last_observation"] = observation

            iterations += 1

        # 设置最终输出
        state["llm_output"] = {
            "react_history": react_history,
            "final_reasoning": react_history[-1]["reasoning"] if react_history else "",
            "iterations_used": iterations,
            "completed": iterations < self.max_iterations,
        }

        return state

    @abstractmethod
    def reason(self, state: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
        """推理阶段：分析当前状态和历史，决定下一步行动"""
        pass

    @abstractmethod
    def act(self, state: Dict[str, Any], reasoning: str) -> Dict[str, Any]:
        """行动阶段：根据推理结果执行具体行动"""
        pass

    @abstractmethod
    def observe(self, state: Dict[str, Any], action_result: Dict[str, Any]) -> str:
        """观察阶段：分析行动结果，为下一轮推理提供信息"""
        pass

    def should_continue_react(self, state: Dict[str, Any]) -> bool:
        """判断是否应该继续ReAct循环"""
        # 检查是否已完成任务
        if state.get("task_completed", False):
            return False

        # 检查是否有明确的停止信号
        if state.get("stop_react", False):
            return False

        return True
