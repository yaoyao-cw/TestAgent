"""LLM服务测试"""

import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.llm.config import LLMConfig, LLMProviderConfig, AgentLLMMapping
from src.llm.factory import LLMFactory, get_llm_factory, get_llm_by_type
from src.llm.service import LLMService, get_llm_service, invoke_llm
from src.models.types import LLMType, AgentType
from src.exceptions import LLMServiceException


class TestLLMConfig:
    """LLM配置测试"""
    
    def test_create_llm_config(self):
        """测试创建LLM配置"""
        config = LLMConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            temperature=0.7,
            api_key="test-key"
        )
        
        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.7
        assert config.api_key == "test-key"
        assert config.timeout == 30  # 默认值
        assert config.max_retries == 3  # 默认值
    
    def test_llm_config_validation(self):
        """测试LLM配置验证"""
        # 测试温度范围验证
        with pytest.raises(ValueError):
            LLMConfig(
                provider="openai",
                model="gpt-3.5-turbo",
                temperature=3.0  # 超出范围
            )
        
        # 测试负数超时
        with pytest.raises(ValueError):
            LLMConfig(
                provider="openai",
                model="gpt-3.5-turbo",
                timeout=-1
            )


class TestLLMProviderConfig:
    """LLM提供商配置测试"""
    
    def test_provider_config(self):
        """测试提供商配置"""
        basic_config = LLMConfig(provider="openai", model="gpt-3.5-turbo")
        advanced_config = LLMConfig(provider="openai", model="gpt-4")
        reasoning_config = LLMConfig(provider="openai", model="o1-preview")
        
        provider_config = LLMProviderConfig(
            basic=basic_config,
            advanced=advanced_config,
            reasoning=reasoning_config
        )
        
        assert provider_config.get_config_by_type(LLMType.BASIC) == basic_config
        assert provider_config.get_config_by_type(LLMType.ADVANCED) == advanced_config
        assert provider_config.get_config_by_type(LLMType.REASONING) == reasoning_config


class TestAgentLLMMapping:
    """智能体LLM映射测试"""
    
    def test_agent_mapping(self):
        """测试智能体映射"""
        mapping = AgentLLMMapping()
        
        assert mapping.get_llm_type_for_agent(AgentType.COORDINATOR) == LLMType.BASIC
        assert mapping.get_llm_type_for_agent(AgentType.PLANNER) == LLMType.ADVANCED
        assert mapping.get_llm_type_for_agent(AgentType.RESEARCHER) == LLMType.ADVANCED
    
    def test_custom_mapping(self):
        """测试自定义映射"""
        mapping = AgentLLMMapping(
            coordinator=LLMType.ADVANCED,
            planner=LLMType.REASONING
        )
        
        assert mapping.get_llm_type_for_agent(AgentType.COORDINATOR) == LLMType.ADVANCED
        assert mapping.get_llm_type_for_agent(AgentType.PLANNER) == LLMType.REASONING


class TestLLMFactory:
    """LLM工厂测试"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_factory(self):
        """测试创建工厂"""
        factory = LLMFactory()
        assert factory is not None
        assert factory.provider_config is not None
        assert factory.agent_mapping is not None
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    def test_create_llm(self, mock_chat_openai):
        """测试创建LLM"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        factory = LLMFactory()
        llm = factory.create_llm(LLMType.BASIC)
        
        assert llm == mock_llm
        mock_chat_openai.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    def test_llm_caching(self, mock_chat_openai):
        """测试LLM缓存"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        factory = LLMFactory()
        
        # 第一次调用
        llm1 = factory.create_llm(LLMType.BASIC)
        # 第二次调用应该使用缓存
        llm2 = factory.create_llm(LLMType.BASIC)
        
        assert llm1 == llm2
        # ChatOpenAI应该只被调用一次
        mock_chat_openai.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    def test_get_llm_for_agent(self, mock_chat_openai):
        """测试为智能体获取LLM"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        factory = LLMFactory()
        llm = factory.get_llm_for_agent(AgentType.COORDINATOR)
        
        assert llm == mock_llm


class TestLLMService:
    """LLM服务测试"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_service(self):
        """测试创建服务"""
        service = LLMService()
        assert service is not None
        assert service.factory is not None
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    def test_format_messages(self, mock_chat_openai):
        """测试消息格式化"""
        service = LLMService()
        
        # 测试字典格式消息
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        formatted = service._format_messages(messages)
        
        assert len(formatted) == 3
        assert isinstance(formatted[0], SystemMessage)
        assert isinstance(formatted[1], HumanMessage)
        assert isinstance(formatted[2], AIMessage)
        assert formatted[0].content == "You are a helpful assistant"
        assert formatted[1].content == "Hello"
        assert formatted[2].content == "Hi there!"
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_invoke_async(self, mock_chat_openai):
        """测试异步调用"""
        mock_llm = MagicMock()
        mock_response = AIMessage(content="Test response")
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_openai.return_value = mock_llm
        
        service = LLMService()
        messages = [{"role": "user", "content": "Hello"}]
        
        response = await service.invoke_async(messages, LLMType.BASIC)
        
        assert response == mock_response
        assert service._call_count == 1
        mock_llm.ainvoke.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    def test_invoke_sync(self, mock_chat_openai):
        """测试同步调用"""
        mock_llm = MagicMock()
        mock_response = AIMessage(content="Test response")
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm
        
        service = LLMService()
        messages = [{"role": "user", "content": "Hello"}]
        
        response = service.invoke_sync(messages, LLMType.BASIC)
        
        assert response.content == mock_response.content
        assert service._call_count == 1
        mock_llm.invoke.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_invoke_for_agent(self, mock_chat_openai):
        """测试为智能体调用"""
        mock_llm = MagicMock()
        mock_response = AIMessage(content="Test response")
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_openai.return_value = mock_llm
        
        service = LLMService()
        messages = [{"role": "user", "content": "Hello"}]
        
        response = await service.invoke_for_agent(messages, AgentType.COORDINATOR)
        
        assert response == mock_response
        mock_llm.ainvoke.assert_called_once()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('src.llm.factory.ChatOpenAI')
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_chat_openai):
        """测试错误处理"""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
        mock_chat_openai.return_value = mock_llm
        
        service = LLMService()
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LLMServiceException):
            await service.invoke_async(messages, LLMType.BASIC)
        
        assert service._error_count == 1
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_statistics(self):
        """测试统计信息"""
        service = LLMService()
        
        # 初始统计
        stats = service.get_statistics()
        assert stats["total_calls"] == 0
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 0.0
        
        # 模拟调用
        service._call_count = 10
        service._error_count = 2
        
        stats = service.get_statistics()
        assert stats["total_calls"] == 10
        assert stats["error_count"] == 2
        assert stats["success_rate"] == 0.8
        
        # 重置统计
        service.reset_statistics()
        stats = service.get_statistics()
        assert stats["total_calls"] == 0
        assert stats["error_count"] == 0


class TestGlobalFunctions:
    """全局函数测试"""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_get_llm_factory(self):
        """测试获取LLM工厂"""
        factory1 = get_llm_factory()
        factory2 = get_llm_factory()
        
        # 应该返回同一个实例（单例）
        assert factory1 is factory2
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_get_llm_service(self):
        """测试获取LLM服务"""
        service1 = get_llm_service()
        service2 = get_llm_service()
        
        # 应该返回同一个实例（单例）
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__])