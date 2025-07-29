#!/usr/bin/env python3
"""
ReAct循环质量测试

实现ReAct循环的行为测试和质量验证，创建推理质量和动作选择的自动化评估，
建立回归测试防止行为退化。
"""

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import create_tester_agent, create_coder_agent
from src.core.base_agent import AgentInput, ReActAgent
from src.models.types import AgentType
from src.models.workspace import GlobalState


@dataclass
class ReActQualityMetrics:
    """ReAct质量指标"""

    reasoning_clarity: float
    reasoning_logic: float
    reasoning_relevance: float
    reasoning_completeness: float
    action_appropriateness: float
    action_efficiency: float
    action_success_rate: float
    observation_informativeness: float
    observation_accuracy: float
    observation_actionability: float
    overall_quality: float


class ReActQualityAnalyzer:
    """ReAct质量分析器"""

    def __init__(self):
        self.quality_standards = {
            "reasoning_clarity": 0.7,
            "reasoning_logic": 0.7,
            "reasoning_relevance": 0.8,
            "reasoning_completeness": 0.6,
            "action_appropriateness": 0.8,
            "action_efficiency": 0.7,
            "action_success_rate": 0.9,
            "observation_informativeness": 0.7,
            "observation_accuracy": 0.8,
            "observation_actionability": 0.6,
            "overall_quality": 0.75,
        }

    def analyze_reasoning_quality(self, reasoning: str) -> Dict[str, float]:
        """分析推理质量"""
        metrics = {
            "clarity": 0.0,
            "logic": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
        }

        # 清晰度评估
        clarity_indicators = [
            ("结构化表达", ["首先", "然后", "最后", "因此", "所以"]),
            ("明确表述", ["我需要", "我应该", "我将要", "目标是"]),
            ("逻辑连接", ["因为", "由于", "基于", "根据"]),
        ]

        clarity_score = 0.0
        for indicator_name, keywords in clarity_indicators:
            if any(keyword in reasoning for keyword in keywords):
                clarity_score += 0.33

        metrics["clarity"] = min(1.0, clarity_score)

        # 逻辑性评估
        logic_indicators = [
            ("条件推理", ["如果", "那么", "假设", "当"]),
            ("因果关系", ["导致", "引起", "造成", "产生"]),
            ("推理链", ["基于此", "因此可以", "进而", "从而"]),
        ]

        logic_score = 0.0
        for indicator_name, keywords in logic_indicators:
            if any(keyword in reasoning for keyword in keywords):
                logic_score += 0.33

        metrics["logic"] = min(1.0, logic_score)

        # 相关性评估
        task_keywords = [
            "测试",
            "用例",
            "脚本",
            "代码",
            "验证",
            "检查",
            "分析",
            "生成",
            "创建",
            "执行",
            "评估",
        ]

        relevance_count = sum(1 for keyword in task_keywords if keyword in reasoning)
        metrics["relevance"] = min(1.0, relevance_count * 0.15)

        # 完整性评估
        completeness_indicators = [
            ("问题识别", ["问题", "需要", "缺少", "不足"]),
            ("解决方案", ["方法", "策略", "方案", "步骤"]),
            ("预期结果", ["预期", "期望", "目标", "结果"]),
        ]

        completeness_score = 0.0
        for indicator_name, keywords in completeness_indicators:
            if any(keyword in reasoning for keyword in keywords):
                completeness_score += 0.33

        # 长度奖励
        if len(reasoning) > 50:
            completeness_score += 0.2
        if len(reasoning) > 100:
            completeness_score += 0.2

        metrics["completeness"] = min(1.0, completeness_score)

        return metrics

    def analyze_action_quality(
        self, action_result: Dict[str, Any], expected_actions: List[str] = None
    ) -> Dict[str, float]:
        """分析动作质量"""
        metrics = {
            "appropriateness": 0.0,
            "efficiency": 0.0,
            "success_rate": 0.0,
        }

        action_type = action_result.get("action_type", "")
        success = action_result.get("success", False)
        output = action_result.get("output", "")

        # 适当性评估
        if expected_actions:
            if action_type in expected_actions:
                metrics["appropriateness"] = 1.0
            elif any(expected in action_type for expected in expected_actions):
                metrics["appropriateness"] = 0.7
            else:
                metrics["appropriateness"] = 0.3
        else:
            # 基于动作类型的通用评估
            valid_action_types = [
                "read_requirements",
                "generate_test_cases",
                "create_mindmap",
                "analyze_test_cases",
                "generate_test_script",
                "validate_code",
                "update_todo",
                "analyze_coverage",
            ]
            if action_type in valid_action_types:
                metrics["appropriateness"] = 0.8
            else:
                metrics["appropriateness"] = 0.4

        # 效率评估
        if success:
            base_efficiency = 0.7

            # 输出质量奖励
            if len(output) > 50:
                base_efficiency += 0.2
            if len(output) > 200:
                base_efficiency += 0.1

            metrics["efficiency"] = min(1.0, base_efficiency)
        else:
            metrics["efficiency"] = 0.2

        # 成功率
        metrics["success_rate"] = 1.0 if success else 0.0

        return metrics

    def analyze_observation_quality(self, observation: str) -> Dict[str, float]:
        """分析观察质量"""
        metrics = {
            "informativeness": 0.0,
            "accuracy": 0.0,
            "actionability": 0.0,
        }

        # 信息量评估
        info_indicators = [
            ("状态描述", ["成功", "失败", "完成", "错误"]),
            ("结果描述", ["结果", "输出", "生成", "创建"]),
            ("数量信息", ["个", "项", "条", "次"]),
        ]

        info_score = 0.0
        for indicator_name, keywords in info_indicators:
            if any(keyword in observation for keyword in keywords):
                info_score += 0.25

        # 长度奖励
        if len(observation) > 30:
            info_score += 0.25

        metrics["informativeness"] = min(1.0, info_score)

        # 准确性评估
        accuracy_indicators = [
            ("明确状态", ["行动类型", "执行状态"]),
            ("具体信息", ["输出结果", "错误信息"]),
            ("量化描述", ["数量", "时间", "大小"]),
        ]

        accuracy_score = 0.0
        for indicator_name, keywords in accuracy_indicators:
            if any(keyword in observation for keyword in keywords):
                accuracy_score += 0.33

        metrics["accuracy"] = min(1.0, accuracy_score)

        # 可操作性评估
        actionability_indicators = [
            ("继续指导", ["继续", "下一步", "接下来"]),
            ("完成信号", ["完成", "结束", "成功"]),
            ("建议指导", ["建议", "需要", "应该"]),
        ]

        actionability_score = 0.0
        for indicator_name, keywords in actionability_indicators:
            if any(keyword in observation for keyword in keywords):
                actionability_score += 0.33

        metrics["actionability"] = min(1.0, actionability_score)

        return metrics

    def calculate_overall_quality(
        self, react_history: List[Dict[str, Any]]
    ) -> ReActQualityMetrics:
        """计算整体质量指标"""
        if not react_history:
            return ReActQualityMetrics(
                reasoning_clarity=0.0,
                reasoning_logic=0.0,
                reasoning_relevance=0.0,
                reasoning_completeness=0.0,
                action_appropriateness=0.0,
                action_efficiency=0.0,
                action_success_rate=0.0,
                observation_informativeness=0.0,
                observation_accuracy=0.0,
                observation_actionability=0.0,
                overall_quality=0.0,
            )

        # 收集所有指标
        reasoning_metrics = []
        action_metrics = []
        observation_metrics = []

        for step in react_history:
            # 分析推理
            reasoning = step.get("reasoning", "")
            if reasoning:
                reasoning_quality = self.analyze_reasoning_quality(reasoning)
                reasoning_metrics.append(reasoning_quality)

            # 分析动作
            action = step.get("action", {})
            if action:
                action_quality = self.analyze_action_quality(action)
                action_metrics.append(action_quality)

            # 分析观察
            observation = step.get("observation", "")
            if observation:
                observation_quality = self.analyze_observation_quality(observation)
                observation_metrics.append(observation_quality)

        # 计算平均值
        def avg_metric(metrics_list: List[Dict[str, float]], key: str) -> float:
            if not metrics_list:
                return 0.0
            values = [m.get(key, 0.0) for m in metrics_list]
            return sum(values) / len(values)

        reasoning_clarity = avg_metric(reasoning_metrics, "clarity")
        reasoning_logic = avg_metric(reasoning_metrics, "logic")
        reasoning_relevance = avg_metric(reasoning_metrics, "relevance")
        reasoning_completeness = avg_metric(reasoning_metrics, "completeness")

        action_appropriateness = avg_metric(action_metrics, "appropriateness")
        action_efficiency = avg_metric(action_metrics, "efficiency")
        action_success_rate = avg_metric(action_metrics, "success_rate")

        observation_informativeness = avg_metric(observation_metrics, "informativeness")
        observation_accuracy = avg_metric(observation_metrics, "accuracy")
        observation_actionability = avg_metric(observation_metrics, "actionability")

        # 计算整体质量
        all_metrics = [
            reasoning_clarity,
            reasoning_logic,
            reasoning_relevance,
            reasoning_completeness,
            action_appropriateness,
            action_efficiency,
            action_success_rate,
            observation_informativeness,
            observation_accuracy,
            observation_actionability,
        ]

        overall_quality = sum(all_metrics) / len(all_metrics)

        return ReActQualityMetrics(
            reasoning_clarity=reasoning_clarity,
            reasoning_logic=reasoning_logic,
            reasoning_relevance=reasoning_relevance,
            reasoning_completeness=reasoning_completeness,
            action_appropriateness=action_appropriateness,
            action_efficiency=action_efficiency,
            action_success_rate=action_success_rate,
            observation_informativeness=observation_informativeness,
            observation_accuracy=observation_accuracy,
            observation_actionability=observation_actionability,
            overall_quality=overall_quality,
        )

    def evaluate_quality_standards(
        self, metrics: ReActQualityMetrics
    ) -> Dict[str, bool]:
        """评估是否满足质量标准"""
        evaluations = {}

        for metric_name, standard_value in self.quality_standards.items():
            actual_value = getattr(metrics, metric_name)
            evaluations[metric_name] = actual_value >= standard_value

        return evaluations

    def detect_quality_regression(
        self,
        current_metrics: ReActQualityMetrics,
        baseline_metrics: ReActQualityMetrics,
    ) -> Dict[str, Any]:
        """检测质量回归"""
        regression_report = {
            "has_regression": False,
            "degraded_metrics": [],
            "improved_metrics": [],
            "overall_change": 0.0,
        }

        threshold = 0.1  # 10%变化阈值

        metric_names = [
            "reasoning_clarity",
            "reasoning_logic",
            "reasoning_relevance",
            "reasoning_completeness",
            "action_appropriateness",
            "action_efficiency",
            "action_success_rate",
            "observation_informativeness",
            "observation_accuracy",
            "observation_actionability",
            "overall_quality",
        ]

        changes = []

        for metric_name in metric_names:
            current_value = getattr(current_metrics, metric_name)
            baseline_value = getattr(baseline_metrics, metric_name)

            if baseline_value > 0:
                change = (current_value - baseline_value) / baseline_value
            else:
                change = current_value - baseline_value

            changes.append(change)

            if change < -threshold:
                regression_report["degraded_metrics"].append(
                    {
                        "metric": metric_name,
                        "current": current_value,
                        "baseline": baseline_value,
                        "change": change,
                    }
                )
                regression_report["has_regression"] = True
            elif change > threshold:
                regression_report["improved_metrics"].append(
                    {
                        "metric": metric_name,
                        "current": current_value,
                        "baseline": baseline_value,
                        "change": change,
                    }
                )

        # 计算总体变化
        if changes:
            regression_report["overall_change"] = sum(changes) / len(changes)

        return regression_report


