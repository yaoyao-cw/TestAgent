"""LLM提供商支持测试"""

import pytest
import os
from unittest.mock import patch, MagicMock

from src.llm.providers import (
    LLMProvider,
    ModelInfo,
    get_model_info,
    get_models_by_provider,
    get_recommended_models,
    validate_model_config,
)
from src.llm.factory import LLMFactory
from src.llm.config import LLMConfig
from src.models.types import LLMType


class TestLLMProviders:
    """LLM提供商测试"""

    def test_llm_provider_enum(self):
        """测试LLM提供商枚举"""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.GOOGLE.value == "google"
        assert LLMProvider.DEEPSEEK.value == "deepseek"
        assert LLMProvider.QWEN.value == "qwen"
        assert LLMProvider.KIMI.value == "kimi"

    def test_model_info(self):
        """测试模型信息"""
        model_info = ModelInfo(
            name="gpt-3.5-turbo",
            provider=LLMProvider.OPENAI,
            max_tokens=4096,
            supports_function_calling=True,
        )

        assert model_info.name == "gpt-3.5-turbo"
        assert model_info.provider == LLMProvider.OPENAI
        assert model_info.max_tokens == 4096
        assert model_info.supports_function_calling is True

    def test_get_model_info(self):
        """测试获取模型信息"""
        # 测试已知模型
        gpt_info = get_model_info("gpt-3.5-turbo")
        assert gpt_info is not None
        assert gpt_info.provider == LLMProvider.OPENAI

        claude_info = get_model_info("claude-3-sonnet-20240229")
        assert claude_info is not None
        assert claude_info.provider == LLMProvider.ANTHROPIC

        # 测试未知模型
        unknown_info = get_model_info("unknown-model")
        assert unknown_info is None

    def test_get_models_by_provider(self):
        """测试按提供商获取模型"""
        openai_models = get_models_by_provider(LLMProvider.OPENAI)
        assert len(openai_models) > 0
        assert all(model.provider == LLMProvider.OPENAI for model in openai_models)

        anthropic_models = get_models_by_provider(LLMProvider.ANTHROPIC)
        assert len(anthropic_models) > 0
        assert all(
            model.provider == LLMProvider.ANTHROPIC for model in anthropic_models
        )

    def test_get_recommended_models(self):
        """测试获取推荐模型"""
        recommended = get_recommended_models()

        assert "basic" in recommended
        assert "advanced" in recommended
        assert "reasoning" in recommended
        assert "coding" in recommended
        assert "chinese" in recommended
        assert "long_context" in recommended

    def test_validate_model_config(self):
        """测试模型配置验证"""
        # 有效配置
        assert validate_model_config("openai", "gpt-3.5-turbo") is True
        assert validate_model_config("anthropic", "claude-3-sonnet-20240229") is True

        # 无效提供商
        assert validate_model_config("invalid_provider", "gpt-3.5-turbo") is False

        # 提供商和模型不匹配
        assert validate_model_config("anthropic", "gpt-3.5-turbo") is False


