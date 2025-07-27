"""Reviewer智能体实现

开发Reviewer智能体，支持代码质量评审和错误日志分析。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger
from ..core.base_agent import AgentInput, AgentOutput, SimpleAgent
from ..llm.service import get_llm_service
from ..models.review import (RequirementReview, ReviewScore, TestCaseReview,
                             TestScriptReview)
from ..models.types import AgentType, TaskType
from ..models.workspace import GlobalState, TaskStatus

logger = get_logger("reviewer_agent")


class ReviewerAgent(SimpleAgent):
    """Reviewer智能体

    负责代码质量评审、错误日志分析和质量保证工作流。
    """

    def __init__(self, global_state: GlobalState):
        super().__init__(AgentType.REVIEWER, global_state)
        self.llm_service = get_llm_service()

        # Reviewer智能体可用的工具
        self.available_tools = [
            "file_read",
            "file_write",
            "knowledge_search",
            "code_analysis",
            "quality_check",
        ]

        # 质量评估标准
        self.quality_standards = {
            "test_case": {
                "completeness_threshold": 80.0,
                "clarity_threshold": 75.0,
                "coverage_threshold": 85.0,
                "executability_threshold": 90.0,
            },
            "test_script": {
                "syntax_threshold": 95.0,
                "logic_threshold": 80.0,
                "performance_threshold": 70.0,
                "maintainability_threshold": 75.0,
            },
            "requirement": {
                "extraction_threshold": 85.0,
                "relevance_threshold": 80.0,
                "structure_threshold": 75.0,
                "completeness_threshold": 80.0,
            },
        }

    def load(self, input_data: AgentInput) -> Dict[str, Any]:
        """加载阶段：加载待评审的内容和评审标准"""
        logger.info("Reviewer智能体开始加载阶段")

        # 获取全局上下文
        context = self.get_context_from_global_state()

        # 解析输入数据
        review_type = input_data.data.get("review_type", "general")
        content_path = input_data.data.get("content_path", "")
        review_criteria = input_data.data.get("review_criteria", {})

        # 读取待评审内容
        content_to_review = self._load_content_for_review(content_path)

        # 获取相关的错误日志
        error_logs = self._load_error_logs()

        # 构建状态
        state = {
            "input_data": input_data.data,
            "context": context,
            "review_type": review_type,
            "content_path": content_path,
            "content_to_review": content_to_review,
            "review_criteria": review_criteria,
            "error_logs": error_logs,
            "quality_standards": self.quality_standards.get(review_type, {}),
            "prompt_template": self.get_prompt_template(),
            "available_tools": self.available_tools,
            "metadata": input_data.metadata or {},
            "review_completed": False,
            "review_result": None,
        }

        logger.info(f"Reviewer智能体加载完成，评审类型: {review_type}")
        return state

    def llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LLM阶段：执行质量评审和分析"""
        logger.info("Reviewer智能体进入LLM阶段")

        review_type = state.get("review_type", "general")
        content_to_review = state.get("content_to_review", "")
        error_logs = state.get("error_logs", [])
        quality_standards = state.get("quality_standards", {})

        try:
            # 根据评审类型执行不同的评审流程
            if review_type == "test_case":
                review_result = self._review_test_cases(
                    content_to_review, quality_standards
                )
            elif review_type == "test_script":
                review_result = self._review_test_scripts(
                    content_to_review, quality_standards
                )
            elif review_type == "requirement":
                review_result = self._review_requirements(
                    content_to_review, quality_standards
                )
            else:
                review_result = self._general_review(
                    content_to_review, quality_standards
                )

            # 分析错误日志
            error_analysis = self._analyze_error_logs(error_logs)

            # 生成改进建议
            improvement_suggestions = self._generate_improvement_suggestions(
                review_result, error_analysis
            )

            # 生成评审报告
            review_report = self._generate_review_report(
                review_result, error_analysis, improvement_suggestions
            )

            state["llm_output"] = {
                "review_result": review_result,
                "error_analysis": error_analysis,
                "improvement_suggestions": improvement_suggestions,
                "review_report": review_report,
                "review_completed": True,
            }

            # 更新状态
            state["review_completed"] = True
            state["review_result"] = review_result

            logger.info(f"评审完成，总体分数: {review_result.get('overall_score', 0)}")

        except Exception as e:
            logger.error(f"LLM阶段出错: {e}")
            state["llm_output"] = {
                "review_result": None,
                "error_analysis": {},
                "improvement_suggestions": [],
                "review_report": f"评审失败: {str(e)}",
                "review_completed": False,
                "error": str(e),
            }

        return state

    def router(self, state: Dict[str, Any]) -> AgentOutput:
        """路由阶段：根据评审结果决定下一步"""
        logger.info("Reviewer智能体进入路由阶段")

        llm_output = state.get("llm_output", {})
        review_completed = llm_output.get("review_completed", False)
        review_result = llm_output.get("review_result", {})

        # 决定下一个智能体
        next_agent = None
        if review_completed and review_result:
            overall_score = review_result.get("overall_score", 0)

            # 根据评审分数决定下一步
            if overall_score >= 80:
                # 质量良好，可以进入报告阶段
                next_agent = "reporter"
            elif overall_score >= 60:
                # 需要改进，返回相应的智能体
                review_type = state.get("review_type", "general")
                if review_type == "test_case":
                    next_agent = "tester"
                elif review_type == "test_script":
                    next_agent = "coder"
                else:
                    next_agent = "human"  # 需要人工干预
            else:
                # 质量不合格，需要人工干预
                next_agent = "human"

        # 保存评审报告
        if review_completed:
            self._save_review_report(llm_output.get("review_report", ""))

        # 更新全局状态
        self.update_global_state(
            {
                "step": self.global_state.get_current_step() + 1,
                "last_output": f"评审完成，分数: {review_result.get('overall_score', 0)}",
            }
        )

        return AgentOutput(
            data={
                "review_result": review_result,
                "error_analysis": llm_output.get("error_analysis", {}),
                "improvement_suggestions": llm_output.get(
                    "improvement_suggestions", []
                ),
                "review_report": llm_output.get("review_report", ""),
                "review_completed": review_completed,
                "next_action": self._get_next_action_recommendation(review_result),
            },
            next_agent=next_agent,
            metadata={
                "agent": self.name,
                "phase_completed": True,
                "review_score": (
                    review_result.get("overall_score", 0) if review_result else 0
                ),
            },
        )

    def get_prompt_template(self) -> str:
        """获取Reviewer智能体的提示词模板"""
        return """你是一个专业的质量评审智能体(Reviewer)，负责代码质量评审和错误日志分析。

## 你的核心能力
1. 测试用例质量评估和改进建议
2. 测试脚本代码审查和优化建议
3. 需求提取质量分析和完善建议
4. 错误日志分析和问题诊断
5. 质量保证工作流程管理

## 评审维度
### 测试用例评审
- 完整性：测试用例是否覆盖所有功能点
- 清晰性：测试步骤是否清晰明确
- 覆盖度：是否覆盖正常、异常、边界情况
- 可执行性：测试用例是否可以实际执行

### 测试脚本评审
- 语法正确性：代码语法是否正确
- 逻辑合理性：测试逻辑是否合理
- 性能表现：执行效率和资源使用
- 可维护性：代码结构和可读性

### 需求提取评审
- 提取完整性：是否完整提取了需求信息
- 相关性：提取内容是否与需求相关
- 结构化程度：信息组织是否清晰结构化
- 准确性：提取信息是否准确无误

## 评分标准
- 90-100分：优秀，可以直接使用
- 80-89分：良好，有小幅改进空间
- 70-79分：中等，需要适度改进
- 60-69分：及格，需要较多改进
- 60分以下：不合格，需要重新制作

## 输出要求
- 详细的评审分析和分数
- 具体的改进建议和优化方案
- 错误问题的诊断和解决建议
- 质量保证的后续行动建议

请专业地进行质量评审并提供建设性的改进建议。
"""

    def _load_content_for_review(self, content_path: str) -> str:
        """加载待评审的内容"""
        try:
            if not content_path:
                return ""

            # 这里应该实现文件读取逻辑
            # 暂时返回示例内容
            return f"待评审内容来自: {content_path}"

        except Exception as e:
            logger.error(f"加载评审内容失败: {e}")
            return ""

    def _load_error_logs(self) -> List[Dict[str, Any]]:
        """加载错误日志"""
        try:
            # 这里应该实现错误日志读取逻辑
            # 暂时返回示例数据
            return [
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "message": "示例错误信息",
                    "agent": "tester",
                    "context": {},
                }
            ]

        except Exception as e:
            logger.error(f"加载错误日志失败: {e}")
            return []

    def _review_test_cases(
        self, content: str, standards: Dict[str, float]
    ) -> Dict[str, Any]:
        """评审测试用例"""
        # 构建测试用例评审提示
        review_prompt = f"""
请对以下测试用例进行专业评审：

## 测试用例内容
{content}

## 评审标准
- 完整性阈值: {standards.get('completeness_threshold', 80)}分
- 清晰度阈值: {standards.get('clarity_threshold', 75)}分  
- 覆盖度阈值: {standards.get('coverage_threshold', 85)}分
- 可执行性阈值: {standards.get('executability_threshold', 90)}分

请从以下维度进行评分（0-100分）：
1. 完整性：测试用例是否完整覆盖功能需求
2. 清晰度：测试步骤和预期结果是否清晰
3. 覆盖度：是否覆盖正常、异常、边界情况
4. 可执行性：测试用例是否具备可执行性

请提供：
- 各维度具体分数和理由
- 总体评价和建议
- 具体的改进措施
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": review_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            review_text = response.content.strip()

            # 解析评审结果
            return self._parse_review_result(review_text, "test_case")

        except Exception as e:
            logger.error(f"测试用例评审失败: {e}")
            return {
                "overall_score": 0,
                "completeness": 0,
                "clarity": 0,
                "coverage": 0,
                "executability": 0,
                "suggestions": [f"评审失败: {str(e)}"],
                "details": {"error": str(e)},
            }

    def _review_test_scripts(
        self, content: str, standards: Dict[str, float]
    ) -> Dict[str, Any]:
        """评审测试脚本"""
        review_prompt = f"""
