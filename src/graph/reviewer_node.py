#!/usr/bin/env python3
"""
评审员节点实现
负责质量评估、测试用例评审和改进建议生成
"""

import re
import ast
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..models.state import TestAgentState
from ..models.execution import ExecutionStep, StepType
from ..models.types import TaskType
from ..models.review import ReviewScore
from ..llm.service import LLMService
from ..exceptions import TestAgentException

logger = logging.getLogger(__name__)


class ReviewerNode:
    """评审员节点 - 负责质量评估、测试用例评审和改进建议生成"""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service or self._get_llm_service()
        self.evaluation_criteria = self._load_evaluation_criteria()
        self.quality_thresholds = self._load_quality_thresholds()

    def _get_llm_service(self):
        """获取LLM服务"""
        try:
            return LLMService()
        except Exception as e:
            logger.warning(f"无法初始化LLM服务: {e}")
            return None

    def _load_evaluation_criteria(self) -> Dict[str, Dict[str, Any]]:
        """加载评估标准"""
        return {
            "test_case_quality": {
                "completeness": {
                    "weight": 0.3,
                    "description": "测试用例覆盖度和完整性",
                    "criteria": [
                        "是否覆盖主要功能场景",
                        "是否包含边界条件测试",
                        "是否考虑异常情况",
                        "是否有负面测试用例",
                    ],
                },
                "clarity": {
                    "weight": 0.25,
                    "description": "测试用例清晰度和可理解性",
                    "criteria": [
                        "步骤描述是否清晰明确",
                        "预期结果是否明确",
                        "测试数据是否合理",
                        "是否易于执行",
                    ],
                },
                "accuracy": {
                    "weight": 0.25,
                    "description": "测试用例准确性和有效性",
                    "criteria": [
                        "测试逻辑是否正确",
                        "断言是否合理",
                        "测试目标是否明确",
                        "是否能发现潜在问题",
                    ],
                },
                "maintainability": {
                    "weight": 0.2,
                    "description": "测试用例可维护性",
                    "criteria": [
                        "是否易于修改和扩展",
                        "是否有良好的组织结构",
                        "是否有适当的注释",
                        "是否遵循最佳实践",
                    ],
                },
            },
            "code_quality": {
                "syntax": {
                    "weight": 0.3,
                    "description": "代码语法正确性",
                    "criteria": [
                        "语法是否正确",
                        "导入语句是否完整",
                        "缩进是否规范",
                        "命名是否符合规范",
                    ],
                },
                "structure": {
                    "weight": 0.25,
                    "description": "代码结构和组织",
                    "criteria": [
                        "类和方法组织是否合理",
                        "代码层次是否清晰",
                        "是否有适当的封装",
                        "是否遵循设计模式",
                    ],
                },
                "readability": {
                    "weight": 0.25,
                    "description": "代码可读性",
                    "criteria": [
                        "变量命名是否有意义",
                        "注释是否充分",
                        "代码是否简洁明了",
                        "是否易于理解",
                    ],
                },
                "testability": {
                    "weight": 0.2,
                    "description": "代码可测试性",
                    "criteria": [
                        "是否易于单元测试",
                        "依赖是否可模拟",
                        "是否有清晰的输入输出",
                        "是否支持自动化测试",
                    ],
                },
            },
            "requirement_extraction": {
                "completeness": {
                    "weight": 0.35,
                    "description": "需求提取完整性",
                    "criteria": [
                        "是否提取了所有关键需求",
                        "是否包含功能性需求",
                        "是否包含非功能性需求",
                        "是否遗漏重要信息",
                    ],
                },
                "accuracy": {
                    "weight": 0.35,
                    "description": "需求提取准确性",
                    "criteria": [
                        "提取的需求是否准确",
                        "是否存在误解或曲解",
                        "是否与原文档一致",
                        "是否有错误的推断",
                    ],
                },
                "clarity": {
                    "weight": 0.3,
                    "description": "需求表达清晰度",
                    "criteria": [
                        "需求描述是否清晰",
                        "是否有歧义表达",
                        "是否易于理解",
                        "是否结构化组织",
                    ],
                },
            },
        }

    def _load_quality_thresholds(self) -> Dict[str, float]:
        """加载质量阈值"""
        return {
            "excellent": 0.9,  # 优秀
            "good": 0.8,  # 良好
            "acceptable": 0.7,  # 可接受
            "poor": 0.6,  # 较差
            "unacceptable": 0.5,  # 不可接受
        }

    async def process(self, state: TestAgentState) -> Dict[str, Any]:
        """
        处理评审任务

        Args:
            state: 包含报告和观察结果的系统状态

        Returns:
            Dict: 评审结果和更新后的状态信息
        """
        try:
            logger.info("评审员开始质量评估")

            # 获取任务信息
            task_topic = (
                state.get("task_topic") if isinstance(state, dict) else state.task_topic
            )
            task_type = (
                state.get("task_type") if isinstance(state, dict) else state.task_type
            )
            locale = (
                state.get("locale", "zh-CN")
                if isinstance(state, dict)
                else getattr(state, "locale", "zh-CN")
            )
            observations = (
                state.get("observations", [])
                if isinstance(state, dict)
                else state.observations
            )
            report = (
                state.get("report")
                if isinstance(state, dict)
                else getattr(state, "report", None)
            )

            # 执行质量评估
            review_result = await self._conduct_quality_review(
                task_topic=task_topic,
                task_type=task_type,
                observations=observations,
                report=report,
                locale=locale,
            )

            # 返回结果
            return {
                "review": review_result,
                "task_completed": True,
                "final_evaluation": True,
                "observations": observations,
            }

        except Exception as e:
            logger.error(f"评审员处理失败: {e}")
            return {
                "review": self._generate_error_review(
                    str(e), task_topic, task_type, locale
                ),
                "task_completed": True,
                "error": True,
                "observations": observations,
            }

    async def _conduct_quality_review(
        self,
        task_topic: str,
        task_type: str,
        observations: List[Dict],
        report: Dict,
        locale: str,
    ) -> Dict[str, Any]:
        """
        执行质量评审

        Args:
            task_topic: 任务主题
            task_type: 任务类型
            observations: 观察结果列表
            report: 生成的报告
            locale: 语言设置

        Returns:
            Dict: 评审结果
        """
        try:
            # 分析观察结果
            analysis = self._analyze_deliverables(observations)

            # 根据任务类型执行相应的评审
            if task_type == TaskType.TEST_CASE_GENERATION.value:
                quality_scores = await self._evaluate_test_cases(analysis, locale)
            elif task_type == TaskType.TEST_SCRIPT_GENERATION.value:
                quality_scores = await self._evaluate_test_scripts(analysis, locale)
            elif task_type == TaskType.REQUIREMENT_EXTRACTION.value:
                quality_scores = await self._evaluate_requirement_extraction(
                    analysis, locale
                )
            else:
                quality_scores = await self._evaluate_generic_quality(analysis, locale)

            # 生成改进建议
            improvement_suggestions = await self._generate_improvement_suggestions(
                quality_scores, analysis, locale
            )

            # 计算总体评分
            overall_score = self._calculate_overall_score(quality_scores)

            return {
                "type": "quality_review",
                "task_topic": task_topic,
                "task_type": task_type,
                "overall_score": overall_score,
                "quality_level": self._get_quality_level(overall_score),
                "detailed_scores": quality_scores,
                "improvement_suggestions": improvement_suggestions,
                "analysis_summary": analysis,
                "review_time": datetime.now().isoformat(),
                "locale": locale,
            }

        except Exception as e:
            logger.error(f"执行质量评审失败: {e}")
            return self._generate_error_review(str(e), task_topic, task_type, locale)

    def _analyze_deliverables(self, observations: List[Dict]) -> Dict[str, Any]:
        """
        分析交付物

        Args:
            observations: 观察结果列表

        Returns:
            Dict: 分析结果
        """
        analysis = {
            "total_deliverables": 0,
            "test_cases": [],
            "generated_code": [],
            "requirements": [],
            "errors": [],
            "quality_indicators": {},
        }

        for obs in observations:
            result = obs.get("result", {})
            if not isinstance(result, dict):
                continue

            result_type = result.get("type", "")

            # 分析测试用例
            if result_type == "test_case_generation":
                analysis["test_cases"].append(
                    {
                        "content": result.get("test_cases", ""),
                        "step_title": obs.get("step_title", ""),
                        "metadata": result,
                    }
                )
                analysis["total_deliverables"] += 1

            # 分析生成的代码
            elif result_type in [
                "test_script_generation",
                "api_test_generation",
                "generic_test_generation",
            ]:
                analysis["generated_code"].append(
                    {
                        "code": result.get("generated_code", ""),
                        "framework": result.get("framework", ""),
                        "is_valid": result.get("is_valid", False),
                        "step_title": obs.get("step_title", ""),
                        "metadata": result,
                    }
                )
                analysis["total_deliverables"] += 1

            # 分析需求提取
            elif result_type == "requirement_analysis":
                analysis["requirements"].append(
                    {
                        "content": result.get("analysis_result", ""),
                        "step_title": obs.get("step_title", ""),
                        "metadata": result,
                    }
                )
                analysis["total_deliverables"] += 1

            # 收集错误信息
            if obs.get("error") or result.get("error"):
                analysis["errors"].append(
                    {
                        "step": obs.get("step_title", "未知步骤"),
                        "error": result.get("error", "未知错误"),
                        "type": result_type,
                    }
                )

        # 计算质量指标
        analysis["quality_indicators"] = {
            "error_rate": len(analysis["errors"]) / max(len(observations), 1),
            "code_validity_rate": self._calculate_code_validity_rate(
                analysis["generated_code"]
            ),
            "deliverable_completeness": analysis["total_deliverables"]
            / max(len(observations), 1),
        }

        return analysis

    def _calculate_code_validity_rate(self, generated_code: List[Dict]) -> float:
        """计算代码有效性比率"""
        if not generated_code:
            return 0.0

        valid_count = sum(1 for code in generated_code if code.get("is_valid", False))
        return valid_count / len(generated_code)

    async def _evaluate_test_cases(
        self, analysis: Dict[str, Any], locale: str
    ) -> Dict[str, Any]:
        """
        评估测试用例质量

        Args:
            analysis: 分析结果
            locale: 语言设置

        Returns:
            Dict: 测试用例质量评分
        """
        if not analysis["test_cases"]:
            return {"error": "没有找到测试用例进行评估"}

        criteria = self.evaluation_criteria["test_case_quality"]
        scores = {}

        for criterion_name, criterion_config in criteria.items():
            if self.llm_service:
                score = await self._evaluate_with_llm(
                    analysis["test_cases"], criterion_config, locale, "test_case"
                )
            else:
                score = self._evaluate_with_heuristics(
                    analysis["test_cases"], criterion_config, "test_case"
                )

            scores[criterion_name] = {
                "score": score,
                "weight": criterion_config["weight"],
                "description": criterion_config["description"],
            }

        return scores

    async def _evaluate_test_scripts(
        self, analysis: Dict[str, Any], locale: str
    ) -> Dict[str, Any]:
        """
        评估测试脚本质量

        Args:
            analysis: 分析结果
            locale: 语言设置

        Returns:
            Dict: 测试脚本质量评分
        """
        if not analysis["generated_code"]:
            return {"error": "没有找到测试脚本进行评估"}

        criteria = self.evaluation_criteria["code_quality"]
        scores = {}

        for criterion_name, criterion_config in criteria.items():
            if self.llm_service:
                score = await self._evaluate_with_llm(
                    analysis["generated_code"], criterion_config, locale, "code"
                )
            else:
                score = self._evaluate_with_heuristics(
                    analysis["generated_code"], criterion_config, "code"
                )

            scores[criterion_name] = {
                "score": score,
                "weight": criterion_config["weight"],
                "description": criterion_config["description"],
            }

        return scores

    async def _evaluate_requirement_extraction(
        self, analysis: Dict[str, Any], locale: str
    ) -> Dict[str, Any]:
        """
        评估需求提取质量

        Args:
            analysis: 分析结果
            locale: 语言设置

        Returns:
            Dict: 需求提取质量评分
        """
        if not analysis["requirements"]:
            return {"error": "没有找到需求提取结果进行评估"}

        criteria = self.evaluation_criteria["requirement_extraction"]
        scores = {}

        for criterion_name, criterion_config in criteria.items():
            if self.llm_service:
                score = await self._evaluate_with_llm(
                    analysis["requirements"], criterion_config, locale, "requirement"
                )
            else:
                score = self._evaluate_with_heuristics(
                    analysis["requirements"], criterion_config, "requirement"
                )

            scores[criterion_name] = {
                "score": score,
                "weight": criterion_config["weight"],
                "description": criterion_config["description"],
            }

        return scores

    async def _evaluate_generic_quality(
        self, analysis: Dict[str, Any], locale: str
    ) -> Dict[str, Any]:
        """
        评估通用质量

        Args:
            analysis: 分析结果
            locale: 语言设置

        Returns:
            Dict: 通用质量评分
        """
        # 基于质量指标的通用评估
        quality_indicators = analysis["quality_indicators"]

        scores = {
            "completeness": {
                "score": quality_indicators["deliverable_completeness"],
                "weight": 0.4,
                "description": "交付物完整性",
            },
            "reliability": {
                "score": 1.0 - quality_indicators["error_rate"],
                "weight": 0.3,
                "description": "执行可靠性",
            },
            "quality": {
                "score": quality_indicators["code_validity_rate"],
                "weight": 0.3,
                "description": "输出质量",
            },
        }

        return scores

    async def _evaluate_with_llm(
        self, items: List[Dict], criterion_config: Dict, locale: str, item_type: str
    ) -> float:
        """
        使用LLM进行评估

        Args:
            items: 待评估项目列表
            criterion_config: 评估标准配置
            locale: 语言设置
            item_type: 项目类型

        Returns:
            float: 评估分数 (0.0-1.0)
        """
        try:
            # 构建评估提示词
            if locale == "zh-CN":
                prompt = f"""
                请根据以下标准评估{item_type}的质量：
                
                评估标准: {criterion_config['description']}
                具体要求:
                {chr(10).join(f"- {criterion}" for criterion in criterion_config['criteria'])}
                
                待评估内容:
                {self._format_items_for_evaluation(items, item_type)}
                
                请给出0.0到1.0之间的评分，其中：
                - 1.0: 完全满足所有标准，质量优秀
                - 0.8: 满足大部分标准，质量良好
                - 0.6: 满足基本标准，质量可接受
                - 0.4: 部分满足标准，质量较差
                - 0.2: 很少满足标准，质量很差
                - 0.0: 完全不满足标准
                
                请只返回数字评分，不要其他解释。
                """
            else:
                prompt = f"""
                Please evaluate the quality of {item_type} based on the following criteria:
                
                Evaluation Criteria: {criterion_config['description']}
                Specific Requirements:
                {chr(10).join(f"- {criterion}" for criterion in criterion_config['criteria'])}
                
                Content to Evaluate:
                {self._format_items_for_evaluation(items, item_type)}
                
                Please provide a score between 0.0 and 1.0, where:
                - 1.0: Fully meets all criteria, excellent quality
                - 0.8: Meets most criteria, good quality
                - 0.6: Meets basic criteria, acceptable quality
                - 0.4: Partially meets criteria, poor quality
                - 0.2: Rarely meets criteria, very poor quality
                - 0.0: Does not meet criteria at all
                
                Please return only the numerical score without other explanations.
                """

            # 调用LLM获取评分
            response = await self.llm_service.generate_response(
                prompt, model_type="reasoning", temperature=0.1
            )

            # 解析评分
            score = self._parse_score_from_response(response)
            return max(0.0, min(1.0, score))  # 确保分数在有效范围内

        except Exception as e:
            logger.error(f"LLM评估失败: {e}")
            # 回退到启发式评估
            return self._evaluate_with_heuristics(items, criterion_config, item_type)

    def _evaluate_with_heuristics(
        self, items: List[Dict], criterion_config: Dict, item_type: str
    ) -> float:
        """
        使用启发式方法进行评估

        Args:
            items: 待评估项目列表
            criterion_config: 评估标准配置
            item_type: 项目类型

        Returns:
            float: 评估分数 (0.0-1.0)
        """
        if not items:
            return 0.0

        total_score = 0.0

        for item in items:
            if item_type == "test_case":
                score = self._evaluate_test_case_heuristic(item, criterion_config)
            elif item_type == "code":
                score = self._evaluate_code_heuristic(item, criterion_config)
            elif item_type == "requirement":
                score = self._evaluate_requirement_heuristic(item, criterion_config)
            else:
                score = 0.5  # 默认中等分数

            total_score += score

        return total_score / len(items)

    def _evaluate_test_case_heuristic(
        self, test_case: Dict, criterion_config: Dict
    ) -> float:
        """启发式评估测试用例"""
        content = test_case.get("content", "")
        if not content:
            return 0.0

        score = 0.0

        # 基于内容长度和结构的简单评估
        if len(content) > 50:  # 有一定的内容长度
            score += 0.3

        # 检查是否包含关键词
        keywords = [
            "测试",
            "验证",
            "检查",
            "断言",
            "预期",
            "结果",
            "test",
            "verify",
            "check",
            "assert",
            "expect",
        ]
        if any(keyword in content.lower() for keyword in keywords):
            score += 0.3

        # 检查是否有结构化内容
        if any(
            marker in content for marker in ["1.", "2.", "3.", "-", "*", "步骤", "step"]
        ):
            score += 0.2

        # 检查是否有条件判断
        if any(
            condition in content for condition in ["如果", "当", "if", "when", "given"]
        ):
            score += 0.2

        return min(1.0, score)

    def _evaluate_code_heuristic(
        self, code_item: Dict, criterion_config: Dict
    ) -> float:
        """启发式评估代码"""
        code = code_item.get("code", "")
        is_valid = code_item.get("is_valid", False)

        if not code:
            return 0.0

        score = 0.0

        # 语法有效性
        if is_valid:
            score += 0.4

        # 代码长度和复杂度
        if len(code) > 100:
            score += 0.2

        # 检查导入语句
        if any(imp in code for imp in ["import", "from"]):
            score += 0.1

        # 检查类和函数定义
        if any(definition in code for definition in ["class ", "def "]):
            score += 0.2

        # 检查注释
        if any(comment in code for comment in ["#", '"""', "'''"]):
            score += 0.1

        return min(1.0, score)

    def _evaluate_requirement_heuristic(
        self, requirement: Dict, criterion_config: Dict
    ) -> float:
        """启发式评估需求"""
        content = requirement.get("content", "")
        if not content:
            return 0.0

        score = 0.0

        # 基于内容长度
        if len(content) > 100:
            score += 0.3

        # 检查需求关键词
        keywords = [
            "需求",
            "功能",
            "应该",
            "必须",
            "可以",
            "requirement",
            "should",
            "must",
            "shall",
        ]
        if any(keyword in content.lower() for keyword in keywords):
            score += 0.3

        # 检查结构化内容
        if any(marker in content for marker in ["1.", "2.", "3.", "-", "*"]):
            score += 0.2

        # 检查具体性
        if any(
            specific in content
            for specific in [
                "用户",
                "系统",
                "界面",
                "数据",
                "user",
                "system",
                "interface",
                "data",
            ]
        ):
            score += 0.2

        return min(1.0, score)

    def _format_items_for_evaluation(self, items: List[Dict], item_type: str) -> str:
        """格式化评估项目"""
        formatted_items = []

        for i, item in enumerate(items, 1):
            if item_type == "test_case":
                content = item.get("content", "")
            elif item_type == "code":
                content = item.get("code", "")
            elif item_type == "requirement":
                content = item.get("content", "")
            else:
                content = str(item)

            # 限制内容长度以避免提示词过长
            if len(content) > 500:
                content = content[:500] + "..."

            formatted_items.append(f"项目 {i}:\n{content}\n")

        return "\n".join(formatted_items)

    def _parse_score_from_response(self, response: str) -> float:
        """从LLM响应中解析评分"""
        try:
            # 尝试直接解析数字
            import re

            numbers = re.findall(r"\d+\.?\d*", response)
            if numbers:
                score = float(numbers[0])
                # 如果分数大于1，假设是百分制，转换为0-1范围
                if score > 1:
                    score = score / 100
                return score
            return 0.5  # 默认中等分数
        except:
            return 0.5

    async def _generate_improvement_suggestions(
        self, quality_scores: Dict[str, Any], analysis: Dict[str, Any], locale: str
    ) -> List[str]:
        """
        生成改进建议

        Args:
            quality_scores: 质量评分
            analysis: 分析结果
            locale: 语言设置

        Returns:
            List[str]: 改进建议列表
        """
        suggestions = []

        # 基于评分生成建议
        for criterion_name, score_info in quality_scores.items():
            if isinstance(score_info, dict) and "score" in score_info:
                score = score_info["score"]
                if score < 0.7:  # 分数较低时给出建议
                    suggestion = self._get_improvement_suggestion(
                        criterion_name, score, score_info.get("description", ""), locale
                    )
                    if suggestion:
                        suggestions.append(suggestion)

        # 基于错误信息生成建议
        if analysis["errors"]:
            if locale == "zh-CN":
                suggestions.append(
                    f"发现 {len(analysis['errors'])} 个执行错误，建议检查配置和输入数据的正确性。"
                )
            else:
                suggestions.append(
                    f"Found {len(analysis['errors'])} execution errors, recommend checking configuration and input data correctness."
                )

        # 基于质量指标生成建议
        quality_indicators = analysis["quality_indicators"]
        if quality_indicators["code_validity_rate"] < 0.8:
            if locale == "zh-CN":
                suggestions.append(
                    "生成的代码语法有效性较低，建议优化代码生成逻辑和模板。"
                )
            else:
                suggestions.append(
                    "Generated code syntax validity is low, recommend optimizing code generation logic and templates."
                )

        # 如果没有具体建议，给出通用建议
        if not suggestions:
            if locale == "zh-CN":
                suggestions.append("整体质量良好，建议继续保持当前的工作标准。")
            else:
                suggestions.append(
                    "Overall quality is good, recommend maintaining current work standards."
                )

        return suggestions

    def _get_improvement_suggestion(
        self, criterion_name: str, score: float, description: str, locale: str
    ) -> str:
        """获取特定标准的改进建议"""
        if locale == "zh-CN":
            suggestions_map = {
                "completeness": "建议增加更多测试场景和边界条件的覆盖。",
                "clarity": "建议改进描述的清晰度和可理解性。",
                "accuracy": "建议检查逻辑准确性和有效性。",
                "maintainability": "建议改进代码结构和可维护性。",
                "syntax": "建议检查语法错误和代码规范。",
                "structure": "建议优化代码组织结构。",
                "readability": "建议改进代码可读性和注释。",
                "testability": "建议提高代码的可测试性。",
            }
        else:
            suggestions_map = {
                "completeness": "Recommend adding more test scenarios and boundary condition coverage.",
                "clarity": "Recommend improving description clarity and understandability.",
                "accuracy": "Recommend checking logical accuracy and effectiveness.",
                "maintainability": "Recommend improving code structure and maintainability.",
                "syntax": "Recommend checking syntax errors and code standards.",
                "structure": "Recommend optimizing code organization structure.",
                "readability": "Recommend improving code readability and comments.",
                "testability": "Recommend improving code testability.",
            }

        return suggestions_map.get(
            criterion_name,
            (
                f"{description}: 建议进一步改进。"
                if locale == "zh-CN"
                else f"{description}: Recommend further improvement."
            ),
        )

    def _calculate_overall_score(self, quality_scores: Dict[str, Any]) -> float:
        """计算总体评分"""
        if not quality_scores or "error" in quality_scores:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for score_info in quality_scores.values():
            if (
                isinstance(score_info, dict)
                and "score" in score_info
                and "weight" in score_info
            ):
                weighted_sum += score_info["score"] * score_info["weight"]
                total_weight += score_info["weight"]

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _get_quality_level(self, score: float) -> str:
        """获取质量等级"""
        if score >= self.quality_thresholds["excellent"]:
            return "excellent"
        elif score >= self.quality_thresholds["good"]:
            return "good"
        elif score >= self.quality_thresholds["acceptable"]:
            return "acceptable"
        elif score >= self.quality_thresholds["poor"]:
            return "poor"
        else:
            return "unacceptable"

    def _generate_error_review(
        self, error_message: str, task_topic: str, task_type: str, locale: str
    ) -> Dict[str, Any]:
        """
        生成错误评审

        Args:
            error_message: 错误信息
            task_topic: 任务主题
            task_type: 任务类型
            locale: 语言设置

        Returns:
            Dict: 错误评审结果
        """
        return {
            "type": "error_review",
            "task_topic": task_topic,
            "task_type": task_type,
            "error": True,
            "error_message": error_message,
            "overall_score": 0.0,
            "quality_level": "unacceptable",
            "improvement_suggestions": [
                (
                    "评审过程中发生错误，请检查系统配置和输入数据。"
                    if locale == "zh-CN"
                    else "Error occurred during review process, please check system configuration and input data."
                )
            ],
            "review_time": datetime.now().isoformat(),
            "locale": locale,
        }
