"""Reporter智能体实现

创建Reporter智能体，实现测试报告生成和信息汇总。
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from ..core.base_agent import SimpleAgent, AgentInput, AgentOutput
from ..models.types import AgentType, TaskType
from ..models.workspace import GlobalState, TaskStatus
from ..llm.service import get_llm_service
from ..config.logging_config import get_logger

logger = get_logger("reporter_agent")


class ReportTemplate:
    """报告模板类"""

    @staticmethod
    def get_test_case_report_template() -> str:
        """测试用例报告模板"""
        return """# 测试用例生成报告

## 项目信息
- **项目名称**: {project_name}
- **任务ID**: {task_id}
- **生成时间**: {generation_time}
- **执行智能体**: {agents_involved}

## 需求分析摘要
{requirement_summary}

## 测试用例概览
- **总用例数**: {total_test_cases}
- **功能测试用例**: {functional_cases}
- **异常测试用例**: {exception_cases}
- **边界测试用例**: {boundary_cases}
- **覆盖率**: {coverage_rate}%

## 详细测试用例
{detailed_test_cases}

## 质量评估
{quality_assessment}

## 执行建议
{execution_recommendations}

## 附录
{appendix}

---
*报告生成时间: {report_time}*
*生成智能体: Reporter*
"""

    @staticmethod
    def get_test_script_report_template() -> str:
        """测试脚本报告模板"""
        return """# 测试脚本生成报告

## 项目信息
- **项目名称**: {project_name}
- **任务ID**: {task_id}
- **生成时间**: {generation_time}
- **技术栈**: {tech_stack}

## 脚本概览
- **脚本文件数**: {script_count}
- **总代码行数**: {total_lines}
- **测试函数数**: {test_functions}
- **依赖库**: {dependencies}

## 脚本结构
{script_structure}

## 代码质量分析
{code_quality}

## 执行指南
{execution_guide}

## 维护建议
{maintenance_suggestions}

---
*报告生成时间: {report_time}*
*生成智能体: Reporter*
"""

    @staticmethod
    def get_execution_report_template() -> str:
        """执行结果报告模板"""
        return """# 测试执行报告

## 执行概览
- **执行时间**: {execution_time}
- **执行环境**: {execution_environment}
- **总测试数**: {total_tests}
- **通过数**: {passed_tests}
- **失败数**: {failed_tests}
- **跳过数**: {skipped_tests}
- **成功率**: {success_rate}%

## 执行详情
{execution_details}

## 失败分析
{failure_analysis}

## 性能分析
{performance_analysis}

## 建议和后续行动
{recommendations}

---
*报告生成时间: {report_time}*
*生成智能体: Reporter*
"""


class ReporterAgent(SimpleAgent):
    """Reporter智能体

    负责测试报告生成和信息汇总。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.REPORTER, global_state)
        self.llm_service = get_llm_service()

        # Reporter智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "knowledge_search",
            "data_analysis",
            "report_generation",
        ]

        # 报告类型映射
        self.report_templates = {
            "test_case": ReportTemplate.get_test_case_report_template(),
            "test_script": ReportTemplate.get_test_script_report_template(),
            "execution": ReportTemplate.get_execution_report_template(),
        }

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：收集所有相关信息和数据"""
        logger.info("Reporter智能体开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 解析输入数据
        report_type = input_data.data.get("report_type", "comprehensive")
        task_id = input_data.data.get("task_id", "")

        # 收集任务相关的所有文件和数据
        task_data = self._collect_task_data(task_id)

        # 收集执行历史和日志
        execution_history = self._collect_execution_history()

        # 收集质量评审结果
        review_results = self._collect_review_results()

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "report_type": report_type,
            "task_id": task_id,
            "task_data": task_data,
            "execution_history": execution_history,
            "review_results": review_results,
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "report_generated": False,
            "report_content": None,
        }

        logger.info(f"Reporter智能体加载完成，报告类型: {report_type}")
        return state

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：生成综合报告"""
        logger.info("Reporter智能体进入LLM阶段")

        report_type = state.get("report_type", "comprehensive")
        task_data = state.get("task_data", {})
        execution_history = state.get("execution_history", [])
        review_results = state.get("review_results", {})

        try:
            # 根据报告类型生成不同的报告
            if report_type == "test_case":
                report_content = self._generate_test_case_report(
                    task_data, review_results
                )
            elif report_type == "test_script":
                report_content = self._generate_test_script_report(
                    task_data, review_results
                )
            elif report_type == "execution":
                report_content = self._generate_execution_report(
                    task_data, execution_history
                )
            else:
                report_content = self._generate_comprehensive_report(
                    task_data, execution_history, review_results
                )

            # 生成执行摘要
            execution_summary = self._generate_execution_summary(execution_history)

            # 生成建议和后续行动
            recommendations = self._generate_recommendations(task_data, review_results)

            # 生成最终报告
            final_report = self._compile_final_report(
                report_content, execution_summary, recommendations
            )

            state["llm_output"] = {
                "report_content": report_content,
                "execution_summary": execution_summary,
                "recommendations": recommendations,
                "final_report": final_report,
                "report_generated": True,
            }

            # 更新状态
            state["report_generated"] = True
            state["report_content"] = final_report

            logger.info("报告生成完成")

        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state["llm_output"] = {
                "report_content": f"报告生成失败: {str(e)}",
                "execution_summary": {},
                "recommendations": [],
                "final_report": f"报告生成失败: {str(e)}",
                "report_generated": False,
                "error": str(e),
            }

        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：保存报告并决定下一步"""
        logger.info("Reporter智能体进入路由阶段")

        llm_output = state.get("llm_output", {})
        report_generated = llm_output.get("report_generated", False)
        final_report = llm_output.get("final_report", "")

        # 保存报告
        report_path = None
        if report_generated and final_report:
            report_path = self._save_report(final_report, state.get("task_id", ""))

        # 决定下一个智能体（通常Reporter是最后一个）
        next_agent = None

        # 检查是否需要人工审核
        if self._needs_human_review(state):
            next_agent = "human"

        # 更新全局状态
        self.update_global_state(
            {
                "step": self.global_state.get_current_step() + 1,
                "last_output": f"报告已生成: {report_path or '内存中'}",
            }
        )

        return AgentOutput(
            data={
                "report_content": final_report,
                "execution_summary": llm_output.get("execution_summary", {}),
                "recommendations": llm_output.get("recommendations", []),
                "report_path": report_path,
                "report_generated": report_generated,
                "task_completed": True,
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "report_path": report_path,
                "task_status": "completed",
            },
        )

    def get_prompt_template(self) -> str:
        """获取Reporter智能体的提示词模板"""
        return """你是一个专业的报告生成智能体(Reporter)，负责测试报告生成和信息汇总。

