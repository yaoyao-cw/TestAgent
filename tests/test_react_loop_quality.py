#!/usr/bin/env python3
"""
ReAct循环质量测试

专门测试ReAct循环的推理质量、动作选择和观察分析的深度质量验证。
"""

import json
import os
import sys
import tempfile
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import TesterAgent, CoderAgent
from src.core.base_agent import AgentInput
from src.models.workspace import GlobalState


class ReActQualityAnalyzer:
    """ReAct质量分析器"""

    def __init__(self):
        self.quality_thresholds = {
            "reasoning": {
                "min_clarity": 0.6,
                "min_logic": 0.6,
                "min_relevance": 0.7,
                "min_completeness": 0.5,
            },
            "action": {
                "min_appropriateness": 0.7,
                "min_efficiency": 0.6,
                "min_success_rate": 0.8,
            },
            "observation": {
                "min_informativeness": 0.6,
                "min_accuracy": 0.7,
                "min_actionability": 0.5,
            },
        }

    def analyze_reasoning_depth(self, reasoning: str) -> Dict[str, Any]:
        """分析推理深度"""
        analysis = {
            "word_count": len(reasoning.split()),
            "sentence_count": len([s for s in reasoning.split("。") if s.strip()]),
            "has_causal_reasoning": False,
            "has_conditional_reasoning": False,
            "has_sequential_reasoning": False,
            "reasoning_patterns": [],
            "depth_score": 0.0,
        }

        # 检测因果推理
        causal_indicators = ["因为", "所以", "导致", "由于", "因此"]
        if any(indicator in reasoning for indicator in causal_indicators):
            analysis["has_causal_reasoning"] = True
            analysis["reasoning_patterns"].append("causal")

        # 检测条件推理
        conditional_indicators = ["如果", "那么", "假设", "当", "则"]
        if any(indicator in reasoning for indicator in conditional_indicators):
            analysis["has_conditional_reasoning"] = True
            analysis["reasoning_patterns"].append("conditional")

        # 检测序列推理
        sequential_indicators = ["首先", "然后", "接下来", "最后", "第一", "第二"]
        if any(indicator in reasoning for indicator in sequential_indicators):
            analysis["has_sequential_reasoning"] = True
            analysis["reasoning_patterns"].append("sequential")

        # 计算深度分数
        depth_score = 0.0
        if analysis["word_count"] > 50:
            depth_score += 0.2
        if analysis["sentence_count"] >= 3:
            depth_score += 0.2
        if analysis["has_causal_reasoning"]:
            depth_score += 0.3
        if analysis["has_conditional_reasoning"]:
            depth_score += 0.2
        if analysis["has_sequential_reasoning"]:
            depth_score += 0.1

        analysis["depth_score"] = min(1.0, depth_score)

        return analysis

    def analyze_action_effectiveness(
        self, action_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析动作有效性"""
        analysis = {
            "action_type": action_result.get("action_type", "unknown"),
            "success": action_result.get("success", False),
            "output_length": len(str(action_result.get("output", ""))),
            "has_error_handling": "error" in action_result,
            "produces_output": bool(action_result.get("output")),
            "effectiveness_score": 0.0,
        }

        # 计算有效性分数
        effectiveness_score = 0.0
        if analysis["success"]:
            effectiveness_score += 0.4
        if analysis["produces_output"]:
            effectiveness_score += 0.3
        if analysis["output_length"] > 20:
            effectiveness_score += 0.2
        if analysis["has_error_handling"]:
            effectiveness_score += 0.1

        analysis["effectiveness_score"] = min(1.0, effectiveness_score)

        return analysis

    def analyze_observation_insight(self, observation: str) -> Dict[str, Any]:
        """分析观察洞察力"""
        analysis = {
            "length": len(observation),
            "has_status_info": False,
            "has_result_analysis": False,
            "has_next_step_guidance": False,
            "insight_indicators": [],
            "insight_score": 0.0,
        }

        # 检测状态信息
        status_indicators = ["成功", "失败", "完成", "进行中", "状态"]
        if any(indicator in observation for indicator in status_indicators):
            analysis["has_status_info"] = True
            analysis["insight_indicators"].append("status")

        # 检测结果分析
        result_indicators = ["结果", "输出", "发现", "显示", "表明"]
        if any(indicator in observation for indicator in result_indicators):
            analysis["has_result_analysis"] = True
            analysis["insight_indicators"].append("result_analysis")

        # 检测下一步指导
        guidance_indicators = ["建议", "需要", "应该", "继续", "下一步"]
        if any(indicator in observation for indicator in guidance_indicators):
            analysis["has_next_step_guidance"] = True
            analysis["insight_indicators"].append("guidance")

        # 计算洞察分数
        insight_score = 0.0
        if analysis["length"] > 30:
            insight_score += 0.2
        if analysis["has_status_info"]:
            insight_score += 0.3
        if analysis["has_result_analysis"]:
            insight_score += 0.3
        if analysis["has_next_step_guidance"]:
            insight_score += 0.2

        analysis["insight_score"] = min(1.0, insight_score)

        return analysis

    def evaluate_react_cycle_quality(
        self, react_step: Dict[str, Any]
    ) -> Dict[str, Any]:
        """评估单个ReAct循环的质量"""
        reasoning = react_step.get("reasoning", "")
        action = react_step.get("action", {})
        observation = react_step.get("observation", "")

        reasoning_analysis = self.analyze_reasoning_depth(reasoning)
        action_analysis = self.analyze_action_effectiveness(action)
        observation_analysis = self.analyze_observation_insight(observation)

        # 计算总体质量分数
        overall_quality = (
            reasoning_analysis["depth_score"] * 0.4
            + action_analysis["effectiveness_score"] * 0.4
            + observation_analysis["insight_score"] * 0.2
        )

        return {
            "reasoning_analysis": reasoning_analysis,
            "action_analysis": action_analysis,
            "observation_analysis": observation_analysis,
            "overall_quality": overall_quality,
            "meets_thresholds": self._check_quality_thresholds(
                reasoning_analysis, action_analysis, observation_analysis
            ),
        }

    def _check_quality_thresholds(
        self,
        reasoning_analysis: Dict,
        action_analysis: Dict,
        observation_analysis: Dict,
    ) -> Dict[str, bool]:
        """检查是否满足质量阈值"""
        return {
            "reasoning_depth": reasoning_analysis["depth_score"] >= 0.6,
            "action_effectiveness": action_analysis["effectiveness_score"] >= 0.6,
            "observation_insight": observation_analysis["insight_score"] >= 0.5,
        }


class TestReActLoopQuality:
    """ReAct循环质量测试类"""

    @pytest.fixture
    def global_state(self):
        """创建测试用的全局状态"""
        return GlobalState()

    @pytest.fixture
    def quality_analyzer(self):
        """创建质量分析器"""
        return ReActQualityAnalyzer()

    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        mock_service = Mock()
        mock_service.invoke_sync = Mock()
        return mock_service

    def test_high_quality_reasoning_analysis(self, quality_analyzer):
        """测试高质量推理分析"""
        high_quality_reasoning = """
        我需要深入分析当前的测试任务。首先，我应该仔细阅读需求文档，
        因为这是理解业务逻辑的基础。如果需求不清晰，那么生成的测试用例
        就可能偏离实际需要。然后，我会根据需求的复杂度选择合适的测试策略。
        接下来，我需要考虑各种测试场景，包括正常流程、异常处理和边界条件。
        最后，我会创建结构化的测试用例文档。基于以上分析，我选择首先
        读取需求文档的行动。
        """

        analysis = quality_analyzer.analyze_reasoning_depth(high_quality_reasoning)

        assert analysis["word_count"] > 50
        assert analysis["sentence_count"] >= 3
        assert analysis["has_causal_reasoning"] is True
        assert analysis["has_conditional_reasoning"] is True
        assert analysis["has_sequential_reasoning"] is True
        assert analysis["depth_score"] > 0.8

    def test_low_quality_reasoning_analysis(self, quality_analyzer):
        """测试低质量推理分析"""
        low_quality_reasoning = "需要执行测试"

        analysis = quality_analyzer.analyze_reasoning_depth(low_quality_reasoning)

        assert analysis["word_count"] < 10
        assert analysis["sentence_count"] <= 1
        assert analysis["has_causal_reasoning"] is False
        assert analysis["has_conditional_reasoning"] is False
        assert analysis["has_sequential_reasoning"] is False
        assert analysis["depth_score"] < 0.3

    def test_action_effectiveness_analysis(self, quality_analyzer):
        """测试动作有效性分析"""
        # 高效动作
        effective_action = {
            "action_type": "generate_test_cases",
            "success": True,
            "output": "成功生成5个测试用例，覆盖正常登录、密码错误、用户不存在等场景",
            "error": None,
        }

        analysis = quality_analyzer.analyze_action_effectiveness(effective_action)

        assert analysis["success"] is True
        assert analysis["produces_output"] is True
        assert analysis["output_length"] > 20
        assert analysis["effectiveness_score"] > 0.8

        # 低效动作
        ineffective_action = {
            "action_type": "unknown",
            "success": False,
            "output": "",
            "error": "执行失败",
        }

        analysis = quality_analyzer.analyze_action_effectiveness(ineffective_action)

        assert analysis["success"] is False
        assert analysis["produces_output"] is False
        assert analysis["effectiveness_score"] < 0.3

    def test_observation_insight_analysis(self, quality_analyzer):
        """测试观察洞察力分析"""
        # 高洞察力观察
        insightful_observation = """
        行动类型: generate_test_cases
        执行状态: 成功
        输出结果: 成功生成了5个测试用例，包含正常登录、密码错误、用户锁定等场景。
        测试覆盖度达到80%，建议继续添加边界条件测试用例以提高覆盖率。
        下一步应该创建思维导图来可视化测试策略。
        """

        analysis = quality_analyzer.analyze_observation_insight(insightful_observation)

        assert analysis["has_status_info"] is True
        assert analysis["has_result_analysis"] is True
        assert analysis["has_next_step_guidance"] is True
        assert analysis["insight_score"] > 0.7

        # 低洞察力观察
        simple_observation = "完成"

        analysis = quality_analyzer.analyze_observation_insight(simple_observation)

        assert analysis["has_status_info"] is False
        assert analysis["has_result_analysis"] is False
        assert analysis["has_next_step_guidance"] is False
        assert analysis["insight_score"] < 0.3

    def test_react_cycle_quality_evaluation(self, quality_analyzer):
        """测试ReAct循环质量评估"""
        # 高质量ReAct循环
        high_quality_cycle = {
            "reasoning": """
            我需要分析测试需求并生成相应的测试用例。首先，我应该理解
            业务逻辑，因为这是设计有效测试的基础。如果需求理解不准确，
            那么测试用例就会偏离目标。然后，我会设计覆盖各种场景的测试用例。
            基于分析，我选择生成测试用例的行动。
            """,
            "action": {
                "action_type": "generate_test_cases",
                "success": True,
                "output": "成功生成3个测试用例，覆盖正常和异常场景",
            },
            "observation": """
            行动类型: generate_test_cases
            执行状态: 成功
            输出结果: 生成了3个高质量测试用例，覆盖了主要业务场景。
            建议继续创建思维导图来完善测试策略。
            """,
        }

        evaluation = quality_analyzer.evaluate_react_cycle_quality(high_quality_cycle)

        assert evaluation["overall_quality"] > 0.7
        assert evaluation["meets_thresholds"]["reasoning_depth"] is True
        assert evaluation["meets_thresholds"]["action_effectiveness"] is True
        assert evaluation["meets_thresholds"]["observation_insight"] is True

    def test_tester_agent_react_quality(
        self, global_state, quality_analyzer, mock_llm_service
    ):
        """测试Tester智能体的ReAct质量"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟高质量LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(
                    content="""
                我需要深入分析当前的测试任务。首先，我应该理解需求文档的内容，
                因为这是生成有效测试用例的基础。如果需求不明确，那么测试用例
                就可能不准确。然后，我会根据需求设计各种测试场景。
                基于分析，我选择读取需求文档的行动。
                """
                ),
                Mock(
                    content="""
                ## 测试用例1: 正常登录
                前置条件: 用户已注册且账户正常
                测试步骤: 1. 输入正确用户名和密码 2. 点击登录按钮
                预期结果: 登录成功，跳转到主页面

                ## 测试用例2: 密码错误
                前置条件: 用户已注册
                测试步骤: 1. 输入正确用户名和错误密码 2. 点击登录按钮
                预期结果: 显示"密码错误"提示信息
                """
                ),
            ]

            tester = TesterAgent(global_state)
            input_data = AgentInput(data={"test_requirements": "用户登录功能测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 执行智能体
                result = tester.execute(input_data)

                # 分析ReAct质量
                react_history = result.data.get("react_history", [])
                assert len(react_history) > 0

                for step in react_history:
                    evaluation = quality_analyzer.evaluate_react_cycle_quality(step)

                    # 验证质量标准
                    assert (
                        evaluation["overall_quality"] > 0.5
                    ), f"ReAct循环质量不足: {evaluation['overall_quality']}"

                    # 详细质量检查
                    reasoning_analysis = evaluation["reasoning_analysis"]
                    assert reasoning_analysis["depth_score"] > 0.4, "推理深度不足"

                    action_analysis = evaluation["action_analysis"]
                    assert (
                        action_analysis["effectiveness_score"] > 0.4
                    ), "动作有效性不足"

    def test_coder_agent_react_quality(
        self, global_state, quality_analyzer, mock_llm_service
    ):
        """测试Coder智能体的ReAct质量"""
        with patch("src.agents.coder.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟高质量LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(
                    content="""
                我需要分析测试用例并生成相应的测试脚本。首先，我应该理解
                测试用例的结构和要求，因为这决定了代码的设计方向。
                如果测试用例分析不充分，那么生成的代码可能不符合预期。
                然后，我会选择合适的测试框架和编码模式。
                基于分析，我选择分析测试用例的行动。
                """
                ),
                Mock(
                    content="""
                ```python
                import pytest

                class TestLogin:
                    def test_normal_login(self):
                        # 测试正常登录场景
                        username = "test_user"
                        password = "correct_password"
                        result = login_function(username, password)
                        assert result.success == True
                        assert result.redirect_url == "/dashboard"

                    def test_wrong_password(self):
                        # 测试密码错误场景
                        username = "test_user"
                        password = "wrong_password"
                        result = login_function(username, password)
                        assert result.success == False
                        assert "密码错误" in result.error_message
                ```
                """
                ),
            ]

            coder = CoderAgent(global_state)
            input_data = AgentInput(
                data={
                    "test_cases": [
                        {
                            "scenario": "正常登录",
                            "steps": "输入正确用户名密码",
                            "expected": "登录成功",
                        }
                    ]
                }
            )

            # 模拟工作空间
            with patch("src.agents.coder.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_script.py"

                # 执行智能体
                result = coder.execute(input_data)

                # 分析ReAct质量
                react_history = result.data.get("react_history", [])
                assert len(react_history) > 0

                for step in react_history:
                    evaluation = quality_analyzer.evaluate_react_cycle_quality(step)

                    # 验证质量标准
                    assert (
                        evaluation["overall_quality"] > 0.5
                    ), f"ReAct循环质量不足: {evaluation['overall_quality']}"

    def test_react_quality_consistency(
        self, global_state, quality_analyzer, mock_llm_service
    ):
        """测试ReAct质量一致性"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟一致的高质量响应
            consistent_reasoning = """
            我需要系统性地分析当前任务。首先，我会理解任务要求，
            因为这是后续工作的基础。然后，我会制定执行计划。
            基于分析，我选择相应的行动。
            """

            mock_llm_service.invoke_sync.return_value = Mock(
                content=consistent_reasoning
            )

            tester = TesterAgent(global_state)
            input_data = AgentInput(data={"test_requirements": "一致性测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 多次执行
                quality_scores = []
                for _ in range(3):
                    result = tester.execute(input_data)
                    react_history = result.data.get("react_history", [])

                    if react_history:
                        evaluation = quality_analyzer.evaluate_react_cycle_quality(
                            react_history[0]
                        )
                        quality_scores.append(evaluation["overall_quality"])

                # 验证质量一致性
                if len(quality_scores) > 1:
                    quality_variance = max(quality_scores) - min(quality_scores)
                    assert (
                        quality_variance < 0.2
                    ), f"质量一致性不足，方差: {quality_variance}"

    def test_react_quality_improvement_over_iterations(
        self, global_state, quality_analyzer, mock_llm_service
    ):
        """测试ReAct质量在迭代中的改进"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟质量逐步提升的响应
            improving_responses = [
                Mock(content="开始分析任务"),  # 简单推理
                Mock(
                    content="我需要深入分析任务需求，首先理解背景，然后制定计划"
                ),  # 中等推理
                Mock(
                    content="我需要系统性地分析任务。首先，我应该理解需求，因为这是基础。然后制定详细计划。基于分析，我选择最佳行动"
                ),  # 高质量推理
            ]

            mock_llm_service.invoke_sync.side_effect = improving_responses

            tester = TesterAgent(global_state)
            tester.max_iterations = 3

            input_data = AgentInput(data={"test_requirements": "改进测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 执行智能体
                result = tester.execute(input_data)
                react_history = result.data.get("react_history", [])

                # 分析质量改进趋势
                quality_scores = []
                for step in react_history:
                    evaluation = quality_analyzer.evaluate_react_cycle_quality(step)
                    quality_scores.append(evaluation["overall_quality"])

                # 验证质量改进（允许一定波动）
                if len(quality_scores) >= 2:
                    # 检查总体趋势是否向上
                    first_half_avg = sum(quality_scores[: len(quality_scores) // 2]) / (
                        len(quality_scores) // 2
                    )
                    second_half_avg = sum(
                        quality_scores[len(quality_scores) // 2 :]
                    ) / (len(quality_scores) - len(quality_scores) // 2)

                    # 允许轻微下降，但总体应该有改进趋势
                    improvement = second_half_avg - first_half_avg
                    assert improvement >= -0.1, f"质量未显示改进趋势: {improvement}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