请对以下测试脚本进行专业评审：

## 测试脚本内容
{content}

## 评审标准
- 语法正确性阈值: {standards.get('syntax_threshold', 95)}分
- 逻辑合理性阈值: {standards.get('logic_threshold', 80)}分
- 性能表现阈值: {standards.get('performance_threshold', 70)}分
- 可维护性阈值: {standards.get('maintainability_threshold', 75)}分

请从以下维度进行评分（0-100分）：
1. 语法正确性：代码语法是否正确无误
2. 逻辑合理性：测试逻辑是否合理有效
3. 性能表现：执行效率和资源使用情况
4. 可维护性：代码结构、注释和可读性

请提供：
- 各维度具体分数和理由
- 代码质量分析
- 性能优化建议
- 可维护性改进措施
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": review_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            review_text = response.content.strip()

            return self._parse_review_result(review_text, "test_script")

        except Exception as e:
            logger.error(f"测试脚本评审失败: {e}")
            return {
                "overall_score": 0,
                "syntax_score": 0,
                "logic_score": 0,
                "performance_score": 0,
                "maintainability": 0,
                "suggestions": [f"评审失败: {str(e)}"],
                "details": {"error": str(e)},
            }

    def _review_requirements(
        self, content: str, standards: Dict[str, float]
    ) -> Dict[str, Any]:
        """评审需求提取"""
        review_prompt = f"""
请对以下需求提取结果进行专业评审：

## 需求提取内容
{content}

## 评审标准
- 提取完整性阈值: {standards.get('extraction_threshold', 85)}分
- 相关性阈值: {standards.get('relevance_threshold', 80)}分
- 结构化程度阈值: {standards.get('structure_threshold', 75)}分
- 准确性阈值: {standards.get('completeness_threshold', 80)}分

请从以下维度进行评分（0-100分）：
1. 提取完整性：是否完整提取了需求信息
2. 相关性：提取内容是否与原始需求相关
3. 结构化程度：信息组织是否清晰结构化
4. 准确性：提取信息是否准确无误

请提供：
- 各维度具体分数和理由
- 需求分析质量评价
- 信息完善建议
- 结构优化方案
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": review_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            review_text = response.content.strip()

            return self._parse_review_result(review_text, "requirement")

        except Exception as e:
            logger.error(f"需求评审失败: {e}")
            return {
                "overall_score": 0,
                "extraction_score": 0,
                "relevance_score": 0,
                "structure_score": 0,
                "completeness": 0,
                "suggestions": [f"评审失败: {str(e)}"],
                "details": {"error": str(e)},
            }

    def _general_review(
        self, content: str, standards: Dict[str, float]
    ) -> Dict[str, Any]:
        """通用评审"""
        review_prompt = f"""
