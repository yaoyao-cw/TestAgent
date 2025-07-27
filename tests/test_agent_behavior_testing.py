#!/usr/bin/env python3
"""
智能体行为测试

实现ReAct循环的行为测试和质量验证，创建推理质量和动作选择的自动化评估，
建立回归测试防止行为退化。
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import (
    CoderAgent,
    TesterAgent,
    create_coder_agent,
    create_tester_agent,
)
from src.core.base_agent import AgentInput, ReActAgent
from src.models.types import AgentType
from src.models.workspace import GlobalState


class ReActBehaviorTester:
    """ReAct行为测试器

    用于测试智能体的ReAct循环行为质量和一致性
    """

    def __init__(self):
        self.test_scenarios = []
        self.behavior_baselines = {}
        self.quality_metrics = {}

    def add_test_scenario(
        self,
        name: str,
        input_data: Dict[str, Any],
        expected_actions: List[str],
        quality_criteria: Dict[str, Any],
    ):
        """添加测试场景"""
        self.test_scenarios.append(
            {
                "name": name,
                "input_data": input_data,
                "expected_actions": expected_actions,
                "quality_criteria": quality_criteria,
            }
        )

    def evaluate_reasoning_quality(self, reasoning: str) -> Dict[str, float]:
        """评估推理质量"""
        metrics = {
            "clarity": 0.0,  # 清晰度
            "logic": 0.0,  # 逻辑性
            "relevance": 0.0,  # 相关性
            "completeness": 0.0,  # 完整性
        }

        # 清晰度评估 - 基于结构化程度
        if "分析" in reasoning and "行动" in reasoning:
            metrics["clarity"] += 0.3
        if "因为" in reasoning or "所以" in reasoning:
            metrics["clarity"] += 0.3
        if len(reasoning.split("。")) >= 3:  # 至少3个完整句子
            metrics["clarity"] += 0.4

        # 逻辑性评估 - 基于推理链
        if "首先" in reasoning or "然后" in reasoning or "最后" in reasoning:
            metrics["logic"] += 0.4
        if "如果" in reasoning and "那么" in reasoning:
            metrics["logic"] += 0.3
        if "基于" in reasoning or "根据" in reasoning:
            metrics["logic"] += 0.3

        # 相关性评估 - 基于关键词匹配
        task_keywords = ["测试", "用例", "脚本", "代码", "验证"]
        keyword_count = sum(1 for keyword in task_keywords if keyword in reasoning)
        metrics["relevance"] = min(1.0, keyword_count * 0.2)

        # 完整性评估 - 基于内容长度和结构
        if len(reasoning) > 100:
            metrics["completeness"] += 0.4
        if "目标" in reasoning or "计划" in reasoning:
            metrics["completeness"] += 0.3
        if "结果" in reasoning or "预期" in reasoning:
            metrics["completeness"] += 0.3

        return metrics

    def evaluate_action_selection(
        self, action_result: Dict[str, Any], expected_actions: List[str]
    ) -> Dict[str, float]:
        """评估动作选择质量"""
        metrics = {
            "appropriateness": 0.0,  # 适当性
            "efficiency": 0.0,  # 效率
            "success_rate": 0.0,  # 成功率
        }

        action_type = action_result.get("action_type", "")
        success = action_result.get("success", False)

        # 适当性评估 - 动作是否在预期范围内
        if action_type in expected_actions:
            metrics["appropriateness"] = 1.0
        elif any(expected in action_type for expected in expected_actions):
            metrics["appropriateness"] = 0.7
        else:
            metrics["appropriateness"] = 0.3

        # 效率评估 - 基于动作执行时间和复杂度
        if success:
            metrics["efficiency"] = 0.8
            if "output" in action_result and len(action_result["output"]) > 50:
                metrics["efficiency"] = 1.0
        else:
            metrics["efficiency"] = 0.2

        # 成功率评估
        metrics["success_rate"] = 1.0 if success else 0.0

        return metrics

    def evaluate_observation_quality(self, observation: str) -> Dict[str, float]:
        """评估观察质量"""
        metrics = {
            "informativeness": 0.0,  # 信息量
            "accuracy": 0.0,  # 准确性
            "actionability": 0.0,  # 可操作性
        }

        # 信息量评估
        if "成功" in observation or "失败" in observation:
            metrics["informativeness"] += 0.3
        if "结果" in observation or "输出" in observation:
            metrics["informativeness"] += 0.3
        if len(observation) > 50:
            metrics["informativeness"] += 0.4

        # 准确性评估 - 基于状态描述的一致性
        if "行动类型" in observation and "执行状态" in observation:
            metrics["accuracy"] = 0.8
        if "错误信息" in observation or "输出结果" in observation:
            metrics["accuracy"] = 1.0

        # 可操作性评估 - 是否提供下一步指导
        if "完成" in observation or "继续" in observation:
            metrics["actionability"] += 0.5
        if "建议" in observation or "需要" in observation:
            metrics["actionability"] += 0.5

        return metrics

    def detect_behavior_regression(
        self, current_behavior: Dict[str, Any], baseline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检测行为退化"""
        regression_report = {
            "has_regression": False,
            "degraded_metrics": [],
            "improvement_metrics": [],
            "overall_change": 0.0,
        }

        threshold = 0.1  # 10%的变化阈值

        for metric_category in ["reasoning", "action", "observation"]:
            if metric_category in current_behavior and metric_category in baseline:
                current_metrics = current_behavior[metric_category]
                baseline_metrics = baseline[metric_category]

                for metric_name in current_metrics:
                    if metric_name in baseline_metrics:
                        current_value = current_metrics[metric_name]
                        baseline_value = baseline_metrics[metric_name]
                        change = current_value - baseline_value

                        if change < -threshold:
                            regression_report["degraded_metrics"].append(
                                {
                                    "category": metric_category,
                                    "metric": metric_name,
                                    "current": current_value,
                                    "baseline": baseline_value,
                                    "change": change,
                                }
                            )
                            regression_report["has_regression"] = True
                        elif change > threshold:
                            regression_report["improvement_metrics"].append(
                                {
                                    "category": metric_category,
                                    "metric": metric_name,
                                    "current": current_value,
                                    "baseline": baseline_value,
                                    "change": change,
                                }
                            )

        # 计算总体变化
        if (
            regression_report["degraded_metrics"]
            or regression_report["improvement_metrics"]
        ):
            total_changes = [
                item["change"]
                for item in regression_report["degraded_metrics"]
                + regression_report["improvement_metrics"]
            ]
            regression_report["overall_change"] = (
                sum(total_changes) / len(total_changes) if total_changes else 0.0
            )

        return regression_report