class TestMultiProviderFactory:
    """多提供商工厂测试"""

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "GOOGLE_API_KEY": "test-google-key",
            "DEEPSEEK_API_KEY": "test-deepseek-key",
            "QWEN_API_KEY": "test-qwen-key",
            "KIMI_API_KEY": "test-kimi-key",
        },
    )
    def test_create_model_config_openai(self):
        """测试创建OpenAI模型配置"""
        factory = LLMFactory()
        config = factory._create_model_config("openai", "gpt-3.5-turbo", 0.7, 30)

        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.7
        assert config.timeout == 30
        assert config.api_key == "test-openai-key"

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
        },
    )
    def test_create_model_config_anthropic(self):
        """测试创建Anthropic模型配置"""
        factory = LLMFactory()
        config = factory._create_model_config(
            "anthropic", "claude-3-sonnet-20240229", 0.3, 60
        )

        assert config.provider == "anthropic"
        assert config.model == "claude-3-sonnet-20240229"
        assert config.temperature == 0.3
        assert config.timeout == 60
        assert config.api_key == "test-anthropic-key"

    @patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "test-openai-key", "DEEPSEEK_API_KEY": "test-deepseek-key"},
    )
    def test_create_model_config_deepseek(self):
        """测试创建DeepSeek模型配置"""
        factory = LLMFactory()
        config = factory._create_model_config("deepseek", "deepseek-chat", 0.5, 45)

        assert config.provider == "deepseek"
        assert config.model == "deepseek-chat"
        assert config.temperature == 0.5
        assert config.timeout == 45
        assert config.api_key == "test-deepseek-key"
        assert config.base_url == "https://api.deepseek.com/v1"

    @patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "test-openai-key", "QWEN_API_KEY": "test-qwen-key"},
    )
    def test_create_model_config_qwen(self):
        """测试创建Qwen模型配置"""
        factory = LLMFactory()
        config = factory._create_model_config("qwen", "qwen-turbo", 0.6, 40)

        assert config.provider == "qwen"
        assert config.model == "qwen-turbo"
        assert config.temperature == 0.6
        assert config.timeout == 40
        assert config.api_key == "test-qwen-key"
        assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"

    @patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "test-openai-key", "KIMI_API_KEY": "test-kimi-key"},
    )
    def test_create_model_config_kimi(self):
        """测试创建Kimi模型配置"""
        factory = LLMFactory()
        config = factory._create_model_config("kimi", "moonshot-v1-8k", 0.4, 35)

        assert config.provider == "kimi"
        assert config.model == "moonshot-v1-8k"
        assert config.temperature == 0.4
        assert config.timeout == 35
        assert config.api_key == "test-kimi-key"
        assert config.base_url == "https://api.moonshot.cn/v1"

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
            "BASIC_LLM_PROVIDER": "deepseek",
            "ADVANCED_LLM_PROVIDER": "anthropic",
            "REASONING_LLM_PROVIDER": "openai",
            "DEEPSEEK_API_KEY": "test-deepseek-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
        },
    )
    def test_provider_config_with_env_vars(self):
        """测试使用环境变量的提供商配置"""
        factory = LLMFactory()
        provider_config = factory._create_provider_config()

        # 检查基础模型使用DeepSeek
        assert provider_config.basic.provider == "deepseek"

        # 检查高级模型使用Anthropic
        assert provider_config.advanced.provider == "anthropic"

        # 检查推理模型使用OpenAI
        assert provider_config.reasoning.provider == "openai"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.llm.factory.ChatOpenAI")
    def test_create_llm_instance_selection(self, mock_openai):
        """测试LLM实例创建选择"""
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        factory = LLMFactory()

        # 测试OpenAI配置
        openai_config = LLMConfig(
            provider="openai", model="gpt-3.5-turbo", api_key="test-key"
        )
        openai_llm = factory._create_llm_instance(openai_config)
        assert openai_llm == mock_openai_instance
        mock_openai.assert_called()

        # 测试Anthropic配置（会回退到litellm，因为没有安装langchain-anthropic）
        anthropic_config = LLMConfig(
            provider="anthropic", model="claude-3-sonnet-20240229", api_key="test-key"
        )
        # 这里主要测试不会抛出异常
        try:
            anthropic_llm = factory._create_llm_instance(anthropic_config)
            # 应该成功创建实例（通过litellm回退）
            assert anthropic_llm is not None
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")


class TestProviderIntegration:
    """提供商集成测试"""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_factory_with_multiple_providers(self):
        """测试工厂支持多提供商"""
        factory = LLMFactory()

        # 测试缓存信息
        cache_info = factory.get_cache_info()
        assert "cached_models" in cache_info
        assert "cache_size" in cache_info

        # 测试清除缓存
        factory.clear_cache()
        cache_info_after = factory.get_cache_info()
        assert cache_info_after["cache_size"] == 0


if __name__ == "__main__":
    pytest.main([__file__])
