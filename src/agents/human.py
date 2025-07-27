"""Human节点实现

建立Human节点，支持关键决策点的人工干预。
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum

from ..core.base_agent import SimpleAgent, AgentInput, AgentOutput
from ..models.types import AgentType
from ..models.workspace import GlobalState, TaskStatus
from ..config.logging_config import get_logger

logger = get_logger("human_agent")


class InterventionType(Enum):
    """人工干预类型"""

    APPROVAL = "approval"  # 审批
    DECISION = "decision"  # 决策
    CORRECTION = "correction"  # 纠正
    GUIDANCE = "guidance"  # 指导
    REVIEW = "review"  # 审查


class InterventionPriority(Enum):
    """干预优先级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HumanInterventionRequest:
    """人工干预请求"""

    def __init__(
        self,
        intervention_type: InterventionType,
        priority: InterventionPriority,
        context: Dict[str, Any],
        question: str,
        options: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.intervention_type = intervention_type
        self.priority = priority
        self.context = context
        self.question = question
        self.options = options or []
        self.timeout_seconds = timeout_seconds
        self.created_at = datetime.now()
        self.request_id = f"human_{int(self.created_at.timestamp())}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "intervention_type": self.intervention_type.value,
            "priority": self.priority.value,
            "context": self.context,
            "question": self.question,
            "options": self.options,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at.isoformat(),
        }


class HumanInterventionResponse:
    """人工干预响应"""

    def __init__(
        self,
        request_id: str,
        response: str,
        selected_option: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ):
        self.request_id = request_id
        self.response = response
        self.selected_option = selected_option
        self.additional_context = additional_context or {}
        self.responded_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "response": self.response,
            "selected_option": self.selected_option,
            "additional_context": self.additional_context,
            "responded_at": self.responded_at.isoformat(),
        }


