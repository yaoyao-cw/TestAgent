"""LLM提供商配置和支持"""

from enum import Enum
from typing import Dict, List, Optional


class LLMProvider(Enum):
    """支持的LLM提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    KIMI = "kimi"
    OPENAI_COMPATIBLE = "openai_compatible"


class ModelInfo:
    """模型信息"""

    def __init__(
        self,
        name: str,
        provider: LLMProvider,
        max_tokens: int = 4096,
        supports_streaming: bool = True,
        supports_function_calling: bool = False,
        cost_per_1k_tokens: Optional[float] = None,
    ):
        self.name = name
        self.provider = provider
        self.max_tokens = max_tokens
        self.supports_streaming = supports_streaming
        self.supports_function_calling = supports_function_calling
        self.cost_per_1k_tokens = cost_per_1k_tokens


# 预定义的模型配置
SUPPORTED_MODELS: Dict[str, ModelInfo] = {
    # OpenAI Models
    "gpt-3.5-turbo": ModelInfo(
        name="gpt-3.5-turbo",
        provider=LLMProvider.OPENAI,
        max_tokens=4096,
        supports_function_calling=True,
        cost_per_1k_tokens=0.002,
    ),
    "gpt-4": ModelInfo(
        name="gpt-4",
        provider=LLMProvider.OPENAI,
        max_tokens=8192,
        supports_function_calling=True,
        cost_per_1k_tokens=0.03,
    ),
    "gpt-4-turbo": ModelInfo(
        name="gpt-4-turbo",
        provider=LLMProvider.OPENAI,
        max_tokens=128000,
        supports_function_calling=True,
        cost_per_1k_tokens=0.01,
    ),
    "o1-preview": ModelInfo(
        name="o1-preview",
        provider=LLMProvider.OPENAI,
        max_tokens=32768,
        supports_streaming=False,
        supports_function_calling=False,
        cost_per_1k_tokens=0.015,
    ),
    # Anthropic Claude Models
    "claude-3-haiku-20240307": ModelInfo(
        name="claude-3-haiku-20240307",
        provider=LLMProvider.ANTHROPIC,
        max_tokens=200000,
        supports_function_calling=True,
        cost_per_1k_tokens=0.00025,
    ),
    "claude-3-sonnet-20240229": ModelInfo(
        name="claude-3-sonnet-20240229",
        provider=LLMProvider.ANTHROPIC,
        max_tokens=200000,
        supports_function_calling=True,
        cost_per_1k_tokens=0.003,
    ),
    "claude-3-opus-20240229": ModelInfo(
        name="claude-3-opus-20240229",
        provider=LLMProvider.ANTHROPIC,
        max_tokens=200000,
        supports_function_calling=True,
        cost_per_1k_tokens=0.015,
    ),
    # Google Gemini Models
    "gemini-pro": ModelInfo(
        name="gemini-pro",
        provider=LLMProvider.GOOGLE,
        max_tokens=32768,
        supports_function_calling=True,
        cost_per_1k_tokens=0.0005,
    ),
    "gemini-pro-vision": ModelInfo(
        name="gemini-pro-vision",
        provider=LLMProvider.GOOGLE,
        max_tokens=16384,
        supports_function_calling=False,
        cost_per_1k_tokens=0.0005,
    ),
    # DeepSeek Models
    "deepseek-chat": ModelInfo(
        name="deepseek-chat",
        provider=LLMProvider.DEEPSEEK,
        max_tokens=32768,
        supports_function_calling=True,
        cost_per_1k_tokens=0.0014,
    ),
    "deepseek-coder": ModelInfo(
        name="deepseek-coder",
        provider=LLMProvider.DEEPSEEK,
        max_tokens=16384,
        supports_function_calling=True,
        cost_per_1k_tokens=0.0014,
    ),
    # Qwen Models
    "qwen-turbo": ModelInfo(
        name="qwen-turbo",
        provider=LLMProvider.QWEN,
        max_tokens=8192,
        supports_function_calling=True,
        cost_per_1k_tokens=0.002,
    ),
    "qwen-plus": ModelInfo(
        name="qwen-plus",
        provider=LLMProvider.QWEN,
        max_tokens=32768,
        supports_function_calling=True,
        cost_per_1k_tokens=0.004,
    ),
    "qwen-max": ModelInfo(
        name="qwen-max",
        provider=LLMProvider.QWEN,
        max_tokens=8192,
        supports_function_calling=True,
        cost_per_1k_tokens=0.02,
    ),
    # Kimi Models
    "moonshot-v1-8k": ModelInfo(
        name="moonshot-v1-8k",
        provider=LLMProvider.KIMI,
        max_tokens=8192,
        supports_function_calling=True,
        cost_per_1k_tokens=0.012,
    ),
    "moonshot-v1-32k": ModelInfo(
        name="moonshot-v1-32k",
        provider=LLMProvider.KIMI,
        max_tokens=32768,
        supports_function_calling=True,
        cost_per_1k_tokens=0.024,
    ),
    "moonshot-v1-128k": ModelInfo(
        name="moonshot-v1-128k",
        provider=LLMProvider.KIMI,
        max_tokens=131072,
        supports_function_calling=True,
        cost_per_1k_tokens=0.06,
    ),
}


def get_model_info(model_name: str) -> Optional[ModelInfo]:
    """获取模型信息"""
    return SUPPORTED_MODELS.get(model_name)


def get_models_by_provider(provider: LLMProvider) -> List[ModelInfo]:
    """获取指定提供商的所有模型"""
    return [model for model in SUPPORTED_MODELS.values() if model.provider == provider]


def get_recommended_models() -> Dict[str, str]:
    """获取推荐的模型配置"""
    return {
        "basic": "gpt-3.5-turbo",  # 基础任务
        "advanced": "gpt-4",  # 高级任务
        "reasoning": "o1-preview",  # 推理任务
        "coding": "deepseek-coder",  # 编程任务
        "chinese": "qwen-plus",  # 中文任务
        "long_context": "claude-3-sonnet-20240229",  # 长上下文任务
    }


def validate_model_config(provider: str, model: str) -> bool:
    """验证模型配置是否有效"""
    try:
        provider_enum = LLMProvider(provider.lower())
        model_info = get_model_info(model)

        if model_info is None:
            return True  # 允许未知模型，可能是新模型

        return model_info.provider == provider_enum
    except ValueError:
        return False