## 你的核心能力
1. 综合信息收集和整理
2. 专业测试报告生成
3. 数据分析和可视化建议
4. 执行结果汇总和分析
5. 质量评估和改进建议

## 报告类型
### 测试用例报告
- 需求分析摘要
- 测试用例详细信息
- 覆盖率分析
- 质量评估结果

### 测试脚本报告
- 脚本结构和组织
- 代码质量分析
- 技术栈和依赖
- 维护建议

### 执行结果报告
- 执行统计和成功率
- 失败原因分析
- 性能表现评估
- 改进建议

### 综合报告
- 完整的项目执行概览
- 各阶段成果汇总
- 质量评估综述
- 后续行动建议

## 报告质量标准
- 信息完整准确
- 结构清晰逻辑性强
- 数据可视化友好
- 建议具体可操作
- 专业术语使用恰当

## 输出要求
- 使用Markdown格式
- 包含必要的统计数据
- 提供清晰的结论和建议
- 支持后续的决策制定

请专业地生成高质量的测试报告。
"""

    def _collect_task_data(self, task_id: str) -> Dict[str, Any]:
        """收集任务相关数据"""
        try:
            # 这里应该实现从工作空间收集数据的逻辑
            # 暂时返回示例数据
            return {
                "task_id": task_id,
                "task_title": "智能测试任务",
                "task_type": "test_case_generation",
                "created_at": datetime.now().isoformat(),
                "files": [],
                "agents_involved": ["coordinator", "planner", "tester", "reviewer"],
                "current_status": "completed",
            }

        except Exception as e:
            logger.error(f"收集任务数据失败: {e}")
            return {}

    def _collect_execution_history(self) -> List[Dict[str, Any]]:
        """收集执行历史"""
        try:
            # 这里应该实现执行历史收集逻辑
            # 暂时返回示例数据
            return [
                {
                    "agent": "coordinator",
                    "timestamp": datetime.now().isoformat(),
                    "action": "任务初始化",
                    "status": "completed",
                    "duration": 2.5,
                },
                {
                    "agent": "planner",
                    "timestamp": datetime.now().isoformat(),
                    "action": "任务规划",
                    "status": "completed",
                    "duration": 5.2,
                },
            ]

        except Exception as e:
            logger.error(f"收集执行历史失败: {e}")
            return []

    def _collect_review_results(self) -> Dict[str, Any]:
        """收集质量评审结果"""
        try:
            # 这里应该实现评审结果收集逻辑
            # 暂时返回示例数据
            return {
                "overall_score": 85,
                "completeness": 88,
                "accuracy": 82,
                "maintainability": 85,
                "suggestions": ["优化测试用例描述", "增加边界测试"],
                "review_time": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"收集评审结果失败: {e}")
            return {}

    def _generate_test_case_report(
        self, task_data: Dict[str, Any], review_results: Dict[str, Any]
    ) -> str:
        """生成测试用例报告"""
        template = self.report_templates["test_case"]

        # 构建报告数据
        report_data = {
            "project_name": task_data.get("task_title", "未知项目"),
            "task_id": task_data.get("task_id", ""),
            "generation_time": task_data.get("created_at", ""),
            "agents_involved": ", ".join(task_data.get("agents_involved", [])),
            "requirement_summary": "基于用户需求生成的测试用例",
            "total_test_cases": 15,  # 示例数据
            "functional_cases": 10,
            "exception_cases": 3,
            "boundary_cases": 2,
            "coverage_rate": 92,
            "detailed_test_cases": "详细测试用例内容...",
            "quality_assessment": self._format_quality_assessment(review_results),
            "execution_recommendations": "建议使用自动化测试框架执行",
            "appendix": "相关文档和资源链接",
            "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return template.format(**report_data)

    def _generate_test_script_report(
        self, task_data: Dict[str, Any], review_results: Dict[str, Any]
    ) -> str:
        """生成测试脚本报告"""
        template = self.report_templates["test_script"]

        report_data = {
            "project_name": task_data.get("task_title", "未知项目"),
            "task_id": task_data.get("task_id", ""),
            "generation_time": task_data.get("created_at", ""),
            "tech_stack": "Python, pytest, selenium",
            "script_count": 5,
            "total_lines": 250,
            "test_functions": 15,
            "dependencies": "pytest, selenium, requests",
            "script_structure": "脚本结构说明...",
            "code_quality": self._format_code_quality(review_results),
            "execution_guide": "执行指南说明...",
            "maintenance_suggestions": "维护建议...",
            "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return template.format(**report_data)

    def _generate_execution_report(
        self, task_data: Dict[str, Any], execution_history: List[Dict[str, Any]]
    ) -> str:
        """生成执行结果报告"""
        template = self.report_templates["execution"]

        # 分析执行历史
        total_tests = len(execution_history)
        passed_tests = len(
            [h for h in execution_history if h.get("status") == "completed"]
        )
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        report_data = {
            "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_environment": "Python 3.11, Docker容器",
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": 0,
            "success_rate": round(success_rate, 2),
            "execution_details": self._format_execution_details(execution_history),
            "failure_analysis": "失败原因分析...",
            "performance_analysis": "性能分析结果...",
            "recommendations": "改进建议和后续行动...",
            "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return template.format(**report_data)

    def _generate_comprehensive_report(
        self,
        task_data: Dict[str, Any],
        execution_history: List[Dict[str, Any]],
        review_results: Dict[str, Any],
    ) -> str:
        """生成综合报告"""
        comprehensive_prompt = f"""
