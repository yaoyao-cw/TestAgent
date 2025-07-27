#!/usr/bin/env python3
"""
工作流工具模块
包含节点间移交和工作流控制的工具
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage

from ..models.state import TestAgentState, TaskType
from ..models.execution import ExecutionPlan
from .decorators import tool, rate_limit, validate_input
from ..exceptions import WorkflowException

logger = logging.getLogger(__name__)


class WorkflowTools:
    """工作流工具类"""

    def __init__(self):
        """初始化工作流工具"""
        self.name = "workflow_tools"
        self.description = "工作流控制和节点移交工具"
        logger.info("WorkflowTools initialized")

    @tool(name="handoff_to_planner")
    @validate_input(required_fields=["task_type", "task_topic"])
    async def handoff_to_planner(
        self,
        task_type: TaskType,
        task_topic: str,
        locale: str = "zh-CN",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        移交任务给规划器

        Args:
            task_type: 任务类型
            task_topic: 任务主题
            locale: 语言设置
            additional_context: 额外上下文信息

        Returns:
            移交结果
        """
        try:
            logger.info(f"Handing off to planner: {task_type.value} - {task_topic}")

            # 构建移交信息
            handoff_info = {
                "success": True,
                "target_node": "planner",
                "task_type": task_type,
                "task_topic": task_topic,
                "locale": locale,
                "additional_context": additional_context,
                "timestamp": (
                    logger.handlers[0].formatter.formatTime(
                        logger.makeRecord("workflow", logging.INFO, "", 0, "", (), None)
                    )
                    if logger.handlers
                    else None
                ),
            }

            # 生成移交消息
            if locale == "zh-CN":
                message = f"""✅ 任务已移交给规划器

**任务类型**: {self._get_task_type_name(task_type, locale)}
**任务主题**: {task_topic}
**语言设置**: {locale}

规划器将为您创建详细的执行计划。"""
            else:
                message = f"""✅ Task handed off to planner

**Task Type**: {self._get_task_type_name(task_type, locale)}
**Task Topic**: {task_topic}
**Language**: {locale}

The planner will create a detailed execution plan for you."""

            handoff_info["message"] = message

            logger.info(f"Successfully handed off task to planner: {task_type.value}")
            return handoff_info

        except Exception as e:
            logger.error(f"Failed to handoff to planner: {e}")
            return {
                "success": False,
                "error": f"移交给规划器失败: {e}",
                "target_node": "planner",
                "task_type": task_type,
                "task_topic": task_topic,
            }

    @tool(name="handoff_to_research_team")
    @validate_input(required_fields=["execution_plan"])
    async def handoff_to_research_team(
        self,
        execution_plan: ExecutionPlan,
        current_step: int = 0,
        additional_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        移交任务给研究团队

        Args:
            execution_plan: 执行计划
            current_step: 当前步骤索引
            additional_instructions: 额外指令

        Returns:
            移交结果
        """
        try:
            logger.info(f"Handing off to research team: step {current_step}")

            if current_step >= len(execution_plan.steps):
                raise WorkflowException("步骤索引超出范围")

            current_step_info = execution_plan.steps[current_step]

            handoff_info = {
                "success": True,
                "target_node": "research_team",
                "execution_plan": execution_plan,
                "current_step": current_step,
                "step_info": current_step_info,
                "additional_instructions": additional_instructions,
            }

            # 生成移交消息
            if execution_plan.locale == "zh-CN":
                message = f"""🔬 任务已移交给研究团队

**当前步骤**: {current_step + 1}/{len(execution_plan.steps)}
**步骤标题**: {current_step_info.title}
**步骤类型**: {current_step_info.step_type.value}
**步骤描述**: {current_step_info.description}

研究团队将执行此步骤并收集相关信息。"""
            else:
                message = f"""🔬 Task handed off to research team

**Current Step**: {current_step + 1}/{len(execution_plan.steps)}
**Step Title**: {current_step_info.title}
**Step Type**: {current_step_info.step_type.value}
**Step Description**: {current_step_info.description}

The research team will execute this step and gather relevant information."""

            handoff_info["message"] = message

            logger.info(
                f"Successfully handed off to research team: {current_step_info.title}"
            )
            return handoff_info

        except Exception as e:
            logger.error(f"Failed to handoff to research team: {e}")
            return {
                "success": False,
                "error": f"移交给研究团队失败: {e}",
                "target_node": "research_team",
                "current_step": current_step,
            }

    @tool(name="handoff_to_reporter")
    @validate_input(required_fields=["observations"])
    async def handoff_to_reporter(
        self,
        observations: list,
        task_type: TaskType,
        locale: str = "zh-CN",
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> Dict[str, Any]:
        """
        移交任务给报告员

        Args:
            observations: 观察结果列表
            task_type: 任务类型
            locale: 语言设置
            execution_plan: 执行计划

        Returns:
            移交结果
        """
        try:
            logger.info(
                f"Handing off to reporter with {len(observations)} observations"
            )

            handoff_info = {
                "success": True,
                "target_node": "reporter",
                "observations": observations,
                "task_type": task_type,
                "locale": locale,
                "execution_plan": execution_plan,
                "observation_count": len(observations),
            }

            # 生成移交消息
            if locale == "zh-CN":
                message = f"""📝 任务已移交给报告员

**任务类型**: {self._get_task_type_name(task_type, locale)}
**观察结果数量**: {len(observations)}
**语言设置**: {locale}

报告员将汇总所有研究结果并生成最终报告。"""
            else:
                message = f"""📝 Task handed off to reporter

**Task Type**: {self._get_task_type_name(task_type, locale)}
**Observation Count**: {len(observations)}
**Language**: {locale}

The reporter will summarize all research results and generate the final report."""

            handoff_info["message"] = message

            logger.info(f"Successfully handed off to reporter")
            return handoff_info

        except Exception as e:
            logger.error(f"Failed to handoff to reporter: {e}")
            return {
                "success": False,
                "error": f"移交给报告员失败: {e}",
                "target_node": "reporter",
                "observation_count": len(observations) if observations else 0,
            }

    @tool(name="handoff_to_reviewer")
    @validate_input(required_fields=["final_report"])
    async def handoff_to_reviewer(
        self,
        final_report: str,
        task_type: TaskType,
        locale: str = "zh-CN",
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> Dict[str, Any]:
        """
        移交任务给评审员

        Args:
            final_report: 最终报告
            task_type: 任务类型
            locale: 语言设置
            execution_plan: 执行计划

        Returns:
            移交结果
        """
        try:
            logger.info("Handing off to reviewer for final evaluation")

            handoff_info = {
                "success": True,
                "target_node": "reviewer",
                "final_report": final_report,
                "task_type": task_type,
                "locale": locale,
                "execution_plan": execution_plan,
                "report_length": len(final_report),
            }

            # 生成移交消息
            if locale == "zh-CN":
                message = f"""⭐ 任务已移交给评审员

**任务类型**: {self._get_task_type_name(task_type, locale)}
**报告长度**: {len(final_report)} 字符
**语言设置**: {locale}

评审员将对最终报告进行质量评估并提供改进建议。"""
            else:
                message = f"""⭐ Task handed off to reviewer

**Task Type**: {self._get_task_type_name(task_type, locale)}
**Report Length**: {len(final_report)} characters
**Language**: {locale}

The reviewer will evaluate the final report quality and provide improvement suggestions."""

            handoff_info["message"] = message

            logger.info("Successfully handed off to reviewer")
            return handoff_info

        except Exception as e:
            logger.error(f"Failed to handoff to reviewer: {e}")
            return {
                "success": False,
                "error": f"移交给评审员失败: {e}",
                "target_node": "reviewer",
                "report_length": len(final_report) if final_report else 0,
            }

    def _get_task_type_name(self, task_type: TaskType, locale: str) -> str:
        """获取任务类型的显示名称"""
        if locale == "zh-CN":
            task_names = {
                TaskType.TEST_CASE_GENERATION: "测试用例生成",
                TaskType.TEST_SCRIPT_GENERATION: "测试脚本生成",
                TaskType.REQUIREMENT_EXTRACTION: "需求内容提取",
                TaskType.TEST_SCRIPT_EXECUTION: "测试脚本执行",
            }
        else:
            task_names = {
                TaskType.TEST_CASE_GENERATION: "Test Case Generation",
                TaskType.TEST_SCRIPT_GENERATION: "Test Script Generation",
                TaskType.REQUIREMENT_EXTRACTION: "Requirement Extraction",
                TaskType.TEST_SCRIPT_EXECUTION: "Test Script Execution",
            }

        return task_names.get(task_type, task_type.value)

    @tool(name="check_workflow_status")
    async def check_workflow_status(self, state: TestAgentState) -> Dict[str, Any]:
        """
        检查工作流状态

        Args:
            state: 当前状态

        Returns:
            状态信息
        """
        try:
            status_info = {
                "success": True,
                "locale": state.locale,
                "task_type": state.task_type.value if state.task_type else None,
                "task_topic": state.task_topic,
                "plan_iterations": state.plan_iterations,
                "has_plan": state.current_plan is not None,
                "observation_count": len(state.observations),
                "has_final_report": bool(state.final_report),
                "has_review": state.review_score is not None,
            }

            # 计算进度
            total_steps = (
                5  # coordinator -> planner -> research -> reporter -> reviewer
            )
            completed_steps = 1  # coordinator已完成

            if status_info["has_plan"]:
                completed_steps += 1
            if status_info["observation_count"] > 0:
                completed_steps += 1
            if status_info["has_final_report"]:
                completed_steps += 1
            if status_info["has_review"]:
                completed_steps += 1

            status_info["progress"] = completed_steps / total_steps
            status_info["progress_percentage"] = int(status_info["progress"] * 100)

            logger.info(
                f"Workflow status: {status_info['progress_percentage']}% complete"
            )
            return status_info

        except Exception as e:
            logger.error(f"Failed to check workflow status: {e}")
            return {"success": False, "error": f"检查工作流状态失败: {e}"}

    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "version": "1.0.0",
            "tools": [
                "handoff_to_planner",
                "handoff_to_research_team",
                "handoff_to_reporter",
                "handoff_to_reviewer",
                "check_workflow_status",
            ],
            "category": "workflow",
        }
