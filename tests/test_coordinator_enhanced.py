#!/usr/bin/env python3
"""
协调器节点增强功能测试
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.exceptions import TestAgentException
from src.graph.nodes import CoordinatorNode
from src.models.state import TaskType, TestAgentState


class TestCoordinatorEnhanced:
    """协调器节点增强功能测试类"""

    @pytest.fixture
    def coordinator(self):
        """创建协调器实例"""
        with patch("src.graph.nodes.LLMService") as mock_llm_service:
            mock_llm_service.return_value = Mock()
            coordinator = CoordinatorNode()
            coordinator.llm_service = mock_llm_service.return_value
            return coordinator

    @pytest.mark.asyncio
    async def test_conversation_context_update(self, coordinator):
        """测试对话上下文更新"""
        user_input = "请生成测试用例"
        coordinator._update_conversation_context(user_input)

        assert len(coordinator.conversation_context) == 1
        context = coordinator.conversation_context[0]
        assert context["user_input"] == user_input
        assert context["input_length"] == len(user_input)
        assert "测试" in context["contains_keywords"]

    @pytest.mark.asyncio
    async def test_conversation_context_limit(self, coordinator):
        """测试对话上下文长度限制"""
        # 添加超过限制的上下文
        for i in range(15):
            coordinator._update_conversation_context(f"测试输入 {i}")

        # 应该只保留最近10个
        assert len(coordinator.conversation_context) == 10
        assert coordinator.conversation_context[-1]["user_input"] == "测试输入 14"
        assert coordinator.conversation_context[0]["user_input"] == "测试输入 5"

    @pytest.mark.asyncio
    async def test_extract_keywords(self, coordinator):
        """测试关键词提取"""
        test_cases = [
            ("请生成测试用例", ["测试", "测试用例"]),
            ("write unit tests", ["unit test"]),
            ("需求分析和验证", ["需求分析", "验证"]),
            ("hello world", []),
        ]

        for text, expected_keywords in test_cases:
            keywords = coordinator._extract_keywords(text)
            for keyword in expected_keywords:
                assert keyword in keywords

    @pytest.mark.asyncio
    async def test_language_detection_with_context(self, coordinator):
        """测试基于上下文的语言检测"""
        # 先建立中文上下文
        for i in range(3):
            coordinator._update_conversation_context(f"请生成测试用例 {i}")

        # 测试短文本的语言检测
        locale = coordinator._detect_language_with_context("继续")
        assert locale == "zh-CN"  # 应该基于上下文判断为中文

    @pytest.mark.asyncio
    async def test_user_preferences_learning(self, coordinator):
        """测试用户偏好学习"""
        user_input = "请生成测试脚本"
        locale = "zh-CN"

        coordinator._learn_user_preferences(user_input, locale)

        assert coordinator.user_preferences["preferred_language"] == "zh-CN"
        assert "task_type_history" in coordinator.user_preferences
        assert (
            TaskType.TEST_SCRIPT_GENERATION.value
            in coordinator.user_preferences["task_type_history"]
        )
        assert "expression_patterns" in coordinator.user_preferences

    @pytest.mark.asyncio
    async def test_formal_language_detection(self, coordinator):
        """测试正式语言检测"""
        formal_input = "请您帮我生成测试用例，谢谢"
        coordinator._learn_user_preferences(formal_input, "zh-CN")

        assert (
            coordinator.user_preferences["expression_patterns"]["uses_formal_language"]
            is True
        )

    @pytest.mark.asyncio
    async def test_enhanced_test_related_with_context(self, coordinator):
        """测试基于上下文的增强测试相关性判断"""
        # 建立测试相关的上下文
        coordinator._update_conversation_context("请生成测试用例")
        coordinator._update_conversation_context("需要单元测试")
        coordinator._update_conversation_context("还要集成测试")

        # 测试延续性表达
        with patch.object(
            coordinator, "_is_test_related", new_callable=AsyncMock
        ) as mock_basic:
            mock_basic.return_value = False  # 基础判断为非测试相关

            result = await coordinator._is_test_related_enhanced("还有其他的吗")
            assert result is True  # 应该基于上下文判断为测试相关

    @pytest.mark.asyncio
    async def test_enhanced_test_related_with_history(self, coordinator):
        """测试基于历史偏好的测试相关性判断"""
        # 建立任务类型历史
        coordinator.user_preferences["task_type_history"] = [
            "test_case_generation",
            "test_case_generation",
            "test_script_generation",
        ]

        with patch.object(
            coordinator, "_is_test_related", new_callable=AsyncMock
        ) as mock_basic:
            mock_basic.return_value = False

            result = await coordinator._is_test_related_enhanced("这个系统功能")
            assert result is True  # 应该基于历史偏好判断为测试相关

    @pytest.mark.asyncio
    async def test_enhanced_task_info_extraction(self, coordinator):
        """测试增强版任务信息提取"""
        # 设置用户偏好
        coordinator.user_preferences["task_type_history"] = [
            "test_script_generation",
            "test_script_generation",
            "test_script_generation",
        ]

        with patch.object(
            coordinator, "_extract_task_info", new_callable=AsyncMock
        ) as mock_basic:
            mock_basic.return_value = {
                "topic": "测试任务",
                "task_type": TaskType.TEST_CASE_GENERATION,
            }

            result = await coordinator._extract_task_info_enhanced("生成代码", "zh-CN")

            # 应该基于用户偏好调整任务类型
            assert result["task_type"] == TaskType.TEST_SCRIPT_GENERATION

    @pytest.mark.asyncio
    async def test_context_summary_generation(self, coordinator):
        """测试上下文摘要生成"""
        # 设置用户偏好和对话上下文
        coordinator.user_preferences = {
            "preferred_language": "zh-CN",
            "task_type_history": ["test_case_generation", "test_case_generation"],
        }

        coordinator._update_conversation_context("请生成测试用例")
        coordinator._update_conversation_context("需要单元测试")

        summary = coordinator._get_context_summary()

        assert "用户偏好：中文交流" in summary
        assert "常用任务类型：test_case_generation" in summary
        assert "相关关键词" in summary

    @pytest.mark.asyncio
    async def test_enhanced_process_with_workflow_tools(self, coordinator):
        """测试增强版处理流程与工作流工具集成"""
        state = TestAgentState(
            messages=[HumanMessage(content="请为登录功能生成测试用例")],
            locale="",
            task_topic="",
            task_type=None,
            plan_iterations=0,
            current_plan=None,
            observations=[],
            resources=[],
            rag_results=[],
            final_report="",
            review_score=None,
            auto_accepted_plan=False,
            enable_rag_search=True,
            enable_human_feedback=True,
        )

        # Mock工具管理器
        with patch("src.graph.nodes.get_tool_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.is_initialized.return_value = True
            mock_manager.execute_tool = AsyncMock(
                return_value={"success": True, "message": "任务已移交给规划器"}
            )
            mock_get_manager.return_value = mock_manager

            with patch.object(
                coordinator, "_is_test_related_enhanced", new_callable=AsyncMock
            ) as mock_test_related:
                mock_test_related.return_value = True

                with patch.object(
                    coordinator, "_extract_task_info_enhanced", new_callable=AsyncMock
                ) as mock_extract:
                    mock_extract.return_value = {
                        "topic": "登录功能测试用例生成",
                        "task_type": TaskType.TEST_CASE_GENERATION,
                    }

                    result = await coordinator.process(state)

                    assert result["locale"] == "zh-CN"
                    assert result["task_topic"] == "登录功能测试用例生成"
                    assert result["task_type"] == TaskType.TEST_CASE_GENERATION
                    assert result["next_node"] == "planner"
                    assert len(result["messages"]) == 2  # 原消息 + 移交消息

    @pytest.mark.asyncio
    async def test_context_enriched_topic(self, coordinator):
        """测试基于上下文丰富任务主题"""
        # 建立包含关键词的上下文
        coordinator._update_conversation_context("需要单元测试和集成测试")

        with patch.object(
            coordinator, "_extract_task_info", new_callable=AsyncMock
        ) as mock_basic:
            mock_basic.return_value = {
                "topic": "测试任务",
                "task_type": TaskType.TEST_CASE_GENERATION,
            }

            result = await coordinator._extract_task_info_enhanced("继续", "zh-CN")

            # 任务主题应该被丰富
            assert "相关:" in result["topic"]
            assert "单元测试" in result["topic"] or "集成测试" in result["topic"]

    @pytest.mark.asyncio
    async def test_average_input_length_calculation(self, coordinator):
        """测试平均输入长度计算（滑动平均）"""
        inputs = [
            "短",
            "这是一个中等长度的输入",
            "这是一个非常非常长的输入文本，用来测试平均长度的计算",
        ]

        # 使用滑动平均算法计算期望值
        expected_avg = 0
        for input_text in inputs:
            coordinator._learn_user_preferences(input_text, "zh-CN")
            if expected_avg == 0:
                expected_avg = len(input_text)
            else:
                expected_avg = expected_avg * 0.8 + len(input_text) * 0.2

        actual_avg = coordinator.user_preferences["expression_patterns"][
            "avg_input_length"
        ]

        assert abs(actual_avg - expected_avg) < 0.1  # 允许小的浮点误差


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