class HumanAgent(SimpleAgent):
    """Human智能体

    负责处理需要人工干预的关键决策点。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.REVIEWER, global_state)  # 使用REVIEWER类型作为占位
        self.name = "human"

        # Human节点可用的工具
        self.available_tools = [
            "user_input",
            "context_display",
            "option_selection",
            "feedback_collection",
        ]

        # 干预历史记录
        self.intervention_history: List[Dict[str, Any]] = []

        # 默认超时设置（秒）
        self.default_timeout = 300  # 5分钟

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：准备人工干预请求"""
        logger.info("Human节点开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 解析输入数据
        intervention_type_str = input_data.data.get("intervention_type", "decision")
        priority_str = input_data.data.get("priority", "medium")
        question = input_data.data.get("question", "需要您的决策")
        options = input_data.data.get("options", [])
        timeout_seconds = input_data.data.get("timeout_seconds", self.default_timeout)

        # 转换枚举类型
        try:
            intervention_type = InterventionType(intervention_type_str)
        except ValueError:
            intervention_type = InterventionType.DECISION

        try:
            priority = InterventionPriority(priority_str)
        except ValueError:
            priority = InterventionPriority.MEDIUM

        # 创建干预请求
        intervention_request = HumanInterventionRequest(
            intervention_type=intervention_type,
            priority=priority,
            context=context,
            question=question,
            options=options,
            timeout_seconds=timeout_seconds,
        )

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "intervention_request": intervention_request,
            "intervention_type": intervention_type,
            "priority": priority,
            "question": question,
            "options": options,
            "timeout_seconds": timeout_seconds,
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "intervention_completed": False,
            "human_response": None,
        }

        logger.info(f"Human节点加载完成，干预类型: {intervention_type.value}")
        return state

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：处理人工干预逻辑"""
        logger.info("Human节点进入LLM阶段")

        intervention_request = state.get("intervention_request")

        try:
            # 显示干预请求给用户
            display_content = self._format_intervention_display(intervention_request)

            # 等待用户响应（这里需要实际的用户交互实现）
            human_response = self._wait_for_human_response(intervention_request)

            # 处理响应
            processed_response = self._process_human_response(
                human_response, intervention_request
            )

            # 记录干预历史
            self._record_intervention(intervention_request, human_response)

            state["llm_output"] = {
                "display_content": display_content,
                "human_response": human_response,
                "processed_response": processed_response,
                "intervention_completed": True,
            }

            # 更新状态
            state["intervention_completed"] = True
            state["human_response"] = human_response

            logger.info("人工干预完成")

        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state["llm_output"] = {
                "display_content": f"干预显示失败: {str(e)}",
                "human_response": None,
                "processed_response": None,
                "intervention_completed": False,
                "error": str(e),
            }

        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据人工响应决定下一步"""
        logger.info("Human节点进入路由阶段")

        llm_output = state.get("llm_output", {})
        intervention_completed = llm_output.get("intervention_completed", False)
        processed_response = llm_output.get("processed_response", {})

        # 决定下一个智能体
        next_agent = None
        if intervention_completed and processed_response:
            next_agent = processed_response.get("next_agent")

            # 如果没有明确指定，根据干预类型推断
            if not next_agent:
                intervention_type = state.get("intervention_type")
                next_agent = self._infer_next_agent(
                    intervention_type, processed_response
                )

        # 更新全局状态
        self.update_global_state(
            {
                "step": self.global_state.get_current_step() + 1,
                "last_output": f"人工干预完成: {processed_response.get('decision', '无决策')}",
            }
        )

        return AgentOutput(
            data={
                "human_response": llm_output.get("human_response", {}),
                "processed_response": processed_response,
                "intervention_completed": intervention_completed,
                "decision": processed_response.get("decision", ""),
                "next_action": processed_response.get("next_action", ""),
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "intervention_type": (
                    state.get("intervention_type", "").value
                    if state.get("intervention_type")
                    else ""
                ),
                "human_decision": processed_response.get("decision", ""),
            },
        )

    def _format_intervention_display(self, request: HumanInterventionRequest) -> str:
        """格式化干预显示内容"""
        display_parts = [
            "# 人工干预请求",
            f"**请求ID**: {request.request_id}",
            f"**干预类型**: {request.intervention_type.value}",
            f"**优先级**: {request.priority.value}",
            f"**创建时间**: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 上下文信息",
        ]

        # 添加上下文信息
        context = request.context
        if context.get("task_id"):
            display_parts.append(f"**任务ID**: {context['task_id']}")
        if context.get("current_step"):
            display_parts.append(f"**当前步骤**: {context['current_step']}")
        if context.get("last_output"):
            display_parts.append(f"**上一步输出**: {context['last_output']}")

        display_parts.extend(["", "## 需要您的决策", request.question, ""])

        # 添加选项
        if request.options:
            display_parts.append("## 可选项")
            for i, option in enumerate(request.options, 1):
                display_parts.append(f"{i}. {option}")
            display_parts.append("")

        # 添加超时信息
        if request.timeout_seconds:
            display_parts.append(f"**超时时间**: {request.timeout_seconds}秒")

        display_parts.extend(["", "---", "*请根据上述信息做出决策*"])

        return "\n".join(display_parts)

    def _wait_for_human_response(
        self, request: HumanInterventionRequest
    ) -> HumanInterventionResponse:
        """等待人工响应（模拟实现）"""
        # 这里应该实现实际的用户交互逻辑
        # 比如通过WebSocket、HTTP API或其他方式获取用户输入
        # 暂时返回模拟响应

        logger.info(f"等待人工响应，请求ID: {request.request_id}")

        # 模拟响应
        if request.intervention_type == InterventionType.APPROVAL:
            response_text = "批准"
            selected_option = (
                "approve"
                if "approve" in [opt.lower() for opt in request.options]
                else None
            )
        elif request.intervention_type == InterventionType.DECISION:
            response_text = "继续执行"
            selected_option = request.options[0] if request.options else None
        else:
            response_text = "确认"
            selected_option = None

        return HumanInterventionResponse(
            request_id=request.request_id,
            response=response_text,
            selected_option=selected_option,
            additional_context={"simulated": True},
        )

    def _process_human_response(
        self, response: HumanInterventionResponse, request: HumanInterventionRequest
    ) -> Dict[str, Any]:
        """处理人工响应"""
        processed = {
            "decision": response.response,
            "selected_option": response.selected_option,
            "additional_context": response.additional_context,
            "next_action": "",
            "next_agent": None,
        }

        # 根据干预类型和响应内容决定下一步行动
        if request.intervention_type == InterventionType.APPROVAL:
            if response.response.lower() in ["批准", "approve", "yes", "是"]:
                processed["next_action"] = "continue"
                processed["next_agent"] = "reporter"  # 批准后继续到报告阶段
            else:
                processed["next_action"] = "reject"
                processed["next_agent"] = "reviewer"  # 拒绝后返回评审

        elif request.intervention_type == InterventionType.DECISION:
            if response.selected_option:
                processed["next_action"] = f"execute_{response.selected_option}"
                # 根据选项决定下一个智能体
                if "retry" in response.selected_option.lower():
                    processed["next_agent"] = "tester"
                elif "modify" in response.selected_option.lower():
                    processed["next_agent"] = "coder"
                else:
                    processed["next_agent"] = "reporter"
            else:
                processed["next_action"] = "continue"
                processed["next_agent"] = "reporter"

        elif request.intervention_type == InterventionType.CORRECTION:
            processed["next_action"] = "apply_correction"
            processed["next_agent"] = "reviewer"  # 应用纠正后重新评审

        elif request.intervention_type == InterventionType.GUIDANCE:
            processed["next_action"] = "apply_guidance"
            # 根据指导内容决定下一个智能体
            if "test" in response.response.lower():
                processed["next_agent"] = "tester"
            elif "code" in response.response.lower():
                processed["next_agent"] = "coder"
            else:
                processed["next_agent"] = "planner"

        elif request.intervention_type == InterventionType.REVIEW:
            if response.response.lower() in ["通过", "pass", "ok", "确认"]:
                processed["next_action"] = "review_passed"
                processed["next_agent"] = "reporter"
            else:
                processed["next_action"] = "review_failed"
                processed["next_agent"] = "reviewer"

        return processed

    def _record_intervention(
        self, request: HumanInterventionRequest, response: HumanInterventionResponse
    ):
        """记录干预历史"""
        intervention_record = {
            "request": request.to_dict(),
            "response": response.to_dict(),
            "recorded_at": datetime.now().isoformat(),
        }

        self.intervention_history.append(intervention_record)

        # 限制历史记录数量
        if len(self.intervention_history) > 100:
            self.intervention_history = self.intervention_history[-100:]

        logger.info(f"记录人工干预: {request.request_id}")

    def _infer_next_agent(
        self, intervention_type: InterventionType, processed_response: Dict[str, Any]
    ) -> Optional[str]:
        """推断下一个智能体"""
        decision = processed_response.get("decision", "").lower()

        # 基于干预类型的默认路由
        default_routes = {
            InterventionType.APPROVAL: "reporter",
            InterventionType.DECISION: "reporter",
            InterventionType.CORRECTION: "reviewer",
            InterventionType.GUIDANCE: "planner",
            InterventionType.REVIEW: "reporter",
        }

        # 基于决策内容的特殊路由
        if "retry" in decision or "重试" in decision:
            return "tester"
        elif "modify" in decision or "修改" in decision:
            return "coder"
        elif "review" in decision or "评审" in decision:
            return "reviewer"
        elif "plan" in decision or "规划" in decision:
            return "planner"

        # 返回默认路由
        return default_routes.get(intervention_type, "reporter")

    def get_intervention_history(self) -> List[Dict[str, Any]]:
        """获取干预历史"""
        return self.intervention_history.copy()

    def clear_intervention_history(self):
        """清空干预历史"""
        self.intervention_history.clear()
        logger.info("干预历史已清空")

    def create_intervention_request(
        self,
        intervention_type: str,
        priority: str,
        question: str,
        options: List[str] = None,
        timeout_seconds: int = None,
    ) -> HumanInterventionRequest:
        """创建干预请求的便捷方法"""
        try:
            intervention_type_enum = InterventionType(intervention_type)
        except ValueError:
            intervention_type_enum = InterventionType.DECISION

        try:
            priority_enum = InterventionPriority(priority)
        except ValueError:
            priority_enum = InterventionPriority.MEDIUM

        context = self.get_context_from_global_state()

        return HumanInterventionRequest(
            intervention_type=intervention_type_enum,
            priority=priority_enum,
            context=context,
            question=question,
            options=options or [],
            timeout_seconds=timeout_seconds or self.default_timeout,
        )


