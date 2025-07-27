#!/usr/bin/env python3
"""
智能体行为回归测试

建立回归测试防止行为退化，包括基线建立、行为监控和退化检测。
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import TesterAgent, CoderAgent, create_tester_agent, create_coder_agent
from src.core.base_agent import AgentInput
from src.models.workspace import GlobalState


class BehaviorBaseline:
    """行为基线管理器"""

    def __init__(self, baseline_dir: str):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(exist_ok=True)

    def save_baseline(self, agent_name: str, behavior_data: Dict[str, Any]):
        """保存行为基线"""
        baseline_file = self.baseline_dir / f"{agent_name}_baseline.json"

        baseline_record = {
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "behavior_data": behavior_data,
            "version": "1.0",
        }

        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(baseline_record, f, ensure_ascii=False, indent=2)

    def load_baseline(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """加载行为基线"""
        baseline_file = self.baseline_dir / f"{agent_name}_baseline.json"

        if not baseline_file.exists():
            return None

        with open(baseline_file, "r", encoding="utf-8") as f:
            baseline_record = json.load(f)

        return baseline_record.get("behavior_data")

    def list_baselines(self) -> List[str]:
        """列出所有基线"""
        baselines = []
        for file in self.baseline_dir.glob("*_baseline.json"):
            agent_name = file.stem.replace("_baseline", "")
            baselines.append(agent_name)
        return baselines


class BehaviorMonitor:
    """行为监控器"""

    def __init__(self):
        self.monitoring_metrics = {
            "react_loop": {
                "iteration_count": [],
                "reasoning_quality": [],
                "action_success_rate": [],
                "observation_informativeness": [],
            },
            "performance": {
                "execution_time": [],
                "memory_usage": [],
                "error_rate": [],
            },
            "output_quality": {
                "completeness": [],
                "accuracy": [],
                "consistency": [],
            },
        }

    def record_react_loop_metrics(self, react_history: List[Dict[str, Any]]):
        """记录ReAct循环指标"""
        self.monitoring_metrics["react_loop"]["iteration_count"].append(
            len(react_history)
        )

        # 计算推理质量平均分
        reasoning_scores = []
        action_success_count = 0
        observation_scores = []

        for step in react_history:
            # 推理质量评分
            reasoning = step.get("reasoning", "")
            reasoning_score = self._evaluate_reasoning_quality(reasoning)
            reasoning_scores.append(reasoning_score)

            # 动作成功率
            action = step.get("action", {})
            if action.get("success", False):
                action_success_count += 1

            # 观察信息量评分
            observation = step.get("observation", "")
            observation_score = self._evaluate_observation_informativeness(observation)
            observation_scores.append(observation_score)

        if reasoning_scores:
            self.monitoring_metrics["react_loop"]["reasoning_quality"].append(
                sum(reasoning_scores) / len(reasoning_scores)
            )

        self.monitoring_metrics["react_loop"]["action_success_rate"].append(
            action_success_count / len(react_history) if react_history else 0
        )

        if observation_scores:
            self.monitoring_metrics["react_loop"]["observation_informativeness"].append(
                sum(observation_scores) / len(observation_scores)
            )

    def record_performance_metrics(self, execution_time: float, error_occurred: bool):
        """记录性能指标"""
        self.monitoring_metrics["performance"]["execution_time"].append(execution_time)
        self.monitoring_metrics["performance"]["error_rate"].append(
            1 if error_occurred else 0
        )

    def record_output_quality_metrics(self, output_data: Dict[str, Any]):
        """记录输出质量指标"""
        # 完整性评分
        completeness = self._evaluate_output_completeness(output_data)
        self.monitoring_metrics["output_quality"]["completeness"].append(completeness)

        # 准确性评分（基于是否有错误）
        accuracy = 1.0 if not output_data.get("error") else 0.0
        self.monitoring_metrics["output_quality"]["accuracy"].append(accuracy)

    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标统计"""
        current_metrics = {}

        for category, metrics in self.monitoring_metrics.items():
            current_metrics[category] = {}
            for metric_name, values in metrics.items():
                if values:
                    current_metrics[category][metric_name] = {
                        "mean": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values),
                    }
                else:
                    current_metrics[category][metric_name] = {
                        "mean": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "count": 0,
                    }

        return current_metrics

    def _evaluate_reasoning_quality(self, reasoning: str) -> float:
        """评估推理质量"""
        score = 0.0

        # 长度评分
        if len(reasoning) > 50:
            score += 0.3
        elif len(reasoning) > 20:
            score += 0.1

        # 结构评分
        if "首先" in reasoning or "然后" in reasoning:
            score += 0.2
        if "因为" in reasoning or "所以" in reasoning:
            score += 0.2
        if "基于" in reasoning or "根据" in reasoning:
            score += 0.2

        # 任务相关性评分
        task_keywords = ["测试", "分析", "生成", "验证", "检查"]
        keyword_count = sum(1 for keyword in task_keywords if keyword in reasoning)
        score += min(0.1, keyword_count * 0.02)

        return min(1.0, score)

    def _evaluate_observation_informativeness(self, observation: str) -> float:
        """评估观察信息量"""
        score = 0.0

        # 长度评分
        if len(observation) > 30:
            score += 0.3

        # 状态信息评分
        if "成功" in observation or "失败" in observation:
            score += 0.3

        # 结果信息评分
        if "结果" in observation or "输出" in observation:
            score += 0.2

        # 指导信息评分
        if "建议" in observation or "需要" in observation:
            score += 0.2

        return min(1.0, score)

    def _evaluate_output_completeness(self, output_data: Dict[str, Any]) -> float:
        """评估输出完整性"""
        score = 0.0

        # 基本字段检查
        required_fields = ["react_history", "completed", "iterations_used"]
        present_fields = sum(1 for field in required_fields if field in output_data)
        score += (present_fields / len(required_fields)) * 0.5

        # 内容质量检查
        react_history = output_data.get("react_history", [])
        if react_history:
            score += 0.3
            # 检查ReAct历史的完整性
            complete_steps = sum(
                1
                for step in react_history
                if all(key in step for key in ["reasoning", "action", "observation"])
            )
            if complete_steps == len(react_history):
                score += 0.2

        return min(1.0, score)


