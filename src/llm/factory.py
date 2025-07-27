"""LLM工厂类"""

import os
from typing import Any, Dict, Optional

import litellm
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

# 条件导入其他LLM提供商
try:
    from langchain_anthropic import ChatAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from langchain_community.chat_models import ChatDeepSeek

    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from ..exceptions import LLMServiceException
from ..models.types import AgentType, LLMType
from .config import AgentLLMMapping, LLMConfig, LLMProviderConfig

logger = get_logger("llm_factory")


class LLMFactory:
    """LLM工厂类，负责创建和管理LLM实例"""

    def __init__(self):
        self.settings = get_settings()
        self.provider_config = self._create_provider_config()
        self.agent_mapping = AgentLLMMapping()
        self._llm_cache: Dict[str, BaseChatModel] = {}

    def _create_provider_config(self) -> LLMProviderConfig:
        """创建LLM提供商配置"""
        # 可以通过环境变量配置不同的模型提供商
        basic_provider = os.getenv("BASIC_LLM_PROVIDER", "openai")
        advanced_provider = os.getenv("ADVANCED_LLM_PROVIDER", "openai")
        reasoning_provider = os.getenv("REASONING_LLM_PROVIDER", "openai")

        return LLMProviderConfig(
            basic=self._create_model_config(
                provider=basic_provider,
                model=os.getenv("BASIC_LLM_MODEL", "gpt-3.5-turbo"),
                temperature=0.7,
                timeout=30,
            ),
            advanced=self._create_model_config(
                provider=advanced_provider,
                model=os.getenv("ADVANCED_LLM_MODEL", "gpt-4"),
                temperature=0.3,
                timeout=60,
            ),
            reasoning=self._create_model_config(
                provider=reasoning_provider,
                model=os.getenv("REASONING_LLM_MODEL", "o1-preview"),
                temperature=0.1,
                timeout=120,
            ),
        )

    def _create_model_config(
        self, provider: str, model: str, temperature: float, timeout: int
    ) -> LLMConfig:
        """根据提供商创建模型配置"""
        provider = provider.lower()

        if provider == "openai":
            return LLMConfig(
                provider="openai",
                model=model,
                temperature=temperature,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "anthropic" or provider == "claude":
            return LLMConfig(
                provider="anthropic",
                model=model or "claude-3-sonnet-20240229",
                temperature=temperature,
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.anthropic_base_url,
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "google" or provider == "gemini":
            return LLMConfig(
                provider="google",
                model=model or "gemini-pro",
                temperature=temperature,
                api_key=self.settings.google_api_key,
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "deepseek":
            return LLMConfig(
                provider="deepseek",
                model=model or "deepseek-chat",
                temperature=temperature,
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url
                or "https://api.deepseek.com/v1",
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "qwen" or provider == "tongyi":
            return LLMConfig(
                provider="qwen",
                model=model or "qwen-turbo",
                temperature=temperature,
                api_key=self.settings.qwen_api_key,
                base_url=self.settings.qwen_base_url
                or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "kimi" or provider == "moonshot":
            return LLMConfig(
                provider="kimi",
                model=model or "moonshot-v1-8k",
                temperature=temperature,
                api_key=self.settings.kimi_api_key,
                base_url=self.settings.kimi_base_url or "https://api.moonshot.cn/v1",
                timeout=timeout,
                max_retries=3,
            )
        elif provider == "openai_compatible":
            return LLMConfig(
                provider="openai_compatible",
                model=model,
                temperature=temperature,
                api_key=self.settings.openai_compatible_api_key,
                base_url=self.settings.openai_compatible_base_url,
                timeout=timeout,
                max_retries=3,
            )
        else:
            # 默认使用OpenAI
            logger.warning(f"Unknown provider {provider}, falling back to OpenAI")
            return LLMConfig(
                provider="openai",
                model=model or "gpt-3.5-turbo",
                temperature=temperature,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=timeout,
                max_retries=3,
            )

    def create_llm(self, llm_type: LLMType) -> BaseChatModel:
        """创建LLM实例

        Args:
            llm_type: LLM类型

        Returns:
            LLM实例

        Raises:
            LLMServiceException: 创建LLM失败时抛出
        """
        cache_key = f"{llm_type.value}"

        if cache_key in self._llm_cache:
            logger.debug(f"Using cached LLM for type: {llm_type.value}")
            return self._llm_cache[cache_key]

        try:
            config = self.provider_config.get_config_by_type(llm_type)
            llm = self._create_llm_instance(config)

            # 缓存LLM实例
            self._llm_cache[cache_key] = llm
            logger.info(
                f"Created LLM instance for type: {llm_type.value}, model: {config.model}"
            )

            return llm

        except Exception as e:
            logger.error(f"Failed to create LLM for type {llm_type.value}: {e}")
            raise LLMServiceException(f"Failed to create LLM: {e}")

    def _create_llm_instance(self, config: LLMConfig) -> BaseChatModel:
        """创建具体的LLM实例"""
        provider = config.provider.lower()

        try:
            if provider == "openai":
                return self._create_openai_llm(config)
            elif provider == "anthropic" or provider == "claude":
                return self._create_anthropic_llm(config)
            elif provider == "google" or provider == "gemini":
                return self._create_google_llm(config)
            elif provider == "deepseek":
                return self._create_deepseek_llm(config)
            elif provider == "qwen" or provider == "tongyi":
                return self._create_qwen_llm(config)
            elif provider == "kimi" or provider == "moonshot":
                return self._create_kimi_llm(config)
            elif provider == "openai_compatible":
                return self._create_openai_compatible_llm(config)
            else:
                # 使用litellm作为后备方案
                return self._create_litellm_instance(config)
        except ImportError as e:
            logger.warning(
                f"Provider {provider} not available, falling back to litellm: {e}"
            )
            return self._create_litellm_instance(config)

    def _create_openai_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建OpenAI LLM实例"""
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            openai_api_key=config.api_key,
            openai_api_base=config.base_url,
            request_timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _create_anthropic_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建Anthropic Claude LLM实例"""
        if not ANTHROPIC_AVAILABLE:
            logger.warning("langchain-anthropic not installed, using litellm")
            return self._create_litellm_instance(config)

        return ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            anthropic_api_key=config.api_key,
            anthropic_api_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _create_google_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建Google Gemini LLM实例"""
        if not GOOGLE_AVAILABLE:
            logger.warning("langchain-google-genai not installed, using litellm")
            return self._create_litellm_instance(config)

        return ChatGoogleGenerativeAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            google_api_key=config.api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _create_deepseek_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建DeepSeek LLM实例"""
        if not DEEPSEEK_AVAILABLE:
            logger.warning("DeepSeek integration not available, using litellm")
            return self._create_litellm_instance(config)

        return ChatDeepSeek(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            deepseek_api_key=config.api_key,
            deepseek_api_base=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _create_qwen_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建Qwen LLM实例"""
        # Qwen通常通过OpenAI兼容接口或litellm使用
        if config.base_url:
            return self._create_openai_compatible_llm(config)
        else:
            return self._create_litellm_instance(config)

    def _create_kimi_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建Kimi LLM实例"""
        # Kimi (Moonshot) 通常通过OpenAI兼容接口使用
        return self._create_openai_compatible_llm(config)

    def _create_openai_compatible_llm(self, config: LLMConfig) -> BaseChatModel:
        """创建OpenAI兼容接口的LLM实例"""
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            openai_api_key=config.api_key,
            openai_api_base=config.base_url,
            request_timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def _create_litellm_instance(self, config: LLMConfig) -> BaseChatModel:
        """使用litellm创建LLM实例"""
        # 设置litellm配置
        if config.api_key:
            litellm.api_key = config.api_key
        if config.base_url:
            litellm.api_base = config.base_url

        # 创建ChatOpenAI实例，但使用litellm的模型名称
        model_name = f"{config.provider}/{config.model}"

        return ChatOpenAI(
            model=model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            request_timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def get_llm_for_agent(self, agent_type: AgentType) -> BaseChatModel:
        """为指定智能体获取LLM实例

        Args:
            agent_type: 智能体类型

        Returns:
            LLM实例
        """
        llm_type = self.agent_mapping.get_llm_type_for_agent(agent_type)
        return self.create_llm(llm_type)

    def clear_cache(self):
        """清除LLM缓存"""
        self._llm_cache.clear()
        logger.info("LLM cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "cached_models": list(self._llm_cache.keys()),
            "cache_size": len(self._llm_cache),
        }


# 全局LLM工厂实例
_llm_factory: Optional[LLMFactory] = None


def get_llm_factory() -> LLMFactory:
    """获取LLM工厂单例"""
    global _llm_factory
    if _llm_factory is None:
        _llm_factory = LLMFactory()
    return _llm_factory


def get_llm_by_type(llm_type: LLMType) -> BaseChatModel:
    """根据类型获取LLM实例

    Args:
        llm_type: LLM类型

    Returns:
        LLM实例
    """
    factory = get_llm_factory()
    return factory.create_llm(llm_type)


def get_llm_for_agent(agent_type: AgentType) -> BaseChatModel:
    """为智能体获取LLM实例

    Args:
        agent_type: 智能体类型

    Returns:
        LLM实例
    """
    factory = get_llm_factory()
    return factory.get_llm_for_agent(agent_type)
