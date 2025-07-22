#!/usr/bin/env python3
"""
协调器节点测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.state import TestAgentState, TaskType
from src.graph.nodes import CoordinatorNode
from src.exceptions import TestAgentException


class TestCoordinatorNode:
    """协调器节点测试类"""
    
    @pytest.fixture
    def coordinator(self):
        """创建协调器实例"""
        with patch('src.graph.nodes.LLMService') as mock_llm_service:
            mock_llm_service.return_value = Mock()
            coordinator = CoordinatorNode()
            coordinator.llm_service = mock_llm_service.return_value
            return coordinator
    
    @pytest.fixture
    def mock_state(self):
        """创建模拟状态"""
        state = TestAgentState(
            messages=[HumanMessage(content="请为用户登录功能生成测试用例")],
            locale="zh-CN",
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
            enable_human_feedback=True
        )
        return state
    
    @pytest.mark.asyncio
    async def test_detect_language_chinese(self, coordinator):
        """测试中文语言检测"""
        chinese_text = "请为用户登录功能生成测试用例"
        locale = coordinator._detect_language(chinese_text)
        assert locale == "zh-CN"
    
    @pytest.mark.asyncio
    async def test_detect_language_english(self, coordinator):
        """测试英文语言检测"""
        english_text = "Please generate test cases for user login functionality"
        locale = coordinator._detect_language(english_text)
        assert locale == "en-US"
    
    @pytest.mark.asyncio
    async def test_detect_language_mixed(self, coordinator):
        """测试中英文混合文本"""
        mixed_text = "Please generate 测试用例 for login"
        locale = coordinator._detect_language(mixed_text)
        # 中文字符比例不足30%，应该识别为英文
        assert locale == "en-US"
    
    @pytest.mark.asyncio
    async def test_is_test_related_keywords_chinese(self, coordinator):
        """测试中文测试相关关键词识别"""
        test_inputs = [
            "请生成测试用例",
            "编写单元测试",
            "需要自动化测试脚本",
            "分析需求文档"
        ]
        
        for input_text in test_inputs:
            with patch.object(coordinator.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "是"
                result = await coordinator._is_test_related(input_text)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_is_test_related_keywords_english(self, coordinator):
        """测试英文测试相关关键词识别"""
        test_inputs = [
            "generate test cases",
            "write unit tests", 
            "automated testing script",
            "qa validation"
        ]
        
        for input_text in test_inputs:
            with patch.object(coordinator.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "yes"
                result = await coordinator._is_test_related(input_text)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_is_test_related_non_test(self, coordinator):
        """测试非测试相关内容识别"""
        non_test_inputs = [
            "你好",
            "今天天气怎么样",
            "hello world",
            "how are you"
        ]
        
        for input_text in non_test_inputs:
            with patch.object(coordinator.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "否"
                result = await coordinator._is_test_related(input_text)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_extract_task_info_test_case_generation(self, coordinator):
        """测试提取测试用例生成任务信息"""
        user_input = "请为用户登录功能生成测试用例"
        locale = "zh-CN"
        
        mock_response = '''
        {
            "topic": "用户登录功能测试用例生成",
            "task_type": "test_case_generation"
        }
        '''
        
        with patch.object(coordinator.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            result = await coordinator._extract_task_info(user_input, locale)
            
            assert result["topic"] == "用户登录功能测试用例生成"
            assert result["task_type"] == TaskType.TEST_CASE_GENERATION
    
    @pytest.mark.asyncio
    async def test_extract_task_info_invalid_json(self, coordinator):
        """测试无效JSON响应的处理"""
        user_input = "生成测试脚本"
        locale = "zh-CN"
        
        with patch.object(coordinator.llm_service, 'generate_response', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "无效的JSON响应"
            result = await coordinator._extract_task_info(user_input, locale)
            
            # 应该返回基于关键词分析的结果
            assert "topic" in result
            assert result["task_type"] == TaskType.TEST_SCRIPT_GENERATION  # "生成测试脚本"应该被识别为脚本生成
    
    @pytest.mark.asyncio
    async def test_generate_simple_response_greeting_chinese(self, coordinator):
        """测试中文问候语回复"""
        response = coordinator._generate_simple_response("你好", "zh-CN")
        assert "你好" in response
        assert "TestAgent" in response
        assert "测试" in response
    
    @pytest.mark.asyncio
    async def test_generate_simple_response_greeting_english(self, coordinator):
        """测试英文问候语回复"""
        response = coordinator._generate_simple_response("hello", "en-US")
        assert "Hello" in response
        assert "TestAgent" in response
        assert "testing" in response
    
    @pytest.mark.asyncio
    async def test_generate_simple_response_non_test_chinese(self, coordinator):
        """测试中文非测试相关回复"""
        response = coordinator._generate_simple_response("今天天气怎么样", "zh-CN")
        assert "抱歉" in response
        assert "TestAgent" in response
        assert "测试" in response
    
    @pytest.mark.asyncio
    async def test_generate_simple_response_non_test_english(self, coordinator):
        """测试英文非测试相关回复"""
        response = coordinator._generate_simple_response("What's the weather like", "en-US")
        assert "Sorry" in response
        assert "TestAgent" in response
        assert "testing" in response
    
    @pytest.mark.asyncio
    async def test_process_test_related_input(self, coordinator, mock_state):
        """测试处理测试相关输入"""
        with patch.object(coordinator, '_is_test_related', new_callable=AsyncMock) as mock_is_test:
            mock_is_test.return_value = True
            
            with patch.object(coordinator, '_extract_task_info', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "topic": "用户登录功能测试",
                    "task_type": TaskType.TEST_CASE_GENERATION
                }
                
                result = await coordinator.process(mock_state)
                
                assert result["locale"] == "zh-CN"
                assert result["task_topic"] == "用户登录功能测试"
                assert result["task_type"] == TaskType.TEST_CASE_GENERATION
    
    @pytest.mark.asyncio
    async def test_process_non_test_related_input(self, coordinator, mock_state):
        """测试处理非测试相关输入"""
        # 修改状态中的消息
        mock_state["messages"] = [HumanMessage(content="你好")]
        
        with patch.object(coordinator, '_is_test_related', new_callable=AsyncMock) as mock_is_test:
            mock_is_test.return_value = False
            
            result = await coordinator.process(mock_state)
            
            assert "final_report" in result
            assert len(result["messages"]) == 2  # 原消息 + AI回复
            assert isinstance(result["messages"][-1], AIMessage)
    
    @pytest.mark.asyncio
    async def test_process_no_messages(self, coordinator):
        """测试没有消息的情况"""
        state = TestAgentState(
            messages=[],
            locale="zh-CN",
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
            enable_human_feedback=True
        )
        
        result = await coordinator.process(state)
        
        # 应该返回错误响应
        assert "final_report" in result
        assert "错误" in result["final_report"] or "Error" in result["final_report"]
    
    @pytest.mark.asyncio
    async def test_process_invalid_message_type(self, coordinator):
        """测试无效消息类型"""
        state = TestAgentState(
            messages=[AIMessage(content="这是AI消息，不是用户消息")],
            locale="zh-CN",
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
            enable_human_feedback=True
        )
        
        result = await coordinator.process(state)
        
        # 应该返回错误响应
        assert "final_report" in result
        assert "错误" in result["final_report"] or "Error" in result["final_report"]
    
    @pytest.mark.asyncio
    async def test_generate_error_response_chinese(self, coordinator):
        """测试中文错误响应生成"""
        error_msg = "测试错误"
        response = coordinator._generate_error_response(error_msg, "zh-CN")
        
        assert "抱歉" in response
        assert error_msg in response
        assert "重试" in response
    
    @pytest.mark.asyncio
    async def test_generate_error_response_english(self, coordinator):
        """测试英文错误响应生成"""
        error_msg = "Test error"
        response = coordinator._generate_error_response(error_msg, "en-US")
        
        assert "Sorry" in response
        assert error_msg in response
        assert "try again" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])