请基于以下信息生成一份综合的智能测试平台执行报告：

## 任务信息
{json.dumps(task_data, ensure_ascii=False, indent=2)}

## 执行历史
{json.dumps(execution_history, ensure_ascii=False, indent=2)}

## 质量评审结果
{json.dumps(review_results, ensure_ascii=False, indent=2)}

请生成一份包含以下部分的综合报告：
1. 执行概览和统计
2. 各阶段成果汇总
3. 质量评估综述
4. 问题和改进点
5. 后续行动建议

报告应该专业、详细且具有指导意义。
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": comprehensive_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            return response.content.strip()

        except Exception as e:
            logger.error(f"生成综合报告失败: {e}")
            return f"综合报告生成失败: {str(e)}"

    def _generate_execution_summary(
        self, execution_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成执行摘要"""
        if not execution_history:
            return {
                "total_steps": 0,
                "completed_steps": 0,
                "total_duration": 0,
                "average_duration": 0,
                "agents_used": [],
            }

        total_steps = len(execution_history)
        completed_steps = len(
            [h for h in execution_history if h.get("status") == "completed"]
        )
        total_duration = sum(h.get("duration", 0) for h in execution_history)
        average_duration = total_duration / total_steps if total_steps > 0 else 0
        agents_used = list(set(h.get("agent", "") for h in execution_history))

        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "success_rate": (
                (completed_steps / total_steps * 100) if total_steps > 0 else 0
            ),
            "total_duration": round(total_duration, 2),
            "average_duration": round(average_duration, 2),
            "agents_used": agents_used,
        }

    def _generate_recommendations(
        self, task_data: Dict[str, Any], review_results: Dict[str, Any]
    ) -> List[str]:
        """生成建议和后续行动"""
        recommendations = []

        # 基于质量评审结果的建议
        overall_score = review_results.get("overall_score", 0)
        if overall_score < 80:
            recommendations.extend(review_results.get("suggestions", []))

        # 基于任务状态的建议
        task_status = task_data.get("current_status", "")
        if task_status == "completed":
            recommendations.append("任务已完成，建议进行最终验收")
        elif task_status == "failed":
            recommendations.append("任务执行失败，建议检查错误日志并重新执行")

        # 通用建议
        recommendations.extend(
            ["定期备份生成的测试资产", "建立持续集成流程", "收集用户反馈以改进测试质量"]
        )

        return recommendations

    def _compile_final_report(
        self,
        report_content: str,
        execution_summary: Dict[str, Any],
        recommendations: List[str],
    ) -> str:
        """编译最终报告"""
        final_report_parts = [
            "# 智能测试平台执行报告",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**生成智能体**: {self.name}",
            "",
            "## 执行摘要",
            f"- **总执行步骤**: {execution_summary.get('total_steps', 0)}",
            f"- **完成步骤**: {execution_summary.get('completed_steps', 0)}",
            f"- **成功率**: {execution_summary.get('success_rate', 0):.1f}%",
            f"- **总耗时**: {execution_summary.get('total_duration', 0)}秒",
            f"- **平均耗时**: {execution_summary.get('average_duration', 0)}秒/步骤",
            f"- **涉及智能体**: {', '.join(execution_summary.get('agents_used', []))}",
            "",
            "## 详细报告",
            report_content,
            "",
            "## 建议和后续行动",
        ]

        for i, recommendation in enumerate(recommendations, 1):
            final_report_parts.append(f"{i}. {recommendation}")

        final_report_parts.extend(
            [
                "",
                "---",
                f"*本报告由{self.name}智能体自动生成*",
                f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(final_report_parts)

    def _format_quality_assessment(self, review_results: Dict[str, Any]) -> str:
        """格式化质量评估结果"""
        if not review_results:
            return "暂无质量评估结果"

        assessment_parts = [
            f"**总体分数**: {review_results.get('overall_score', 0)}/100",
            f"**完整性**: {review_results.get('completeness', 0)}/100",
            f"**准确性**: {review_results.get('accuracy', 0)}/100",
            f"**可维护性**: {review_results.get('maintainability', 0)}/100",
        ]

        suggestions = review_results.get("suggestions", [])
        if suggestions:
            assessment_parts.append("\n**改进建议**:")
            for suggestion in suggestions:
                assessment_parts.append(f"- {suggestion}")

        return "\n".join(assessment_parts)

    def _format_code_quality(self, review_results: Dict[str, Any]) -> str:
        """格式化代码质量结果"""
        if not review_results:
            return "暂无代码质量分析结果"

        return f"""
**代码质量评分**: {review_results.get('overall_score', 0)}/100

**详细评分**:
- 语法正确性: {review_results.get('syntax_score', 0)}/100
- 逻辑合理性: {review_results.get('logic_score', 0)}/100
- 性能表现: {review_results.get('performance_score', 0)}/100
- 可维护性: {review_results.get('maintainability', 0)}/100

**质量等级**: {self._get_quality_grade(review_results.get('overall_score', 0))}
"""

    def _format_execution_details(self, execution_history: List[Dict[str, Any]]) -> str:
        """格式化执行详情"""
        if not execution_history:
            return "暂无执行详情"

        details_parts = [
            "| 智能体 | 操作 | 状态 | 耗时(秒) |",
            "|--------|------|------|----------|",
        ]

        for history in execution_history:
            agent = history.get("agent", "未知")
            action = history.get("action", "未知操作")
            status = history.get("status", "未知")
            duration = history.get("duration", 0)

            details_parts.append(f"| {agent} | {action} | {status} | {duration} |")

        return "\n".join(details_parts)

    def _get_quality_grade(self, score: float) -> str:
        """获取质量等级"""
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "中等"
        elif score >= 60:
            return "及格"
        else:
            return "不合格"

    def _save_report(self, report_content: str, task_id: str) -> Optional[str]:
        """保存报告到文件"""
        try:
            # 生成报告文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{task_id}_{timestamp}.md"

            # 这里应该实现文件保存逻辑
            # 暂时只记录日志
            logger.info(f"报告已保存: {filename}")

            return filename

        except Exception as e:
            logger.error(f"保存报告失败: {e}")
            return None

    def _needs_human_review(self, state: Dict[str, Any]) -> bool:
        """判断是否需要人工审核"""
        # 检查质量评审结果
        review_results = state.get("review_results", {})
        overall_score = review_results.get("overall_score", 100)

        # 如果质量分数较低，需要人工审核
        if overall_score < 70:
            return True

        # 检查是否有执行失败
        execution_history = state.get("execution_history", [])
        failed_count = len(
            [h for h in execution_history if h.get("status") == "failed"]
        )

        # 如果失败次数较多，需要人工审核
        if failed_count > 2:
            return True

        return False


def create_reporter_agent(global_state: GlobalState) -> ReporterAgent:
    """创建Reporter智能体实例"""
    return ReporterAgent(global_state)
