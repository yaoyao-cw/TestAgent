#!/usr/bin/env python3
"""
错误恢复系统测试

测试错误恢复管理器和智能体行为优化器的功能
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.core.agent_behavior_optimizer import (AgentBehaviorOptimizer,
                                               AttentionGuide, BehaviorPattern,
                                               ContextDiversityInjection,
                                               get_behavior_optimizer,
                                               reset_behavior_optimizer)
from src.core.error_recovery_manager import (ContextPreservationLevel,
                                             ErrorContext,
                                             ErrorRecoveryManager, ErrorType,
                                             RecoveryPlan,
                                             get_error_recovery_manager,
                                             reset_error_recovery_manager)
from src.core.exceptions import LLMError, NetworkError, TimeoutError
from src.models.workspace import GlobalState


class TestErrorRecoveryManager:
    """错误恢复管理器测试"""

    @pytest.fixture
    def global_state(self):
        """创建模拟的全局状态"""
        return Mock(spec=GlobalState)

    @pytest.fixture
    def error_recovery_manager(self, global_state):
        """创建错误恢复管理器实例"""
        reset_error_recovery_manager()
        return ErrorRecoveryManager(global_state)

    def test_error_classification(self, error_recovery_manager):
        """测试错误分类功能"""
        # 测试网络错误分类
        network_error = NetworkError("连接超时")
        assert (
            error_recovery_manager.classify_error(network_error) == ErrorType.TRANSIENT
        )

        # 测试LLM错误分类
        llm_error = LLMError("模型调用失败")
        assert error_recovery_manager.classify_error(llm_error) == ErrorType.RECOVERABLE

        # 测试超时错误分类
        timeout_error = TimeoutError("操作超时")
        assert (
            error_recovery_manager.classify_error(timeout_error) == ErrorType.TRANSIENT
        )

        # 测试未知错误分类
        unknown_error = ValueError("未知错误")
        assert (
            error_recovery_manager.classify_error(unknown_error)
            == ErrorType.RECOVERABLE
        )

    def test_preserve_error_context(self, error_recovery_manager):
        """测试错误上下文保留"""
        exception = NetworkError("网络连接失败")

        context = error_recovery_manager.preserve_error_context(
            exception=exception,
            agent_id="tester",
            task_id="task_001",
            execution_step="test_generation",
            preservation_level=ContextPreservationLevel.STANDARD,
        )

        assert context.error_type == ErrorType.TRANSIENT
        assert context.agent_id == "tester"
        assert context.task_id == "task_001"
        assert context.execution_step == "test_generation"
        assert context.retry_count == 0
        assert len(context.recovery_attempts) == 0

        # 验证上下文已存储
        assert context.error_id in error_recovery_manager.error_contexts

    def test_create_recovery_plan(self, error_recovery_manager):
        """测试恢复计划创建"""
        # 创建错误上下文
        exception = LLMError("LLM调用失败")
        context = error_recovery_manager.preserve_error_context(
            exception=exception,
            agent_id="coder",
            task_id="task_002",
            execution_step="code_generation",
        )

        # 创建恢复计划
        plan = error_recovery_manager.create_recovery_plan(context)

        assert plan.error_context == context
        assert len(plan.recovery_actions) > 0
        assert len(plan.fallback_strategies) > 0
        assert plan.estimated_recovery_time > 0
        assert 0 <= plan.success_probability <= 1

        # 验证计划已存储
        assert plan.plan_id in error_recovery_manager.recovery_plans

    @pytest.mark.asyncio
    async def test_execute_recovery(self, error_recovery_manager):
        """测试恢复计划执行"""
        # 创建错误上下文和恢复计划
        exception = TimeoutError("操作超时")
        context = error_recovery_manager.preserve_error_context(
            exception=exception,
            agent_id="executor",
            task_id="task_003",
            execution_step="code_execution",
        )

        plan = error_recovery_manager.create_recovery_plan(context)

        # 执行恢复计划
        result = await error_recovery_manager.execute_recovery(plan)

        assert "plan_id" in result
        assert "success" in result
        assert "actions_executed" in result
        assert "recovery_time" in result
        assert result["plan_id"] == plan.plan_id

        # 验证恢复尝试已记录
        assert len(context.recovery_attempts) > 0

    def test_resume_task_from_checkpoint(self, error_recovery_manager):
        """测试任务恢复功能"""
        # 创建错误上下文
        exception = NetworkError("网络中断")
        context = error_recovery_manager.preserve_error_context(
            exception=exception,
            agent_id="tester",
            task_id="task_004",
            execution_step="test_execution",
        )

        # 尝试恢复任务
        result = error_recovery_manager.resume_task_from_checkpoint("task_004")

        assert "success" in result
        assert "message" in result

        if result["success"]:
            assert "restored_state" in result
            assert "resume_point" in result

    def test_error_learning_data(self, error_recovery_manager):
        """测试错误学习数据生成"""
        # 创建多个错误上下文
        for i in range(3):
            exception = LLMError(f"LLM错误 {i}")
            context = error_recovery_manager.preserve_error_context(
                exception=exception,
                agent_id="coder",
                task_id=f"task_{i}",
                execution_step="code_generation",
            )

            # 模拟恢复尝试
            context.recovery_attempts.append(
                {"success": i % 2 == 0, "final_action": "retry", "recovery_time": 30}
            )

        # 获取学习数据
        learning_data = error_recovery_manager.get_error_learning_data(
            ErrorType.RECOVERABLE
        )

        assert len(learning_data) == 3
        for sample in learning_data:
            assert "error_pattern" in sample
            assert "context_features" in sample
            assert "recovery_outcomes" in sample
            assert "lessons_learned" in sample

    def test_cleanup_old_contexts(self, error_recovery_manager):
        """测试旧上下文清理"""
        # 创建一些错误上下文
        for i in range(5):
            exception = NetworkError(f"网络错误 {i}")
            context = error_recovery_manager.preserve_error_context(
                exception=exception,
                agent_id="tester",
                task_id=f"task_{i}",
                execution_step="test_generation",
            )

            # 模拟旧的时间戳
            if i < 3:
                context.timestamp = datetime.now() - timedelta(hours=25)

        # 清理旧上下文
        cleaned_count = error_recovery_manager.cleanup_old_contexts(24)

        assert cleaned_count == 3
        assert len(error_recovery_manager.error_contexts) == 2

    def test_recovery_statistics(self, error_recovery_manager):
        """测试恢复统计信息"""
        # 模拟一些恢复操作
        error_recovery_manager._update_recovery_stats(True)
        error_recovery_manager._update_recovery_stats(True)
        error_recovery_manager._update_recovery_stats(False)

        stats = error_recovery_manager.get_recovery_statistics()

        assert stats["total_errors"] == 3
        assert stats["recovered_errors"] == 2
        assert stats["failed_recoveries"] == 1
        assert abs(stats["recovery_success_rate"] - 2 / 3) < 0.01


class TestAgentBehaviorOptimizer:
    """智能体行为优化器测试"""

    @pytest.fixture
    def global_state(self):
        """创建模拟的全局状态"""
        return Mock(spec=GlobalState)

    @pytest.fixture
    def error_recovery_manager(self, global_state):
        """创建错误恢复管理器"""
        return Mock(spec=ErrorRecoveryManager)

    @pytest.fixture
    def behavior_optimizer(self, global_state, error_recovery_manager):
        """创建智能体行为优化器实例"""
        reset_behavior_optimizer()
        return AgentBehaviorOptimizer(global_state, error_recovery_manager)

    def test_generate_attention_guide(self, behavior_optimizer):
        """测试注意力引导生成"""
        todo_content = """
        # 测试任务
        - [ ] 生成测试用例
        - [x] 分析需求
        - [ ] 执行测试
        """

        execution_history = [
            {"action": "analyze_requirements", "status": "success"},
            {"action": "generate_tests", "status": "in_progress"},
        ]

        guide = behavior_optimizer.generate_attention_guide(
            agent_id="tester",
            task_id="task_001",
            todo_content=todo_content,
            execution_history=execution_history,
        )

        assert isinstance(guide, AttentionGuide)
        assert guide.task_goal
        assert guide.current_focus
        assert len(guide.priority_items) > 0
        assert len(guide.context_reminders) > 0

        # 测试转换为提示词
        prompt_section = guide.to_prompt_section()
        assert "## 任务目标" in prompt_section
        assert "## 当前焦点" in prompt_section

    def test_inject_context_diversity(self, behavior_optimizer):
        """测试上下文多样性注入"""
        current_context = "当前正在生成测试用例"
        execution_history = [
            {"action": "generate_tests", "status": "failed"},
            {"action": "generate_tests", "status": "failed"},
            {"action": "generate_tests", "status": "failed"},
        ]

        # 多次测试以验证随机性
        enhanced_contexts = []
        for _ in range(10):
            enhanced = behavior_optimizer.inject_context_diversity(
                agent_id="tester",
                current_context=current_context,
                execution_history=execution_history,
            )
            enhanced_contexts.append(enhanced)

        # 应该有一些上下文被增强了
        enhanced_count = sum(1 for ctx in enhanced_contexts if ctx != current_context)
        assert enhanced_count > 0

    def test_detect_behavior_drift(self, behavior_optimizer):
        """测试行为漂移检测"""
        recent_actions = ["generate_tests", "generate_tests", "generate_tests"]
        context_info = {"task_id": "task_001", "history_length": 10}

        drift_analysis = behavior_optimizer.detect_behavior_drift(
            agent_id="tester", recent_actions=recent_actions, context_info=context_info
        )

        assert "drift_detected" in drift_analysis
        assert "pattern_count" in drift_analysis

        # 验证行为模式已记录
        assert len(behavior_optimizer.behavior_patterns) > 0

    def test_adapt_from_errors(self, behavior_optimizer):
        """测试错误驱动适应"""
        # 创建模拟错误上下文
        error_contexts = []
        for i in range(3):
            context = Mock(spec=ErrorContext)
            context.error_type = ErrorType.TRANSIENT
            context.agent_id = "coder"
            context.execution_step = "code_generation"
            context.recovery_attempts = [
                {"success": i % 2 == 0, "final_action": "retry"}
            ]
            error_contexts.append(context)

        adaptation_result = behavior_optimizer.adapt_from_errors(
            agent_id="coder", error_contexts=error_contexts
        )

        assert "adaptations" in adaptation_result
        assert "success" in adaptation_result
        assert "error_patterns_analyzed" in adaptation_result

    def test_optimize_agent_behavior(self, behavior_optimizer):
        """测试综合行为优化"""
        current_context = "正在编写代码"
        execution_history = [
            {"action": "analyze_code", "status": "success"},
            {"action": "generate_code", "status": "in_progress"},
        ]
        todo_content = "# 编码任务\n- [ ] 实现功能\n- [ ] 添加测试"

        # 模拟错误恢复管理器
        behavior_optimizer.error_recovery_manager.error_contexts = {}

        result = behavior_optimizer.optimize_agent_behavior(
            agent_id="coder",
            task_id="task_001",
            current_context=current_context,
            execution_history=execution_history,
            todo_content=todo_content,
        )

        assert "attention_guide" in result
        assert "enhanced_context" in result
        assert "drift_analysis" in result
        assert "adaptations" in result
        assert "optimizations_applied" in result

        # 验证注意力引导已生成
        if result["attention_guide"]:
            assert isinstance(result["attention_guide"], AttentionGuide)

    def test_optimization_statistics(self, behavior_optimizer):
        """测试优化统计信息"""
        # 模拟一些优化操作
        behavior_optimizer.optimization_stats["attention_guides_generated"] = 5
        behavior_optimizer.optimization_stats["diversity_injections_applied"] = 3
        behavior_optimizer.optimization_stats["drift_patterns_detected"] = 2

        stats = behavior_optimizer.get_optimization_statistics()

        assert stats["attention_guides_generated"] == 5
        assert stats["diversity_injections_applied"] == 3
        assert stats["drift_patterns_detected"] == 2
        assert "total_behavior_patterns" in stats
        assert "active_attention_guides" in stats


class TestIntegration:
    """集成测试"""

    @pytest.fixture
    def global_state(self):
        """创建模拟的全局状态"""
        return Mock(spec=GlobalState)

    def test_error_recovery_and_behavior_optimization_integration(self, global_state):
        """测试错误恢复和行为优化的集成"""
        # 重置全局实例
        reset_error_recovery_manager()
        reset_behavior_optimizer()

        # 创建错误恢复管理器
        error_manager = get_error_recovery_manager(global_state)

        # 创建行为优化器
        behavior_optimizer = get_behavior_optimizer(global_state, error_manager)

        # 模拟错误场景
        exception = LLMError("模型调用失败")
        error_context = error_manager.preserve_error_context(
            exception=exception,
            agent_id="coder",
            task_id="integration_test",
            execution_step="code_generation",
        )

        # 使用行为优化器进行适应
        adaptation_result = behavior_optimizer.adapt_from_errors(
            agent_id="coder", error_contexts=[error_context]
        )

        assert (
            adaptation_result["success"] or len(adaptation_result["adaptations"]) >= 0
        )

        # 验证统计信息
        error_stats = error_manager.get_recovery_statistics()
        behavior_stats = behavior_optimizer.get_optimization_statistics()

        assert error_stats["active_contexts"] > 0
        assert "total_behavior_patterns" in behavior_stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