class ReActBehaviorTester:
    """ReAct行为测试器"""

    def __init__(self):
        self.analyzer = ReActQualityAnalyzer()
        self.test_scenarios = []

    def add_test_scenario(
        self, name: str, input_data: Dict[str, Any], expected_actions: List[str] = None
    ):
        """添加测试场景"""
        self.test_scenarios.append(
            {
                "name": name,
                "input_data": input_data,
                "expected_actions": expected_actions or [],
            }
        )

    def test_agent_react_behavior(
        self, agent: ReActAgent, scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """测试智能体ReAct行为"""
        input_data = AgentInput(data=scenario["input_data"])

        # 执行智能体
        result = agent.execute(input_data)

        # 提取ReAct历史
        react_history = result.data.get("react_history", [])

        # 分析质量
        quality_metrics = self.analyzer.calculate_overall_quality(react_history)
        quality_evaluations = self.analyzer.evaluate_quality_standards(quality_metrics)

        return {
            "scenario_name": scenario["name"],
            "react_history": react_history,
            "quality_metrics": quality_metrics,
            "quality_evaluations": quality_evaluations,
            "meets_standards": all(quality_evaluations.values()),
            "execution_success": result.error is None,
            "iterations_used": len(react_history),
        }

    def run_comprehensive_behavior_test(self, agent: ReActAgent) -> Dict[str, Any]:
        """运行综合行为测试"""
        test_results = []

        for scenario in self.test_scenarios:
            result = self.test_agent_react_behavior(agent, scenario)
            test_results.append(result)

        # 汇总结果
        total_scenarios = len(test_results)
        successful_executions = sum(1 for r in test_results if r["execution_success"])
        meets_standards_count = sum(1 for r in test_results if r["meets_standards"])

        # 计算平均质量指标
        if test_results:
            avg_metrics = self._calculate_average_metrics(test_results)
        else:
            avg_metrics = None

        return {
            "test_results": test_results,
            "summary": {
                "total_scenarios": total_scenarios,
                "successful_executions": successful_executions,
                "execution_success_rate": (
                    successful_executions / total_scenarios
                    if total_scenarios > 0
                    else 0
                ),
                "meets_standards_count": meets_standards_count,
                "quality_compliance_rate": (
                    meets_standards_count / total_scenarios
                    if total_scenarios > 0
                    else 0
                ),
            },
            "average_metrics": avg_metrics,
        }

    def _calculate_average_metrics(
        self, test_results: List[Dict[str, Any]]
    ) -> ReActQualityMetrics:
        """计算平均质量指标"""
        if not test_results:
            return None

        metric_sums = {
            "reasoning_clarity": 0.0,
            "reasoning_logic": 0.0,
            "reasoning_relevance": 0.0,
            "reasoning_completeness": 0.0,
            "action_appropriateness": 0.0,
            "action_efficiency": 0.0,
            "action_success_rate": 0.0,
            "observation_informativeness": 0.0,
            "observation_accuracy": 0.0,
            "observation_actionability": 0.0,
            "overall_quality": 0.0,
        }

        for result in test_results:
            metrics = result["quality_metrics"]
            for metric_name in metric_sums.keys():
                metric_sums[metric_name] += getattr(metrics, metric_name)

        count = len(test_results)

        return ReActQualityMetrics(
            reasoning_clarity=metric_sums["reasoning_clarity"] / count,
            reasoning_logic=metric_sums["reasoning_logic"] / count,
            reasoning_relevance=metric_sums["reasoning_relevance"] / count,
            reasoning_completeness=metric_sums["reasoning_completeness"] / count,
            action_appropriateness=metric_sums["action_appropriateness"] / count,
            action_efficiency=metric_sums["action_efficiency"] / count,
            action_success_rate=metric_sums["action_success_rate"] / count,
            observation_informativeness=metric_sums["observation_informativeness"]
            / count,
            observation_accuracy=metric_sums["observation_accuracy"] / count,
            observation_actionability=metric_sums["observation_actionability"] / count,
            overall_quality=metric_sums["overall_quality"] / count,
        )


class TestReActLoopQuality:
    """ReAct循环质量测试类"""

    @pytest.fixture
    def global_state(self):
        """创建全局状态"""
        return GlobalState()

    @pytest.fixture
    def quality_analyzer(self):
        """创建质量分析器"""
        return ReActQualityAnalyzer()

    @pytest.fixture
    def behavior_tester(self):
        """创建行为测试器"""
        tester = ReActBehaviorTester()

        # 添加标准测试场景
        tester.add_test_scenario(
            name="test_case_generation",
            input_data={"test_requirements": "用户登录功能测试"},
            expected_actions=[
                "read_requirements",
                "generate_test_cases",
                "create_mindmap",
            ],
        )

        tester.add_test_scenario(
            name="complex_analysis",
            input_data={
                "test_requirements": "电商系统完整功能测试，包括用户管理、商品管理、订单处理、支付系统"
            },
            expected_actions=[
                "read_requirements",
                "analyze_complexity",
                "generate_test_cases",
                "create_mindmap",
            ],
        )

        return tester

    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        mock_service = Mock()

        # 模拟高质量推理响应
        high_quality_responses = [
            Mock(
                content="""
            我需要仔细分析当前的测试需求。首先，我应该理解用户登录功能的具体要求，
            包括正常登录流程、异常处理和安全考虑。然后，我会基于这些需求设计全面的测试用例，
            覆盖正常场景、异常场景和边界条件。最后，我将创建思维导图来可视化测试覆盖范围。
            基于以上分析，我选择读取需求文档的行动。
            """
            ),
            Mock(
                content="""
            基于需求分析，我现在需要生成具体的测试用例。我将创建包含正常登录、
            密码错误、用户名不存在、账户锁定等多种场景的测试用例。每个测试用例
            都将包含明确的前置条件、测试步骤和预期结果。
            """
            ),
            Mock(
                content="""
            测试用例生成完成后，我需要创建思维导图来展示测试策略和覆盖范围。
            这将帮助可视化测试的完整性和系统性。
            """
            ),
        ]

        mock_service.invoke_sync.side_effect = high_quality_responses
        return mock_service

    def test_reasoning_quality_analysis(self, quality_analyzer):
        """测试推理质量分析"""
        # 高质量推理示例
        high_quality_reasoning = """
        我需要分析当前的测试任务。首先，我应该理解需求文档的内容，
        因为这是生成有效测试用例的基础。然后，我会根据需求设计测试场景，
        包括正常情况、异常情况和边界条件。最后，我会创建思维导图来
        可视化测试覆盖范围。基于以上分析，我选择读取需求文档的行动。
        """

        # 低质量推理示例
        low_quality_reasoning = "执行测试"

        # 分析高质量推理
        high_metrics = quality_analyzer.analyze_reasoning_quality(
            high_quality_reasoning
        )
        assert (
            high_metrics["clarity"] >= 0.7
        ), f"高质量推理清晰度不足: {high_metrics['clarity']}"
        assert (
            high_metrics["logic"] >= 0.6
        ), f"高质量推理逻辑性不足: {high_metrics['logic']}"
        assert (
            high_metrics["relevance"] >= 0.8
        ), f"高质量推理相关性不足: {high_metrics['relevance']}"
        assert (
            high_metrics["completeness"] >= 0.8
        ), f"高质量推理完整性不足: {high_metrics['completeness']}"

        # 分析低质量推理
        low_metrics = quality_analyzer.analyze_reasoning_quality(low_quality_reasoning)
        assert (
            low_metrics["clarity"] < 0.5
        ), f"低质量推理清晰度评估过高: {low_metrics['clarity']}"
        assert (
            low_metrics["logic"] < 0.5
        ), f"低质量推理逻辑性评估过高: {low_metrics['logic']}"
        assert (
            low_metrics["completeness"] < 0.5
        ), f"低质量推理完整性评估过高: {low_metrics['completeness']}"

    def test_action_quality_analysis(self, quality_analyzer):
        """测试动作质量分析"""
        # 高质量动作
        high_quality_action = {
            "action_type": "generate_test_cases",
            "success": True,
            "output": "成功生成了10个测试用例，覆盖了正常登录、密码错误、用户名不存在等场景，每个用例都包含详细的前置条件、测试步骤和预期结果。",
        }

        # 低质量动作
        low_quality_action = {
            "action_type": "unknown_action",
            "success": False,
            "output": "失败",
        }

        expected_actions = [
            "generate_test_cases",
            "read_requirements",
            "create_mindmap",
        ]

        # 分析高质量动作
        high_metrics = quality_analyzer.analyze_action_quality(
            high_quality_action, expected_actions
        )
        assert (
            high_metrics["appropriateness"] >= 0.8
        ), f"高质量动作适当性不足: {high_metrics['appropriateness']}"
        assert (
            high_metrics["efficiency"] >= 0.8
        ), f"高质量动作效率不足: {high_metrics['efficiency']}"
        assert (
            high_metrics["success_rate"] == 1.0
        ), f"高质量动作成功率不正确: {high_metrics['success_rate']}"

        # 分析低质量动作
        low_metrics = quality_analyzer.analyze_action_quality(
            low_quality_action, expected_actions
        )
        assert (
            low_metrics["appropriateness"] < 0.5
        ), f"低质量动作适当性评估过高: {low_metrics['appropriateness']}"
        assert (
            low_metrics["efficiency"] < 0.5
        ), f"低质量动作效率评估过高: {low_metrics['efficiency']}"
        assert (
            low_metrics["success_rate"] == 0.0
        ), f"低质量动作成功率不正确: {low_metrics['success_rate']}"

    def test_observation_quality_analysis(self, quality_analyzer):
        """测试观察质量分析"""
        # 高质量观察
        high_quality_observation = """
        行动类型: generate_test_cases
        执行状态: 成功
        输出结果: 成功生成了8个测试用例，包含正常登录、密码错误、用户名不存在、
        账户锁定等场景。每个测试用例都包含详细的前置条件、测试步骤和预期结果。
        建议继续创建思维导图来可视化测试覆盖范围。
        """

        # 低质量观察
        low_quality_observation = "完成"

        # 分析高质量观察
        high_metrics = quality_analyzer.analyze_observation_quality(
            high_quality_observation
        )
        assert (
            high_metrics["informativeness"] >= 0.8
        ), f"高质量观察信息量不足: {high_metrics['informativeness']}"
        assert (
            high_metrics["accuracy"] >= 0.8
        ), f"高质量观察准确性不足: {high_metrics['accuracy']}"
        assert (
            high_metrics["actionability"] >= 0.6
        ), f"高质量观察可操作性不足: {high_metrics['actionability']}"

        # 分析低质量观察
        low_metrics = quality_analyzer.analyze_observation_quality(
            low_quality_observation
        )
        assert (
            low_metrics["informativeness"] < 0.5
        ), f"低质量观察信息量评估过高: {low_metrics['informativeness']}"
        assert (
            low_metrics["accuracy"] < 0.5
        ), f"低质量观察准确性评估过高: {low_metrics['accuracy']}"

    def test_overall_quality_calculation(self, quality_analyzer):
        """测试整体质量计算"""
        # 模拟ReAct历史
        react_history = [
            {
                "iteration": 1,
                "reasoning": "我需要分析测试需求。首先理解功能要求，然后设计测试用例。基于分析，我选择读取需求的行动。",
                "action": {
                    "action_type": "read_requirements",
                    "success": True,
                    "output": "成功读取需求文档，包含用户登录功能的详细描述。",
                },
                "observation": "行动类型: read_requirements, 执行状态: 成功, 输出结果: 成功读取需求文档。建议继续生成测试用例。",
            },
            {
                "iteration": 2,
                "reasoning": "基于需求分析，现在需要生成具体的测试用例，覆盖各种场景。",
                "action": {
                    "action_type": "generate_test_cases",
                    "success": True,
                    "output": "生成了5个测试用例，覆盖正常和异常场景。",
                },
                "observation": "行动类型: generate_test_cases, 执行状态: 成功, 生成了5个测试用例。任务基本完成。",
            },
        ]

        # 计算整体质量
        metrics = quality_analyzer.calculate_overall_quality(react_history)

        # 验证质量指标
        assert 0.0 <= metrics.reasoning_clarity <= 1.0
        assert 0.0 <= metrics.reasoning_logic <= 1.0
        assert 0.0 <= metrics.reasoning_relevance <= 1.0
        assert 0.0 <= metrics.reasoning_completeness <= 1.0
        assert 0.0 <= metrics.action_appropriateness <= 1.0
        assert 0.0 <= metrics.action_efficiency <= 1.0
        assert 0.0 <= metrics.action_success_rate <= 1.0
        assert 0.0 <= metrics.observation_informativeness <= 1.0
        assert 0.0 <= metrics.observation_accuracy <= 1.0
        assert 0.0 <= metrics.observation_actionability <= 1.0
        assert 0.0 <= metrics.overall_quality <= 1.0

        # 验证合理的质量水平
        assert metrics.overall_quality > 0.3, f"整体质量过低: {metrics.overall_quality}"

    def test_quality_standards_evaluation(self, quality_analyzer):
        """测试质量标准评估"""
        # 创建满足标准的指标
        good_metrics = ReActQualityMetrics(
            reasoning_clarity=0.8,
            reasoning_logic=0.8,
            reasoning_relevance=0.9,
            reasoning_completeness=0.7,
            action_appropriateness=0.9,
            action_efficiency=0.8,
            action_success_rate=0.95,
            observation_informativeness=0.8,
            observation_accuracy=0.9,
            observation_actionability=0.7,
            overall_quality=0.8,
        )

        # 创建不满足标准的指标
        poor_metrics = ReActQualityMetrics(
            reasoning_clarity=0.5,
            reasoning_logic=0.4,
            reasoning_relevance=0.6,
            reasoning_completeness=0.3,
            action_appropriateness=0.6,
            action_efficiency=0.5,
            action_success_rate=0.7,
            observation_informativeness=0.4,
            observation_accuracy=0.5,
            observation_actionability=0.3,
            overall_quality=0.5,
        )

        # 评估好的指标
        good_evaluations = quality_analyzer.evaluate_quality_standards(good_metrics)
        good_pass_count = sum(1 for passed in good_evaluations.values() if passed)
        assert (
            good_pass_count >= len(good_evaluations) * 0.8
        ), f"好指标通过率过低: {good_pass_count}/{len(good_evaluations)}"

        # 评估差的指标
        poor_evaluations = quality_analyzer.evaluate_quality_standards(poor_metrics)
        poor_pass_count = sum(1 for passed in poor_evaluations.values() if passed)
        assert (
            poor_pass_count < len(poor_evaluations) * 0.5
        ), f"差指标通过率过高: {poor_pass_count}/{len(poor_evaluations)}"

    def test_quality_regression_detection(self, quality_analyzer):
        """测试质量回归检测"""
        # 基线指标
        baseline_metrics = ReActQualityMetrics(
            reasoning_clarity=0.8,
            reasoning_logic=0.7,
            reasoning_relevance=0.9,
            reasoning_completeness=0.6,
            action_appropriateness=0.9,
            action_efficiency=0.8,
            action_success_rate=0.95,
            observation_informativeness=0.8,
            observation_accuracy=0.9,
            observation_actionability=0.7,
            overall_quality=0.8,
        )

        # 退化指标
        degraded_metrics = ReActQualityMetrics(
            reasoning_clarity=0.6,  # 明显下降
            reasoning_logic=0.5,  # 明显下降
            reasoning_relevance=0.85,  # 轻微下降
            reasoning_completeness=0.65,  # 轻微上升
            action_appropriateness=0.8,  # 轻微下降
            action_efficiency=0.9,  # 上升
            action_success_rate=0.9,  # 轻微下降
            observation_informativeness=0.7,  # 轻微下降
            observation_accuracy=0.85,  # 轻微下降
            observation_actionability=0.6,  # 轻微下降
            overall_quality=0.7,  # 下降
        )

        # 检测回归
        regression_report = quality_analyzer.detect_quality_regression(
            degraded_metrics, baseline_metrics
        )

        # 验证回归检测
        assert regression_report["has_regression"], "未检测到明显的质量回归"
        assert len(regression_report["degraded_metrics"]) > 0, "未识别出退化的指标"
        assert regression_report["overall_change"] < 0, "总体变化应该是负数"

        # 验证具体退化指标
        degraded_metric_names = [
            m["metric"] for m in regression_report["degraded_metrics"]
        ]
        assert "reasoning_clarity" in degraded_metric_names, "未检测到推理清晰度退化"
        assert "reasoning_logic" in degraded_metric_names, "未检测到推理逻辑性退化"

    def test_tester_agent_react_behavior(
        self, global_state, behavior_tester, mock_llm_service
    ):
        """测试Tester智能体ReAct行为"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 创建Tester智能体
            tester = create_tester_agent(global_state)

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 运行综合行为测试
                test_result = behavior_tester.run_comprehensive_behavior_test(tester)

                # 验证测试结果
                assert "test_results" in test_result
                assert "summary" in test_result
                assert "average_metrics" in test_result

                summary = test_result["summary"]
                assert summary["total_scenarios"] > 0, "没有执行测试场景"
                assert (
                    summary["execution_success_rate"] >= 0.8
                ), f"执行成功率过低: {summary['execution_success_rate']}"

                # 验证平均质量指标
                avg_metrics = test_result["average_metrics"]
                if avg_metrics:
                    assert (
                        avg_metrics.overall_quality >= 0.5
                    ), f"平均质量过低: {avg_metrics.overall_quality}"
                    assert (
                        avg_metrics.reasoning_clarity >= 0.4
                    ), f"平均推理清晰度过低: {avg_metrics.reasoning_clarity}"
                    assert (
                        avg_metrics.action_success_rate >= 0.7
                    ), f"平均动作成功率过低: {avg_metrics.action_success_rate}"

    def test_coder_agent_react_behavior(self, global_state, mock_llm_service):
        """测试Coder智能体ReAct行为"""
        with patch("src.agents.coder.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 创建Coder智能体
            coder = create_coder_agent(global_state)

            # 创建行为测试器
            behavior_tester = ReActBehaviorTester()
            behavior_tester.add_test_scenario(
                name="code_generation",
                input_data={
                    "test_cases": [
                        {
                            "scenario": "用户正常登录",
                            "steps": "输入用户名密码，点击登录",
                            "expected": "登录成功",
                        }
                    ]
                },
                expected_actions=[
                    "analyze_test_cases",
                    "generate_test_script",
                    "validate_code",
                ],
            )

            # 模拟工作空间
            with patch("src.agents.coder.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_script.py"

                # 运行行为测试
                test_result = behavior_tester.run_comprehensive_behavior_test(coder)

                # 验证结果
                summary = test_result["summary"]
                assert (
                    summary["execution_success_rate"] >= 0.8
                ), f"Coder执行成功率过低: {summary['execution_success_rate']}"

                # 验证质量指标
                avg_metrics = test_result["average_metrics"]
                if avg_metrics:
                    assert (
                        avg_metrics.overall_quality >= 0.4
                    ), f"Coder平均质量过低: {avg_metrics.overall_quality}"

    def test_react_loop_consistency(self, global_state, mock_llm_service):
        """测试ReAct循环一致性"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            tester = create_tester_agent(global_state)
            behavior_tester = ReActBehaviorTester()
            behavior_tester.add_test_scenario(
                name="consistency_test",
                input_data={"test_requirements": "一致性测试需求"},
            )

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 多次运行相同测试
                results = []
                for _ in range(3):
                    result = behavior_tester.run_comprehensive_behavior_test(tester)
                    results.append(result)

                # 验证一致性
                for i in range(1, len(results)):
                    # 检查基本结构一致性
                    assert len(results[i]["test_results"]) == len(
                        results[0]["test_results"]
                    ), "测试结果数量不一致"

                    # 检查质量指标稳定性
                    if results[i]["average_metrics"] and results[0]["average_metrics"]:
                        quality_diff = abs(
                            results[i]["average_metrics"].overall_quality
                            - results[0]["average_metrics"].overall_quality
                        )
                        assert quality_diff < 0.3, f"质量指标变化过大: {quality_diff}"

    def test_react_loop_performance_impact(self, global_state, mock_llm_service):
        """测试ReAct循环对性能的影响"""
        import psutil

        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 获取初始内存
            process = psutil.Process()
            initial_memory = process.memory_info().rss

            tester = create_tester_agent(global_state)
            behavior_tester = ReActBehaviorTester()
            behavior_tester.add_test_scenario(
                name="performance_test",
                input_data={"test_requirements": "性能测试需求"},
            )

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 执行测试并测量性能
                start_time = time.time()
                result = behavior_tester.run_comprehensive_behavior_test(tester)
                execution_time = time.time() - start_time

                # 获取最终内存
                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory

                # 验证性能指标
                assert execution_time < 10.0, f"执行时间过长: {execution_time:.2f}秒"
                assert (
                    memory_increase < 100 * 1024 * 1024
                ), f"内存增长过多: {memory_increase / 1024 / 1024:.1f}MB"

                # 验证ReAct历史不会过大
                for test_result in result["test_results"]:
                    react_history = test_result["react_history"]
                    total_content_size = sum(len(str(step)) for step in react_history)
                    assert (
                        total_content_size < 50000
                    ), f"ReAct历史内容过大: {total_content_size} 字符"


if __name__ == "__main__":
    # 运行ReAct循环质量测试
    pytest.main([__file__, "-v", "--tb=short"])
