"""
服务配置加载器

从配置文件加载外部服务配置，支持动态配置更新。
"""

import os
from typing import Dict, List, Optional, Any
import logging

from .litellm_service import LiteLLMConfig
from .redis_service import RedisConfig
from ..config.settings import get_settings
from ..config.logging_config import get_logger

logger = get_logger("service_config_loader")


class ServiceConfigLoader:
    """服务配置加载器"""

    def __init__(self):
        self.settings = get_settings()

    def load_litellm_configs(self) -> Dict[str, LiteLLMConfig]:
        """加载LiteLLM配置"""
        configs = {}

        try:
            # 主要LLM配置
            if self.settings.llm.provider and self.settings.llm.api_key:
                configs[self.settings.llm.provider] = LiteLLMConfig(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    api_key=self.settings.llm.api_key,
                    api_base=self.settings.llm.api_base,
                    temperature=self.settings.llm.temperature,
                    max_tokens=self.settings.llm.max_tokens,
                    timeout=self.settings.llm.timeout,
                    retry_attempts=self.settings.llm.retry_attempts,
                )

            # 从环境变量加载其他提供商配置
            self._load_additional_llm_configs(configs)

            logger.info(f"已加载LiteLLM配置: {list(configs.keys())}")
            return configs

        except Exception as e:
            logger.error(f"加载LiteLLM配置失败: {e}")
            return {}

    def _load_additional_llm_configs(self, configs: Dict[str, LiteLLMConfig]):
        """从环境变量加载额外的LLM配置"""
        # OpenAI配置
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and "openai" not in configs:
            configs["openai"] = LiteLLMConfig(
                provider="openai",
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                api_key=openai_key,
                api_base=os.getenv("OPENAI_API_BASE"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("OPENAI_TIMEOUT", "60")),
            )

        # Anthropic配置
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and "anthropic" not in configs:
            configs["anthropic"] = LiteLLMConfig(
                provider="anthropic",
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
                api_key=anthropic_key,
                temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("ANTHROPIC_TIMEOUT", "60")),
            )

        # Google配置
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key and "google" not in configs:
            configs["google"] = LiteLLMConfig(
                provider="google",
                model=os.getenv("GOOGLE_MODEL", "gemini-pro"),
                api_key=google_key,
                temperature=float(os.getenv("GOOGLE_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("GOOGLE_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("GOOGLE_TIMEOUT", "60")),
            )

        # Azure OpenAI配置
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_key and azure_endpoint and "azure" not in configs:
            configs["azure"] = LiteLLMConfig(
                provider="azure",
                model=os.getenv("AZURE_OPENAI_MODEL", "gpt-35-turbo"),
                api_key=azure_key,
                api_base=azure_endpoint,
                temperature=float(os.getenv("AZURE_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("AZURE_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("AZURE_TIMEOUT", "60")),
                custom_llm_provider="azure",
            )

        # DeepSeek配置
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key and "deepseek" not in configs:
            configs["deepseek"] = LiteLLMConfig(
                provider="deepseek",
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=deepseek_key,
                api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
                temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("DEEPSEEK_TIMEOUT", "60")),
            )

        # Kimi配置
        kimi_key = os.getenv("KIMI_API_KEY")
        if kimi_key and "kimi" not in configs:
            configs["kimi"] = LiteLLMConfig(
                provider="kimi",
                model=os.getenv("KIMI_MODEL", "moonshot-v1-8k"),
                api_key=kimi_key,
                api_base=os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1"),
                temperature=float(os.getenv("KIMI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("KIMI_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("KIMI_TIMEOUT", "60")),
            )

        # Qwen配置
        qwen_key = os.getenv("QWEN_API_KEY")
        if qwen_key and "qwen" not in configs:
            configs["qwen"] = LiteLLMConfig(
                provider="qwen",
                model=os.getenv("QWEN_MODEL", "qwen-turbo"),
                api_key=qwen_key,
                api_base=os.getenv(
                    "QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
                ),
                temperature=float(os.getenv("QWEN_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("QWEN_MAX_TOKENS", "2000")),
                timeout=int(os.getenv("QWEN_TIMEOUT", "60")),
            )

    def load_redis_config(self) -> Optional[RedisConfig]:
        """加载Redis配置"""
        try:
            # 优先使用环境变量
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                return RedisConfig(url=redis_url)

            # 使用配置文件中的设置
            if hasattr(self.settings, "cache") and hasattr(
                self.settings.cache, "redis_url"
            ):
                redis_url = self.settings.cache.redis_url
                if redis_url:
                    return RedisConfig(url=redis_url)

            # 使用默认配置
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD")

            return RedisConfig(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
                socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")),
                socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "5.0")),
            )

        except Exception as e:
            logger.error(f"加载Redis配置失败: {e}")
            return None

    def get_mcp_servers_config(self) -> Dict[str, Any]:
        """获取MCP服务器配置"""
        try:
            if hasattr(self.settings, "mcp") and hasattr(self.settings.mcp, "servers"):
                return self.settings.mcp.servers
            return {}
        except Exception as e:
            logger.error(f"获取MCP服务器配置失败: {e}")
            return {}

    def get_sandbox_config(self) -> Dict[str, Any]:
        """获取沙盒配置"""
        try:
            sandbox_config = {}

            if hasattr(self.settings, "sandbox"):
                sandbox_config.update(self.settings.sandbox.__dict__)

            # 从环境变量覆盖
            e2b_api_key = os.getenv("E2B_API_KEY") or getattr(
                self.settings, "E2B_API_KEY", None
            )
            if e2b_api_key:
                sandbox_config["e2b_api_key"] = e2b_api_key

            return sandbox_config

        except Exception as e:
            logger.error(f"获取沙盒配置失败: {e}")
            return {}

    def get_rag_services_config(self) -> Dict[str, Any]:
        """获取RAG服务配置"""
        try:
            rag_config = {}

            if hasattr(self.settings, "rag"):
                rag_config.update(self.settings.rag.__dict__)

            # 添加环境变量配置
            rag_config.update(
                {
                    "chromadb_host": os.getenv("CHROMADB_HOST", "localhost"),
                    "chromadb_port": int(os.getenv("CHROMADB_PORT", "8000")),
                    "ragflow_api_url": os.getenv("RAGFLOW_API_URL"),
                    "ragflow_api_key": os.getenv("RAGFLOW_API_KEY"),
                    "qanything_api_url": os.getenv("QANYTHING_API_URL"),
                    "qanything_api_key": os.getenv("QANYTHING_API_KEY"),
                }
            )

            return rag_config

        except Exception as e:
            logger.error(f"获取RAG服务配置失败: {e}")
            return {}

    def validate_configs(self) -> Dict[str, bool]:
        """验证配置"""
        validation_results = {}

        # 验证LiteLLM配置
        litellm_configs = self.load_litellm_configs()
        validation_results["litellm"] = len(litellm_configs) > 0

        # 验证Redis配置
        redis_config = self.load_redis_config()
        validation_results["redis"] = redis_config is not None

        # 验证MCP配置
        mcp_config = self.get_mcp_servers_config()
        validation_results["mcp"] = isinstance(mcp_config, dict)

        # 验证沙盒配置
        sandbox_config = self.get_sandbox_config()
        validation_results["sandbox"] = isinstance(sandbox_config, dict)

        # 验证RAG配置
        rag_config = self.get_rag_services_config()
        validation_results["rag"] = isinstance(rag_config, dict)

        return validation_results

    def get_all_service_configs(self) -> Dict[str, Any]:
        """获取所有服务配置"""
        return {
            "litellm": self.load_litellm_configs(),
            "redis": self.load_redis_config(),
            "mcp": self.get_mcp_servers_config(),
            "sandbox": self.get_sandbox_config(),
            "rag": self.get_rag_services_config(),
            "validation": self.validate_configs(),
        }


# 全局配置加载器实例
_config_loader: Optional[ServiceConfigLoader] = None


def get_service_config_loader() -> ServiceConfigLoader:
    """获取全局配置加载器实例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ServiceConfigLoader()
    return _config_loader