def create_human_agent(global_state: GlobalState) -> HumanAgent:
    """创建Human智能体实例"""
    return HumanAgent(global_state)


# 便捷函数
def request_human_approval(
    global_state: GlobalState, question: str, timeout_seconds: int = 300
) -> HumanInterventionRequest:
    """请求人工批准"""
    human_agent = create_human_agent(global_state)
    return human_agent.create_intervention_request(
        intervention_type="approval",
        priority="medium",
        question=question,
        options=["approve", "reject"],
        timeout_seconds=timeout_seconds,
    )


def request_human_decision(
    global_state: GlobalState,
    question: str,
    options: List[str],
    timeout_seconds: int = 300,
) -> HumanInterventionRequest:
    """请求人工决策"""
    human_agent = create_human_agent(global_state)
    return human_agent.create_intervention_request(
        intervention_type="decision",
        priority="medium",
        question=question,
        options=options,
        timeout_seconds=timeout_seconds,
    )


def request_human_review(
    global_state: GlobalState, content: str, timeout_seconds: int = 600
) -> HumanInterventionRequest:
    """请求人工审查"""
    human_agent = create_human_agent(global_state)
    return human_agent.create_intervention_request(
        intervention_type="review",
        priority="high",
        question=f"请审查以下内容：\n\n{content}",
        options=["pass", "fail"],
        timeout_seconds=timeout_seconds,
    )