class TestAgentBehaviorTesting:
    """智能体行为测试类"""

    @pytest.fixture
    def global_state(self):
        """创建测试用的全局状态"""
        return GlobalState()

    @pytest.fixture
    def behavior_tester(self):
        """创建行为测试器"""
        return ReActBehaviorTester()

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作空间"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        mock_service = Mock()
        mock_service.invoke_sync = Mock()
        return mock_service

    def test_tester_agent_react_loop_behavior(
        self, global_state, behavior_tester, mock_llm_service
    ):
        """测试Tester智能体的ReAct循环行为"""
        # 设置测试场景
        behavior_tester.add_test_scenario(
            name="test_case_generation",
            input_data={"test_requirements": "用户登录功能测试"},
            expected_actions=[
                "read_requirements",
                "generate_test_cases",
                "create_mindmap",
                "update_todo",
            ],
            quality_criteria={
                "min_reasoning_clarity": 0.7,
                "min_action_appropriateness": 0.8,
                "min_observation_informativeness": 0.6,
            },
        )

        # 创建Tester智能体
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                # 推理响应
                Mock(
                    content="我需要分析当前任务状态。首先，我应该读取需求文档来理解测试目标。然后生成相应的测试用例。基于分析，我选择读取需求的行动。"
                ),
                # 测试用例生成响应
                Mock(
                    content="""
## 测试用例1: 正常登录
前置条件: 用户已注册
测试步骤: 1. 输入正确用户名密码 2. 点击登录按钮
预期结果: 登录成功，跳转到主页

## 测试用例2: 密码错误
前置条件: 用户已注册
测试步骤: 1. 输入正确用户名和错误密码 2. 点击登录按钮
预期结果: 显示密码错误提示
"""
                ),
            ]

            tester = create_tester_agent(global_state)

            # 执行测试
            input_data = AgentInput(data={"test_requirements": "用户登录功能测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 执行智能体
                result = tester.execute(input_data)

                # 验证ReAct循环执行
                assert result.error is None
                assert "react_history" in result.data
                react_history = result.data["react_history"]

                # 验证ReAct循环结构
                assert len(react_history) > 0
                for step in react_history:
                    assert "reasoning" in step
                    assert "action" in step
                    assert "observation" in step

                # 评估行为质量
                for step in react_history:
                    reasoning_quality = behavior_tester.evaluate_reasoning_quality(
                        step["reasoning"]
                    )
                    action_quality = behavior_tester.evaluate_action_selection(
                        step["action"],
                        behavior_tester.test_scenarios[0]["expected_actions"],
                    )
                    observation_quality = behavior_tester.evaluate_observation_quality(
                        step["observation"]
                    )

                    # 验证质量标准
                    assert (
                        reasoning_quality["clarity"] >= 0.5
                    ), f"推理清晰度不足: {reasoning_quality['clarity']}"
                    assert (
                        action_quality["appropriateness"] >= 0.5
                    ), f"动作适当性不足: {action_quality['appropriateness']}"
                    assert (
                        observation_quality["informativeness"] >= 0.5
                    ), f"观察信息量不足: {observation_quality['informativeness']}"

    def test_coder_agent_react_loop_behavior(
        self, global_state, behavior_tester, mock_llm_service
    ):
        """测试Coder智能体的ReAct循环行为"""
        # 设置测试场景
        behavior_tester.add_test_scenario(
            name="test_script_generation",
            input_data={
                "test_cases": [
                    {
                        "scenario": "用户正常登录",
                        "steps": "输入用户名密码",
                        "expected": "登录成功",
                    }
                ]
            },
            expected_actions=[
                "analyze_test_cases",
                "generate_test_script",
                "validate_code",
                "optimize_code",
            ],
            quality_criteria={
                "min_reasoning_logic": 0.7,
                "min_action_efficiency": 0.8,
                "min_observation_accuracy": 0.7,
            },
        )

        # 创建Coder智能体
        with patch("src.agents.coder.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                # 推理响应
                Mock(
                    content="我需要分析测试用例并生成相应的测试脚本。首先分析测试用例的类型和复杂度，然后选择合适的代码模板生成脚本。基于分析，我选择分析测试用例的行动。"
                ),
                # 代码生成响应
                Mock(
                    content="""
```python
import pytest

class TestLogin:
    def test_normal_login(self):
        # 测试正常登录
        username = "test_user"
        password = "test_password"
        result = login(username, password)
        assert result.success == True
        assert result.message == "登录成功"
```
"""
                ),
            ]

            coder = create_coder_agent(global_state)

            # 执行测试
            input_data = AgentInput(
                data={
                    "test_cases": [
                        {
                            "scenario": "用户正常登录",
                            "steps": "输入用户名密码",
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

                # 验证ReAct循环执行
                assert result.error is None
                assert "react_history" in result.data
                react_history = result.data["react_history"]

                # 验证ReAct循环结构
                assert len(react_history) > 0
                for step in react_history:
                    assert "reasoning" in step
                    assert "action" in step
                    assert "observation" in step

                # 评估行为质量
                for step in react_history:
                    reasoning_quality = behavior_tester.evaluate_reasoning_quality(
                        step["reasoning"]
                    )
                    action_quality = behavior_tester.evaluate_action_selection(
                        step["action"],
                        behavior_tester.test_scenarios[0]["expected_actions"],
                    )
                    observation_quality = behavior_tester.evaluate_observation_quality(
                        step["observation"]
                    )

                    # 验证质量标准
                    assert (
                        reasoning_quality["logic"] >= 0.4
                    ), f"推理逻辑性不足: {reasoning_quality['logic']}"
                    assert (
                        action_quality["efficiency"] >= 0.4
                    ), f"动作效率不足: {action_quality['efficiency']}"
                    assert (
                        observation_quality["accuracy"] >= 0.4
                    ), f"观察准确性不足: {observation_quality['accuracy']}"

    def test_react_loop_iteration_control(self, global_state, mock_llm_service):
        """测试ReAct循环的迭代控制"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应 - 设置足够多的响应以测试迭代控制
            mock_responses = []
            for i in range(10):  # 超过最大迭代次数
                mock_responses.append(Mock(content=f"第{i+1}次推理，继续执行任务分析"))

            mock_llm_service.invoke_sync.side_effect = mock_responses

            tester = create_tester_agent(global_state)
            tester.max_iterations = 3  # 设置最大迭代次数

            input_data = AgentInput(data={"test_requirements": "测试需求"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 执行智能体
                result = tester.execute(input_data)

                # 验证迭代控制
                react_history = result.data.get("react_history", [])
                assert (
                    len(react_history) <= tester.max_iterations
                ), "ReAct循环超过最大迭代次数"

                # 验证迭代次数记录
                iterations_used = result.data.get("iterations_used", 0)
                assert iterations_used <= tester.max_iterations

    def test_react_loop_early_termination(self, global_state, mock_llm_service):
        """测试ReAct循环的提前终止"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应 - 第二次迭代时任务完成
            mock_llm_service.invoke_sync.side_effect = [
                Mock(content="开始分析任务需求"),
                Mock(content="任务分析完成，生成测试用例"),
            ]

            tester = create_tester_agent(global_state)

            input_data = AgentInput(data={"test_requirements": "简单测试需求"})

            # 模拟工作空间和任务完成条件
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 模拟任务完成检查
                original_check = tester._check_task_completion

                def mock_check_completion(state):
                    # 第二次迭代后返回完成
                    return len(state.get("react_history", [])) >= 2

                tester._check_task_completion = mock_check_completion

                # 执行智能体
                result = tester.execute(input_data)

                # 验证提前终止
                react_history = result.data.get("react_history", [])
                assert len(react_history) <= 2, "ReAct循环未能提前终止"
                assert result.data.get("completed", False), "任务完成状态未正确设置"

    def test_reasoning_quality_evaluation(self, behavior_tester):
        """测试推理质量评估"""
        # 高质量推理示例
        high_quality_reasoning = """
        我需要分析当前的测试任务。首先，我应该理解需求文档的内容，
        因为这是生成有效测试用例的基础。然后，我会根据需求设计测试场景，
        包括正常情况、异常情况和边界条件。最后，我会创建思维导图来
        可视化测试覆盖范围。基于以上分析，我选择读取需求文档的行动。
        """

        # 低质量推理示例
        low_quality_reasoning = "执行测试"

        # 评估高质量推理
        high_quality_metrics = behavior_tester.evaluate_reasoning_quality(
            high_quality_reasoning
        )
        assert high_quality_metrics["clarity"] > 0.7
        assert high_quality_metrics["logic"] > 0.7
        assert high_quality_metrics["completeness"] > 0.7

        # 评估低质量推理
        low_quality_metrics = behavior_tester.evaluate_reasoning_quality(
            low_quality_reasoning
        )
        assert low_quality_metrics["clarity"] < 0.5
        assert low_quality_metrics["logic"] < 0.5
        assert low_quality_metrics["completeness"] < 0.5

    def test_action_selection_evaluation(self, behavior_tester):
        """测试动作选择评估"""
        expected_actions = [
            "read_requirements",
            "generate_test_cases",
            "create_mindmap",
        ]

        # 适当的动作选择
        appropriate_action = {
            "action_type": "read_requirements",
            "success": True,
            "output": "成功读取需求文档，包含用户登录功能的详细描述",
        }

        # 不适当的动作选择
        inappropriate_action = {
            "action_type": "unknown_action",
            "success": False,
            "output": "执行失败",
        }

        # 评估适当动作
        appropriate_metrics = behavior_tester.evaluate_action_selection(
            appropriate_action, expected_actions
        )
        assert appropriate_metrics["appropriateness"] == 1.0
        assert appropriate_metrics["success_rate"] == 1.0

        # 评估不适当动作
        inappropriate_metrics = behavior_tester.evaluate_action_selection(
            inappropriate_action, expected_actions
        )
        assert inappropriate_metrics["appropriateness"] < 0.5
        assert inappropriate_metrics["success_rate"] == 0.0

    def test_observation_quality_evaluation(self, behavior_tester):
        """测试观察质量评估"""
        # 高质量观察
        high_quality_observation = """
        行动类型: read_requirements
        执行状态: 成功
        输出结果: 成功读取需求文档，包含3个主要功能模块的详细描述，
        为后续测试用例生成提供了充分的信息基础。建议继续生成测试用例。
        """

        # 低质量观察
        low_quality_observation = "完成"

        # 评估高质量观察
        high_quality_metrics = behavior_tester.evaluate_observation_quality(
            high_quality_observation
        )
        assert high_quality_metrics["informativeness"] > 0.8
        assert high_quality_metrics["accuracy"] > 0.8
        assert high_quality_metrics["actionability"] > 0.5

        # 评估低质量观察
        low_quality_metrics = behavior_tester.evaluate_observation_quality(
            low_quality_observation
        )
        assert low_quality_metrics["informativeness"] < 0.5
        assert low_quality_metrics["accuracy"] < 0.5

    def test_behavior_regression_detection(self, behavior_tester):
        """测试行为退化检测"""
        # 基线行为
        baseline_behavior = {
            "reasoning": {"clarity": 0.8, "logic": 0.7, "relevance": 0.9},
            "action": {"appropriateness": 0.9, "efficiency": 0.8},
            "observation": {"informativeness": 0.8, "accuracy": 0.9},
        }

        # 退化行为
        degraded_behavior = {
            "reasoning": {"clarity": 0.6, "logic": 0.5, "relevance": 0.7},  # 明显下降
            "action": {"appropriateness": 0.8, "efficiency": 0.9},  # 略有改善
            "observation": {"informativeness": 0.6, "accuracy": 0.7},  # 下降
        }

        # 检测退化
        regression_report = behavior_tester.detect_behavior_regression(
            degraded_behavior, baseline_behavior
        )

        assert regression_report["has_regression"] is True
        assert len(regression_report["degraded_metrics"]) > 0
        assert regression_report["overall_change"] < 0  # 总体下降

        # 验证具体退化指标
        degraded_metrics = regression_report["degraded_metrics"]
        clarity_degraded = any(
            metric["metric"] == "clarity" for metric in degraded_metrics
        )
        assert clarity_degraded, "未检测到推理清晰度退化"

    def test_react_loop_error_handling(self, global_state, mock_llm_service):
        """测试ReAct循环的错误处理"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM服务异常
            mock_llm_service.invoke_sync.side_effect = Exception("LLM服务异常")

            tester = create_tester_agent(global_state)
            input_data = AgentInput(data={"test_requirements": "测试需求"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 执行智能体
                result = tester.execute(input_data)

                # 验证错误处理
                assert result.error is not None
                assert "LLM服务异常" in result.error or "推理出错" in str(result.data)

    def test_react_loop_performance_metrics(self, global_state, mock_llm_service):
        """测试ReAct循环的性能指标"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(content="快速推理响应"),
                Mock(content="第二次推理响应"),
            ]

            tester = create_tester_agent(global_state)
            input_data = AgentInput(data={"test_requirements": "性能测试需求"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 记录执行时间
                start_time = time.time()
                result = tester.execute(input_data)
                execution_time = time.time() - start_time

                # 验证性能指标
                assert execution_time < 10.0, f"执行时间过长: {execution_time}秒"
                assert result.data.get("iterations_used", 0) <= tester.max_iterations

                # 验证内存使用（简单检查）
                react_history = result.data.get("react_history", [])
                total_content_length = sum(len(str(step)) for step in react_history)
                assert (
                    total_content_length < 100000
                ), "ReAct历史内容过大，可能存在内存泄漏"

    def test_react_loop_consistency(self, global_state, mock_llm_service):
        """测试ReAct循环的一致性"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟一致的LLM响应
            consistent_response = Mock(content="一致的推理分析和行动选择")
            mock_llm_service.invoke_sync.return_value = consistent_response

            tester = create_tester_agent(global_state)
            input_data = AgentInput(data={"test_requirements": "一致性测试需求"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 多次执行相同输入
                results = []
                for _ in range(3):
                    result = tester.execute(input_data)
                    results.append(result)

                # 验证一致性
                for i in range(1, len(results)):
                    # 检查基本结构一致性
                    assert type(results[i].data) == type(
                        results[0].data
                    ), "返回数据结构不一致"

                    # 检查ReAct历史结构一致性
                    history_0 = results[0].data.get("react_history", [])
                    history_i = results[i].data.get("react_history", [])

                    if history_0 and history_i:
                        assert len(history_0) == len(
                            history_i
                        ), f"ReAct历史长度不一致: {len(history_0)} vs {len(history_i)}"


class TestReActBehaviorRegression:
    """ReAct行为回归测试类"""

    @pytest.fixture
    def baseline_data_file(self, tmp_path):
        """创建基线数据文件"""
        baseline_file = tmp_path / "react_behavior_baseline.json"
        baseline_data = {
            "tester_agent": {
                "reasoning": {"clarity": 0.8, "logic": 0.7, "relevance": 0.9},
                "action": {"appropriateness": 0.9, "efficiency": 0.8},
                "observation": {"informativeness": 0.8, "accuracy": 0.9},
            },
            "coder_agent": {
                "reasoning": {"clarity": 0.7, "logic": 0.8, "relevance": 0.8},
                "action": {"appropriateness": 0.8, "efficiency": 0.9},
                "observation": {"informativeness": 0.7, "accuracy": 0.8},
            },
        }

        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)

        return baseline_file

    def test_load_baseline_data(self, baseline_data_file):
        """测试加载基线数据"""
        with open(baseline_data_file, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)

        assert "tester_agent" in baseline_data
        assert "coder_agent" in baseline_data
        assert "reasoning" in baseline_data["tester_agent"]

    def test_save_current_behavior_metrics(self, tmp_path):
        """测试保存当前行为指标"""
        current_metrics = {
            "tester_agent": {
                "reasoning": {"clarity": 0.75, "logic": 0.8, "relevance": 0.85},
                "action": {"appropriateness": 0.9, "efficiency": 0.85},
                "observation": {"informativeness": 0.8, "accuracy": 0.9},
            }
        }

        metrics_file = tmp_path / "current_behavior_metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(current_metrics, f, ensure_ascii=False, indent=2)

        # 验证保存
        assert metrics_file.exists()

        # 验证加载
        with open(metrics_file, "r", encoding="utf-8") as f:
            loaded_metrics = json.load(f)

        assert loaded_metrics == current_metrics

    def test_regression_report_generation(self, baseline_data_file, tmp_path):
        """测试回归报告生成"""
        # 加载基线数据
        with open(baseline_data_file, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)

        # 模拟当前行为数据（有退化）
        current_data = {
            "tester_agent": {
                "reasoning": {"clarity": 0.6, "logic": 0.5, "relevance": 0.8},  # 退化
                "action": {"appropriateness": 0.9, "efficiency": 0.9},  # 改善
                "observation": {"informativeness": 0.7, "accuracy": 0.8},  # 轻微退化
            }
        }

        # 生成回归报告
        behavior_tester = ReActBehaviorTester()
        regression_report = behavior_tester.detect_behavior_regression(
            current_data["tester_agent"], baseline_data["tester_agent"]
        )

        # 保存报告
        report_file = tmp_path / "regression_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(regression_report, f, ensure_ascii=False, indent=2)

        # 验证报告内容
        assert regression_report["has_regression"] is True
        assert len(regression_report["degraded_metrics"]) > 0

        # 验证报告文件
        assert report_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
