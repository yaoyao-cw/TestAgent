"""配置模块测试"""

import os
from unittest.mock import patch

import pytest

from src.config.logging_config import get_logger, setup_logging
from src.config.settings import Settings, get_settings


class TestSettings:
    """设置类测试"""

    def test_default_settings(self):
        """测试默认设置"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            settings = Settings()
            assert settings.openai_api_key == "test-key"
            assert settings.rag_provider == "chroma"
            assert settings.max_plan_iterations == 3
            assert settings.auto_accepted_plan is True

    def test_llm_providers(self):
        """测试LLM提供商配置"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            settings = Settings()
            providers = settings.llm_providers

            assert "basic" in providers
            assert "advanced" in providers
            assert "reasoning" in providers

            assert providers["basic"]["model"] == "gpt-3.5-turbo"
            assert providers["advanced"]["model"] == "gpt-4"

    def test_agent_llm_map(self):
        """测试智能体LLM映射"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            settings = Settings()
            agent_map = settings.agent_llm_map

            assert agent_map["coordinator"] == "basic"
            assert agent_map["planner"] == "advanced"
            assert agent_map["researcher"] == "advanced"

    def test_get_llm_config(self):
        """测试获取LLM配置"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            settings = Settings()

            config = settings.get_llm_config("coordinator")
            assert config["model"] == "gpt-3.5-turbo"

            config = settings.get_llm_config("planner")
            assert config["model"] == "gpt-4"

            # 测试未知智能体类型
            config = settings.get_llm_config("unknown")
            assert config["model"] == "gpt-3.5-turbo"  # 应该返回basic配置


class TestLogging:
    """日志配置测试"""

    def test_get_logger(self):
        """测试获取日志器"""
        logger = get_logger("test")
        assert logger is not None
        assert "testagent.test" in logger.logger.name

    def test_setup_logging(self, tmp_path):
        """测试日志设置"""
        log_file = tmp_path / "test.log"
        setup_logging("DEBUG", str(log_file))

        # 测试日志文件是否创建
        logger = get_logger("test")
        logger.info("Test message")

        assert log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__])