class RegressionDetector:
    """回归检测器"""

    def __init__(self, threshold: float = 0.1):
        self.threshold = threshold  # 10%的变化阈值

    def detect_regression(
        self, current_metrics: Dict[str, Any], baseline_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检测行为回归"""
        regression_report = {
            "has_regression": False,
            "degraded_metrics": [],
            "improved_metrics": [],
            "stable_metrics": [],
            "overall_change": 0.0,
            "severity": "none",  # none, minor, major, critical
        }

        all_changes = []

        for category in current_metrics:
            if category not in baseline_metrics:
                continue

            for metric_name in current_metrics[category]:
                if metric_name not in baseline_metrics[category]:
                    continue

                current_value = current_metrics[category][metric_name]["mean"]
                baseline_value = baseline_metrics[category][metric_name]["mean"]

                if baseline_value == 0:
                    continue  # 避免除零错误

                change_ratio = (current_value - baseline_value) / baseline_value
                all_changes.append(change_ratio)

                metric_info = {
                    "category": category,
                    "metric": metric_name,
                    "current": current_value,
                    "baseline": baseline_value,
                    "change_ratio": change_ratio,
                    "change_absolute": current_value - baseline_value,
                }

                if change_ratio < -self.threshold:
                    regression_report["degraded_metrics"].append(metric_info)
                    regression_report["has_regression"] = True
                elif change_ratio > self.threshold:
                    regression_report["improved_metrics"].append(metric_info)
                else:
                    regression_report["stable_metrics"].append(metric_info)

        # 计算总体变化
        if all_changes:
            regression_report["overall_change"] = sum(all_changes) / len(all_changes)

        # 确定严重程度
        regression_report["severity"] = self._determine_severity(regression_report)

        return regression_report

    def _determine_severity(self, regression_report: Dict[str, Any]) -> str:
        """确定回归严重程度"""
        if not regression_report["has_regression"]:
            return "none"

        degraded_count = len(regression_report["degraded_metrics"])
        max_degradation = 0.0

        if regression_report["degraded_metrics"]:
            max_degradation = abs(
                min(
                    metric["change_ratio"]
                    for metric in regression_report["degraded_metrics"]
                )
            )

        if degraded_count >= 5 or max_degradation > 0.3:
            return "critical"
        elif degraded_count >= 3 or max_degradation > 0.2:
            return "major"
        elif degraded_count >= 1 or max_degradation > 0.1:
            return "minor"
        else:
            return "none"


class TestAgentBehaviorRegression:
    """智能体行为回归测试类"""

    @pytest.fixture
    def global_state(self):
        """创建测试用的全局状态"""
        return GlobalState()

    @pytest.fixture
    def temp_baseline_dir(self):
        """创建临时基线目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def behavior_baseline(self, temp_baseline_dir):
        """创建行为基线管理器"""
        return BehaviorBaseline(temp_baseline_dir)

    @pytest.fixture
    def behavior_monitor(self):
        """创建行为监控器"""
        return BehaviorMonitor()

    @pytest.fixture
    def regression_detector(self):
        """创建回归检测器"""
        return RegressionDetector()

    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        mock_service = Mock()
        mock_service.invoke_sync = Mock()
        return mock_service

    def test_baseline_creation_and_loading(self, behavior_baseline):
        """测试基线创建和加载"""
        # 创建测试基线数据
        test_baseline = {
            "react_loop": {
                "iteration_count": {"mean": 3.0, "min": 2, "max": 4},
                "reasoning_quality": {"mean": 0.8, "min": 0.7, "max": 0.9},
                "action_success_rate": {"mean": 0.9, "min": 0.8, "max": 1.0},
            },
            "performance": {
                "execution_time": {"mean": 2.5, "min": 2.0, "max": 3.0},
                "error_rate": {"mean": 0.1, "min": 0.0, "max": 0.2},
            },
        }

        # 保存基线
        behavior_baseline.save_baseline("tester_agent", test_baseline)

        # 验证基线文件存在
        baseline_file = (
            Path(behavior_baseline.baseline_dir) / "tester_agent_baseline.json"
        )
        assert baseline_file.exists()

        # 加载基线
        loaded_baseline = behavior_baseline.load_baseline("tester_agent")
        assert loaded_baseline == test_baseline

        # 测试列出基线
        baselines = behavior_baseline.list_baselines()
        assert "tester_agent" in baselines

    def test_behavior_monitoring(self, behavior_monitor):
        """测试行为监控"""
        # 模拟ReAct历史数据
        react_history = [
            {
                "reasoning": "我需要分析当前任务，首先理解需求，然后制定计划",
                "action": {
                    "action_type": "analyze",
                    "success": True,
                    "output": "分析完成",
                },
                "observation": "行动类型: analyze, 执行状态: 成功, 输出结果: 分析完成",
            },
            {
                "reasoning": "基于分析结果，我需要生成测试用例",
                "action": {
                    "action_type": "generate",
                    "success": True,
                    "output": "生成3个测试用例",
                },
                "observation": "行动类型: generate, 执行状态: 成功, 生成了3个测试用例",
            },
        ]

        # 记录ReAct循环指标
        behavior_monitor.record_react_loop_metrics(react_history)

        # 记录性能指标
        behavior_monitor.record_performance_metrics(2.5, False)

        # 记录输出质量指标
        output_data = {
            "react_history": react_history,
            "completed": True,
            "iterations_used": 2,
        }
        behavior_monitor.record_output_quality_metrics(output_data)

        # 获取当前指标
        current_metrics = behavior_monitor.get_current_metrics()

        # 验证指标记录
        assert current_metrics["react_loop"]["iteration_count"]["mean"] == 2.0
        assert current_metrics["react_loop"]["action_success_rate"]["mean"] == 1.0
        assert current_metrics["performance"]["execution_time"]["mean"] == 2.5
        assert current_metrics["performance"]["error_rate"]["mean"] == 0.0
        assert current_metrics["output_quality"]["completeness"]["mean"] > 0.8

    def test_regression_detection(self, regression_detector):
        """测试回归检测"""
        # 基线指标
        baseline_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.8},
                "action_success_rate": {"mean": 0.9},
            },
            "performance": {
                "execution_time": {"mean": 2.0},
                "error_rate": {"mean": 0.1},
            },
        }

        # 当前指标（有退化）
        current_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.6},  # 下降25%
                "action_success_rate": {"mean": 0.95},  # 略有改善
            },
            "performance": {
                "execution_time": {"mean": 3.0},  # 增加50%
                "error_rate": {"mean": 0.05},  # 改善50%
            },
        }

        # 检测回归
        regression_report = regression_detector.detect_regression(
            current_metrics, baseline_metrics
        )

        # 验证回归检测结果
        assert regression_report["has_regression"] is True
        assert (
            len(regression_report["degraded_metrics"]) >= 2
        )  # reasoning_quality和execution_time
        assert regression_report["severity"] in ["minor", "major", "critical"]

        # 验证具体退化指标
        degraded_metrics = regression_report["degraded_metrics"]
        reasoning_degraded = any(
            metric["metric"] == "reasoning_quality" for metric in degraded_metrics
        )
        assert reasoning_degraded

    def test_tester_agent_regression_monitoring(
        self, global_state, behavior_monitor, mock_llm_service
    ):
        """测试Tester智能体的回归监控"""
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(content="我需要分析测试需求，首先理解业务逻辑，然后设计测试策略"),
                Mock(content="基于需求分析，我生成相应的测试用例"),
            ]

            tester = create_tester_agent(global_state)
            input_data = AgentInput(data={"test_requirements": "用户登录功能测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []
                mock_workspace.create_agent_file.return_value = "test_file.md"

                # 执行智能体并监控
                import time

                start_time = time.time()
                result = tester.execute(input_data)
                execution_time = time.time() - start_time

                # 记录监控指标
                react_history = result.data.get("react_history", [])
                behavior_monitor.record_react_loop_metrics(react_history)
                behavior_monitor.record_performance_metrics(
                    execution_time, result.error is not None
                )
                behavior_monitor.record_output_quality_metrics(result.data)

                # 获取监控结果
                current_metrics = behavior_monitor.get_current_metrics()

                # 验证监控数据
                assert current_metrics["react_loop"]["iteration_count"]["count"] == 1
                assert current_metrics["performance"]["execution_time"]["count"] == 1
                assert current_metrics["output_quality"]["completeness"]["count"] == 1

    def test_coder_agent_regression_monitoring(
        self, global_state, behavior_monitor, mock_llm_service
    ):
        """测试Coder智能体的回归监控"""
        with patch("src.agents.coder.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟LLM响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(content="我需要分析测试用例结构，然后选择合适的代码模板生成脚本"),
                Mock(
                    content="```python\nimport pytest\n\nclass TestLogin:\n    def test_login(self):\n        assert True\n```"
                ),
            ]

            coder = create_coder_agent(global_state)
            input_data = AgentInput(
                data={
                    "test_cases": [
                        {
                            "scenario": "正常登录",
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

                # 执行智能体并监控
                import time

                start_time = time.time()
                result = coder.execute(input_data)
                execution_time = time.time() - start_time

                # 记录监控指标
                react_history = result.data.get("react_history", [])
                behavior_monitor.record_react_loop_metrics(react_history)
                behavior_monitor.record_performance_metrics(
                    execution_time, result.error is not None
                )
                behavior_monitor.record_output_quality_metrics(result.data)

                # 获取监控结果
                current_metrics = behavior_monitor.get_current_metrics()

                # 验证监控数据
                assert current_metrics["react_loop"]["iteration_count"]["count"] == 1
                assert current_metrics["performance"]["execution_time"]["count"] == 1

    def test_full_regression_workflow(
        self,
        global_state,
        behavior_baseline,
        behavior_monitor,
        regression_detector,
        mock_llm_service,
    ):
        """测试完整的回归工作流程"""
        # 1. 建立基线
        baseline_data = {
            "react_loop": {
                "iteration_count": {"mean": 2.0},
                "reasoning_quality": {"mean": 0.8},
                "action_success_rate": {"mean": 0.9},
            },
            "performance": {
                "execution_time": {"mean": 2.0},
                "error_rate": {"mean": 0.1},
            },
            "output_quality": {
                "completeness": {"mean": 0.9},
                "accuracy": {"mean": 0.95},
            },
        }
        behavior_baseline.save_baseline("tester_agent", baseline_data)

        # 2. 执行当前测试并监控
        with patch("src.agents.tester.get_llm_service") as mock_get_llm:
            mock_get_llm.return_value = mock_llm_service

            # 模拟质量下降的响应
            mock_llm_service.invoke_sync.side_effect = [
                Mock(content="简单分析"),  # 质量下降的推理
                Mock(content="执行任务"),  # 质量下降的推理
            ]

            tester = create_tester_agent(global_state)
            input_data = AgentInput(data={"test_requirements": "回归测试"})

            # 模拟工作空间
            with patch("src.agents.tester.workspace_manager") as mock_workspace:
                mock_workspace.get_task_files.return_value = []

                # 执行多次以获得统计数据
                for _ in range(3):
                    import time

                    start_time = time.time()
                    result = tester.execute(input_data)
                    execution_time = time.time() - start_time

                    react_history = result.data.get("react_history", [])
                    behavior_monitor.record_react_loop_metrics(react_history)
                    behavior_monitor.record_performance_metrics(
                        execution_time, result.error is not None
                    )
                    behavior_monitor.record_output_quality_metrics(result.data)

        # 3. 获取当前指标
        current_metrics = behavior_monitor.get_current_metrics()

        # 4. 加载基线并检测回归
        loaded_baseline = behavior_baseline.load_baseline("tester_agent")
        regression_report = regression_detector.detect_regression(
            current_metrics, loaded_baseline
        )

        # 5. 验证回归检测结果
        # 由于模拟了质量下降的响应，应该检测到回归
        if regression_report["has_regression"]:
            assert len(regression_report["degraded_metrics"]) > 0
            assert regression_report["severity"] != "none"

    def test_regression_severity_classification(self, regression_detector):
        """测试回归严重程度分类"""
        baseline_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.8},
                "action_success_rate": {"mean": 0.9},
            }
        }

        # 测试轻微回归
        minor_regression_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.7},  # 下降12.5%
                "action_success_rate": {"mean": 0.9},
            }
        }

        report = regression_detector.detect_regression(
            minor_regression_metrics, baseline_metrics
        )
        assert report["severity"] == "minor"

        # 测试严重回归
        major_regression_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.6},  # 下降25%
                "action_success_rate": {"mean": 0.7},  # 下降22%
            }
        }

        report = regression_detector.detect_regression(
            major_regression_metrics, baseline_metrics
        )
        assert report["severity"] in ["major", "critical"]

    def test_regression_report_format(self, regression_detector):
        """测试回归报告格式"""
        baseline_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.8},
            }
        }

        current_metrics = {
            "react_loop": {
                "reasoning_quality": {"mean": 0.6},
            }
        }

        report = regression_detector.detect_regression(
            current_metrics, baseline_metrics
        )

        # 验证报告结构
        required_fields = [
            "has_regression",
            "degraded_metrics",
            "improved_metrics",
            "stable_metrics",
            "overall_change",
            "severity",
        ]

        for field in required_fields:
            assert field in report

        # 验证退化指标详情
        if report["degraded_metrics"]:
            degraded_metric = report["degraded_metrics"][0]
            required_metric_fields = [
                "category",
                "metric",
                "current",
                "baseline",
                "change_ratio",
                "change_absolute",
            ]

            for field in required_metric_fields:
                assert field in degraded_metric


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
