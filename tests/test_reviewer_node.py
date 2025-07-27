#!/usr/bin/env python3
"""
评审员节点单元测试
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.exceptions import TestAgentException
from src.graph.reviewer_node import ReviewerNode
from src.models.execution import ExecutionStep, StepType
from src.models.state import TestAgentState
from src.models.types import TaskType


class TestReviewerNode:
    """评审员节点测试类"""

    def setup_method(self):
        """测试前置设置"""
        self.reviewer_node = ReviewerNode()
        self.mock_llm_service = Mock()
        self.reviewer_node.llm_service = self.mock_llm_service

    def test_init(self):
        """测试初始化"""
        node = ReviewerNode()
        assert node is not None
        assert hasattr(node, "evaluation_criteria")
        assert hasattr(node, "quality_thresholds")
        assert "test_case_quality" in node.evaluation_criteria
        assert "code_quality" in node.evaluation_criteria
        assert "requirement_extraction" in node.evaluation_criteria

    def test_load_evaluation_criteria(self):
        """测试加载评估标准"""
        criteria = self.reviewer_node._load_evaluation_criteria()

        assert isinstance(criteria, dict)
        assert "test_case_quality" in criteria
        assert "code_quality" in criteria
        assert "requirement_extraction" in criteria

        # 检查测试用例质量标准
        test_case_criteria = criteria["test_case_quality"]
        assert "completeness" in test_case_criteria
        assert "clarity" in test_case_criteria
        assert "accuracy" in test_case_criteria
        assert "maintainability" in test_case_criteria

        # 检查权重和描述
        for criterion in test_case_criteria.values():
            assert "weight" in criterion
            assert "description" in criterion
            assert "criteria" in criterion
            assert isinstance(criterion["criteria"], list)

    def test_load_quality_thresholds(self):
        """测试加载质量阈值"""
        thresholds = self.reviewer_node._load_quality_thresholds()

        assert isinstance(thresholds, dict)
        assert "excellent" in thresholds
        assert "good" in thresholds
        assert "acceptable" in thresholds
        assert "poor" in thresholds
        assert "unacceptable" in thresholds

        # 检查阈值顺序
        assert thresholds["excellent"] > thresholds["good"]
        assert thresholds["good"] > thresholds["acceptable"]
        assert thresholds["acceptable"] > thresholds["poor"]
        assert thresholds["poor"] > thresholds["unacceptable"]

    def test_analyze_deliverables(self):
        """测试分析交付物"""
        observations = [
            {
                "step_title": "测试用例生成",
                "step_type": "research",
                "result": {
                    "type": "test_case_generation",
                    "test_cases": "测试用例内容",
                },
            },
            {
                "step_title": "代码生成",
                "step_type": "coding",
                "result": {
                    "type": "test_script_generation",
                    "generated_code": "import pytest\ndef test_example(): pass",
                    "framework": "pytest",
                    "is_valid": True,
                },
            },
            {
                "step_title": "需求分析",
                "step_type": "research",
                "result": {
                    "type": "requirement_analysis",
                    "analysis_result": "需求分析结果",
                },
            },
            {
                "step_title": "错误步骤",
                "step_type": "coding",
                "error": True,
                "result": {"type": "coding_error", "error": "语法错误"},
            },
        ]

        analysis = self.reviewer_node._analyze_deliverables(observations)

        assert analysis["total_deliverables"] == 3
        assert len(analysis["test_cases"]) == 1
        assert len(analysis["generated_code"]) == 1
        assert len(analysis["requirements"]) == 1
        assert len(analysis["errors"]) == 1

        # 检查质量指标
        assert "quality_indicators" in analysis
        assert "error_rate" in analysis["quality_indicators"]
        assert "code_validity_rate" in analysis["quality_indicators"]
        assert "deliverable_completeness" in analysis["quality_indicators"]

    def test_calculate_code_validity_rate(self):
        """测试计算代码有效性比率"""
        # 空列表
        assert self.reviewer_node._calculate_code_validity_rate([]) == 0.0

        # 全部有效
        valid_code = [{"is_valid": True}, {"is_valid": True}]
        assert self.reviewer_node._calculate_code_validity_rate(valid_code) == 1.0

        # 部分有效
        mixed_code = [{"is_valid": True}, {"is_valid": False}, {"is_valid": True}]
        assert (
            abs(self.reviewer_node._calculate_code_validity_rate(mixed_code) - 0.667)
            < 0.01
        )

    def test_evaluate_test_case_heuristic(self):
        """测试启发式测试用例评估"""
        # 空内容
        empty_case = {"content": ""}
        score = self.reviewer_node._evaluate_test_case_heuristic(empty_case, {})
        assert score == 0.0

        # 良好的测试用例
        good_case = {
            "content": """
            测试用例1: 验证用户登录功能
            步骤:
            1. 输入正确的用户名和密码
            2. 点击登录按钮
            预期结果: 成功登录并跳转到主页
            """
        }
        score = self.reviewer_node._evaluate_test_case_heuristic(good_case, {})
        assert score > 0.5

    def test_evaluate_code_heuristic(self):
        """测试启发式代码评估"""
        # 空代码
        empty_code = {"code": "", "is_valid": False}
        score = self.reviewer_node._evaluate_code_heuristic(empty_code, {})
        assert score == 0.0

        # 良好的代码
        good_code = {
            "code": """
            import pytest
            
            class TestExample:
                '''测试类示例'''
                
                def test_method(self):
                    # 测试方法
                    assert True
            """,
            "is_valid": True,
        }
        score = self.reviewer_node._evaluate_code_heuristic(good_code, {})
        assert score > 0.7

    def test_evaluate_requirement_heuristic(self):
        """测试启发式需求评估"""
        # 空需求
        empty_req = {"content": ""}
        score = self.reviewer_node._evaluate_requirement_heuristic(empty_req, {})
        assert score == 0.0

        # 良好的需求
        good_req = {
            "content": """
            功能需求:
            1. 用户应该能够登录系统
            2. 系统必须验证用户凭据
            3. 界面应该显示登录状态
            4. 数据应该安全存储
            """
        }
        score = self.reviewer_node._evaluate_requirement_heuristic(good_req, {})
        assert score > 0.8

    def test_parse_score_from_response(self):
        """测试从响应中解析评分"""
        # 直接数字
        assert self.reviewer_node._parse_score_from_response("0.85") == 0.85

        # 百分制
        assert self.reviewer_node._parse_score_from_response("85") == 0.85

        # 包含文字的响应
        assert self.reviewer_node._parse_score_from_response("评分是 0.75 分") == 0.75

        # 无效响应
        assert self.reviewer_node._parse_score_from_response("无法解析") == 0.5

    def test_calculate_overall_score(self):
        """测试计算总体评分"""
        # 空评分
        assert self.reviewer_node._calculate_overall_score({}) == 0.0

        # 错误评分
        assert self.reviewer_node._calculate_overall_score({"error": "评估失败"}) == 0.0

        # 正常评分
        quality_scores = {
            "completeness": {"score": 0.8, "weight": 0.3},
            "clarity": {"score": 0.7, "weight": 0.25},
            "accuracy": {"score": 0.9, "weight": 0.25},
            "maintainability": {"score": 0.6, "weight": 0.2},
        }

        expected_score = (0.8 * 0.3 + 0.7 * 0.25 + 0.9 * 0.25 + 0.6 * 0.2) / 1.0
        actual_score = self.reviewer_node._calculate_overall_score(quality_scores)
        assert abs(actual_score - expected_score) < 0.01

    def test_get_quality_level(self):
        """测试获取质量等级"""
        assert self.reviewer_node._get_quality_level(0.95) == "excellent"
        assert self.reviewer_node._get_quality_level(0.85) == "good"
        assert self.reviewer_node._get_quality_level(0.75) == "acceptable"
        assert self.reviewer_node._get_quality_level(0.65) == "poor"
        assert self.reviewer_node._get_quality_level(0.45) == "unacceptable"

    def test_format_items_for_evaluation(self):
        """测试格式化评估项目"""
        items = [{"content": "测试内容1"}, {"content": "测试内容2"}]

        formatted = self.reviewer_node._format_items_for_evaluation(items, "test_case")

        assert "项目 1:" in formatted
        assert "项目 2:" in formatted
        assert "测试内容1" in formatted
        assert "测试内容2" in formatted

    def test_get_improvement_suggestion(self):
        """测试获取改进建议"""
        # 中文建议
        suggestion_zh = self.reviewer_node._get_improvement_suggestion(
            "completeness", 0.6, "完整性", "zh-CN"
        )
        assert "建议" in suggestion_zh
        assert "测试场景" in suggestion_zh

        # 英文建议
        suggestion_en = self.reviewer_node._get_improvement_suggestion(
            "completeness", 0.6, "Completeness", "en-US"
        )
        assert "Recommend" in suggestion_en
        assert "test scenarios" in suggestion_en

    @pytest.mark.asyncio
    async def test_evaluate_test_cases(self):
        """测试评估测试用例"""
        analysis = {
            "test_cases": [{"content": "测试用例内容", "step_title": "测试步骤"}]
        }

        # 不使用LLM的情况
        self.reviewer_node.llm_service = None
        scores = await self.reviewer_node._evaluate_test_cases(analysis, "zh-CN")

        assert isinstance(scores, dict)
        assert "completeness" in scores
        assert "clarity" in scores
        assert "accuracy" in scores
        assert "maintainability" in scores

        for score_info in scores.values():
            assert "score" in score_info
            assert "weight" in score_info
            assert "description" in score_info

    @pytest.mark.asyncio
    async def test_evaluate_test_scripts(self):
        """测试评估测试脚本"""
        analysis = {
            "generated_code": [
                {
                    "code": "import pytest\ndef test_example(): pass",
                    "framework": "pytest",
                    "is_valid": True,
                }
            ]
        }

        # 不使用LLM的情况
        self.reviewer_node.llm_service = None
        scores = await self.reviewer_node._evaluate_test_scripts(analysis, "zh-CN")

        assert isinstance(scores, dict)
        assert "syntax" in scores
        assert "structure" in scores
        assert "readability" in scores
        assert "testability" in scores

    @pytest.mark.asyncio
    async def test_evaluate_requirement_extraction(self):
        """测试评估需求提取"""
        analysis = {
            "requirements": [{"content": "需求分析结果", "step_title": "需求分析"}]
        }

        # 不使用LLM的情况
        self.reviewer_node.llm_service = None
        scores = await self.reviewer_node._evaluate_requirement_extraction(
            analysis, "zh-CN"
        )

        assert isinstance(scores, dict)
        assert "completeness" in scores
        assert "accuracy" in scores
        assert "clarity" in scores

    @pytest.mark.asyncio
    async def test_evaluate_generic_quality(self):
        """测试评估通用质量"""
        analysis = {
            "quality_indicators": {
                "deliverable_completeness": 0.8,
                "error_rate": 0.1,
                "code_validity_rate": 0.9,
            }
        }

        scores = await self.reviewer_node._evaluate_generic_quality(analysis, "zh-CN")

        assert isinstance(scores, dict)
        assert "completeness" in scores
        assert "reliability" in scores
        assert "quality" in scores

        assert scores["completeness"]["score"] == 0.8
        assert scores["reliability"]["score"] == 0.9  # 1.0 - 0.1
        assert scores["quality"]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_generate_improvement_suggestions(self):
        """测试生成改进建议"""
        quality_scores = {
            "completeness": {"score": 0.6, "description": "完整性"},
            "clarity": {"score": 0.8, "description": "清晰度"},
        }

        analysis = {
            "errors": [{"step": "步骤1", "error": "错误1"}],
            "quality_indicators": {"code_validity_rate": 0.5},
        }

        suggestions = await self.reviewer_node._generate_improvement_suggestions(
            quality_scores, analysis, "zh-CN"
        )

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

        # 应该包含针对低分项的建议
        completeness_suggestion = any(
            "完整性" in s or "测试场景" in s for s in suggestions
        )
        assert completeness_suggestion

        # 应该包含针对错误的建议
        error_suggestion = any("错误" in s for s in suggestions)
        assert error_suggestion

    def test_generate_error_review(self):
        """测试生成错误评审"""
        error_review = self.reviewer_node._generate_error_review(
            "测试错误", "测试任务", "test_type", "zh-CN"
        )

        assert error_review["type"] == "error_review"
        assert error_review["task_topic"] == "测试任务"
        assert error_review["task_type"] == "test_type"
        assert error_review["error"] is True
        assert error_review["overall_score"] == 0.0
        assert error_review["quality_level"] == "unacceptable"
        assert len(error_review["improvement_suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_process_success(self):
        """测试成功处理评审"""
        observations = [
            {
                "step_title": "测试用例生成",
                "step_type": "research",
                "result": {
                    "type": "test_case_generation",
                    "test_cases": "测试用例内容",
                },
            }
        ]

        state = {
            "task_topic": "测试任务",
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "locale": "zh-CN",
            "observations": observations,
            "report": {"type": "final_report", "content": "报告内容"},
        }

        # 不使用LLM
        self.reviewer_node.llm_service = None

        result = await self.reviewer_node.process(state)

        assert "review" in result
        assert result["task_completed"] is True
        assert result["final_evaluation"] is True
        assert result["review"]["type"] == "quality_review"
        assert result["review"]["task_topic"] == "测试任务"
        assert "overall_score" in result["review"]
        assert "quality_level" in result["review"]
        assert "improvement_suggestions" in result["review"]

    @pytest.mark.asyncio
    async def test_process_with_error(self):
        """测试处理错误情况"""
        state = {
            "task_topic": None,  # 故意设置为None引发错误
            "task_type": TaskType.TEST_CASE_GENERATION.value,
            "locale": "zh-CN",
            "observations": [],
        }

        result = await self.reviewer_node.process(state)

        assert "review" in result
        assert result["task_completed"] is True

        # 检查review类型
        expected_types = ["error_review", "quality_review"]
        assert result["review"]["type"] in expected_types

        # 如果是quality_review，应该有低分或错误信息
        if result["review"]["type"] == "quality_review":
            # 应该有低分（因为没有交付物）
            assert result["review"]["overall_score"] == 0.0
            assert result["review"]["quality_level"] == "unacceptable"
            # 详细评分中应该包含错误信息
            assert "error" in result["review"]["detailed_scores"]

    @pytest.mark.asyncio
    async def test_evaluate_with_llm(self):
        """测试使用LLM进行评估"""
        items = [{"content": "测试内容"}]
        criterion_config = {"description": "测试标准", "criteria": ["标准1", "标准2"]}

        # Mock LLM响应
        self.mock_llm_service.generate_response = AsyncMock(return_value="0.75")

        score = await self.reviewer_node._evaluate_with_llm(
            items, criterion_config, "zh-CN", "test_case"
        )

        assert score == 0.75
        self.mock_llm_service.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_conduct_quality_review(self):
        """测试执行质量评审"""
        observations = [
            {
                "step_title": "测试用例生成",
                "result": {
                    "type": "test_case_generation",
                    "test_cases": "测试用例内容",
                },
            }
        ]

        report = {"type": "final_report", "content": "报告内容"}

        # 不使用LLM
        self.reviewer_node.llm_service = None

        review_result = await self.reviewer_node._conduct_quality_review(
            "测试任务",
            TaskType.TEST_CASE_GENERATION.value,
            observations,
            report,
            "zh-CN",
        )

        assert review_result["type"] == "quality_review"
        assert review_result["task_topic"] == "测试任务"
        assert "overall_score" in review_result
        assert "quality_level" in review_result
        assert "detailed_scores" in review_result
        assert "improvement_suggestions" in review_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