请对以下内容进行通用质量评审：

## 评审内容
{content}

请从以下维度进行评分（0-100分）：
1. 完整性：内容是否完整
2. 准确性：信息是否准确
3. 可维护性：结构是否清晰易维护

请提供：
- 各维度具体分数和理由
- 总体质量评价
- 改进建议
"""

        try:
            messages = [
                {"role": "system", "content": self.get_prompt_template()},
                {"role": "user", "content": review_prompt},
            ]

            response = self.llm_service.invoke_sync(
                messages, agent_type=self.agent_type
            )
            review_text = response.content.strip()

            return self._parse_review_result(review_text, "general")

        except Exception as e:
            logger.error(f"通用评审失败: {e}")
            return {
                "overall_score": 0,
                "completeness": 0,
                "accuracy": 0,
                "maintainability": 0,
                "suggestions": [f"评审失败: {str(e)}"],
                "details": {"error": str(e)},
            }

    def _analyze_error_logs(self, error_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析错误日志"""
        if not error_logs:
            return {"error_count": 0, "error_patterns": [], "recommendations": []}

        # 统计错误类型和频率
        error_types = {}
        for log in error_logs:
            error_type = log.get("level", "UNKNOWN")
            error_types[error_type] = error_types.get(error_type, 0) + 1

        # 识别错误模式
        error_patterns = []
        for error_type, count in error_types.items():
            if count > 1:
                error_patterns.append(f"{error_type}: {count}次")

        # 生成建议
        recommendations = []
        if error_types.get("ERROR", 0) > 3:
            recommendations.append("错误频率较高，建议检查核心逻辑")
        if error_types.get("WARNING", 0) > 5:
            recommendations.append("警告信息较多，建议优化代码质量")

        return {
            "error_count": len(error_logs),
            "error_types": error_types,
            "error_patterns": error_patterns,
            "recommendations": recommendations,
            "latest_errors": error_logs[-5:] if len(error_logs) > 5 else error_logs,
        }

    def _generate_improvement_suggestions(
        self, review_result: Dict[str, Any], error_analysis: Dict[str, Any]
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 基于评审结果的建议
        overall_score = review_result.get("overall_score", 0)
        if overall_score < 80:
            suggestions.extend(review_result.get("suggestions", []))

        # 基于错误分析的建议
        suggestions.extend(error_analysis.get("recommendations", []))

        # 通用改进建议
        if overall_score < 60:
            suggestions.append("建议重新设计和实现")
        elif overall_score < 80:
            suggestions.append("建议进行针对性优化")

        return list(set(suggestions))  # 去重

    def _generate_review_report(
        self,
        review_result: Dict[str, Any],
        error_analysis: Dict[str, Any],
        improvement_suggestions: List[str],
    ) -> str:
        """生成评审报告"""
        report_parts = [
            "# 质量评审报告",
            f"**评审时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**评审智能体**: {self.name}",
            "",
            "## 评审结果",
            f"**总体分数**: {review_result.get('overall_score', 0)}/100",
            f"**质量等级**: {self._get_quality_grade(review_result.get('overall_score', 0))}",
            "",
        ]

        # 详细分数
        if "completeness" in review_result:
            report_parts.extend(
                [
                    "### 详细评分",
                    f"- 完整性: {review_result.get('completeness', 0)}/100",
                    f"- 准确性: {review_result.get('accuracy', 0)}/100",
                    f"- 可维护性: {review_result.get('maintainability', 0)}/100",
                    "",
                ]
            )

        # 错误分析
        if error_analysis.get("error_count", 0) > 0:
            report_parts.extend(
                [
                    "## 错误分析",
                    f"**错误总数**: {error_analysis.get('error_count', 0)}",
                    "**错误类型分布**:",
                ]
            )

            for error_type, count in error_analysis.get("error_types", {}).items():
                report_parts.append(f"- {error_type}: {count}次")

            report_parts.append("")

        # 改进建议
        if improvement_suggestions:
            report_parts.extend(
                [
                    "## 改进建议",
                ]
            )

            for i, suggestion in enumerate(improvement_suggestions, 1):
                report_parts.append(f"{i}. {suggestion}")

            report_parts.append("")

        # 结论和建议
        overall_score = review_result.get("overall_score", 0)
        if overall_score >= 80:
            conclusion = "质量良好，建议进入下一阶段"
        elif overall_score >= 60:
            conclusion = "质量合格，建议进行优化后继续"
        else:
            conclusion = "质量不合格，建议重新制作"

        report_parts.extend(
            ["## 结论", conclusion, "", "---", f"*本报告由{self.name}智能体自动生成*"]
        )

        return "\n".join(report_parts)

    def _parse_review_result(
        self, review_text: str, review_type: str
    ) -> Dict[str, Any]:
        """解析评审结果"""
        # 简单的解析逻辑，实际可以更复杂
        result = {
            "overall_score": 75,  # 默认分数
            "completeness": 75,
            "accuracy": 75,
            "maintainability": 75,
            "suggestions": [],
            "details": {"raw_review": review_text},
        }

        # 尝试从文本中提取分数
        lines = review_text.split("\n")
        for line in lines:
            line = line.strip()

            # 查找分数信息
            if "分数" in line or "评分" in line:
                # 简单的分数提取逻辑
                import re

                scores = re.findall(r"(\d+)", line)
                if scores:
                    score = int(scores[0])
                    if 0 <= score <= 100:
                        result["overall_score"] = score

            # 查找建议信息
            if line.startswith("-") or line.startswith("•") or "建议" in line:
                suggestion = line.lstrip("- •").strip()
                if suggestion and "建议" in suggestion:
                    result["suggestions"].append(suggestion)

        # 根据评审类型添加特定字段
        if review_type == "test_case":
            result.update(
                {
                    "clarity": result["completeness"],
                    "coverage": result["accuracy"],
                    "executability": result["maintainability"],
                }
            )
        elif review_type == "test_script":
            result.update(
                {
                    "syntax_score": result["completeness"],
                    "logic_score": result["accuracy"],
                    "performance_score": result["maintainability"],
                }
            )
        elif review_type == "requirement":
            result.update(
                {
                    "extraction_score": result["completeness"],
                    "relevance_score": result["accuracy"],
                    "structure_score": result["maintainability"],
                }
            )

        return result

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

    def _save_review_report(self, report: str):
        """保存评审报告"""
        try:
            # 这里应该实现文件保存逻辑
            # 暂时只记录日志
            logger.info("评审报告已生成")

        except Exception as e:
            logger.error(f"保存评审报告失败: {e}")

    def _get_next_action_recommendation(self, review_result: Dict[str, Any]) -> str:
        """获取下一步行动建议"""
        if not review_result:
            return "评审失败，建议人工检查"

        overall_score = review_result.get("overall_score", 0)

        if overall_score >= 80:
            return "质量良好，建议进入报告生成阶段"
        elif overall_score >= 60:
            return "质量合格，建议进行优化改进"
        else:
            return "质量不合格，建议重新制作或人工干预"


def create_reviewer_agent(global_state: GlobalState) -> ReviewerAgent:
    """创建Reviewer智能体实例"""
    return ReviewerAgent(global_state)
