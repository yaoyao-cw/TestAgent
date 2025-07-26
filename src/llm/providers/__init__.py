"""LLM提供商模块"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from .base import BaseLLMProvider, LLMMessage, LLMResponse
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .deepseek_provider import DeepSeekProvider
from .qwen_provider import QwenProvider
from .kimi_provider import KimiProvider
from .doubao_provider import DoubaoProvider
from .zhipu_provider import ZhipuProvider
from .baichuan_provider import BaichuanProvider

# 为了兼容性，创建LLMProvider别名
LLMProvider = BaseLLMProvider


@dataclass
class ModelInfo:
    """模型信息"""

    name: str
    provider: str
    max_tokens: int
    supports_streaming: bool = True
    cost_per_1k_tokens: Optional[float] = None


# 模型信息映射
MODEL_INFO_MAP: Dict[str, ModelInfo] = {
    # OpenAI模型
    "gpt-4": ModelInfo("gpt-4", "openai", 8192, True, 0.03),
    "gpt-4-turbo": ModelInfo("gpt-4-turbo", "openai", 128000, True, 0.01),
    "gpt-3.5-turbo": ModelInfo("gpt-3.5-turbo", "openai", 4096, True, 0.002),
    # Anthropic模型
    "claude-3-opus": ModelInfo("claude-3-opus", "anthropic", 200000, True, 0.015),
    "claude-3-sonnet": ModelInfo("claude-3-sonnet", "anthropic", 200000, True, 0.003),
    "claude-3-haiku": ModelInfo("claude-3-haiku", "anthropic", 200000, True, 0.00025),
    # 国产模型
    "deepseek-chat": ModelInfo("deepseek-chat", "deepseek", 32768, True, 0.0014),
    "qwen-turbo": ModelInfo("qwen-turbo", "qwen", 8192, True, 0.002),
    "moonshot-v1-8k": ModelInfo("moonshot-v1-8k", "kimi", 8192, True, 0.012),
    "doubao-pro-4k": ModelInfo("doubao-pro-4k", "doubao", 4096, True, 0.0008),
    "glm-4": ModelInfo("glm-4", "zhipu", 128000, True, 0.1),
    "baichuan2-turbo": ModelInfo("baichuan2-turbo", "baichuan", 32768, True, 0.008),
}


def get_model_info(model_name: str) -> Optional[ModelInfo]:
    """获取模型信息"""
    return MODEL_INFO_MAP.get(model_name)


def get_recommended_models() -> List[str]:
    """获取推荐模型列表"""
    return ["gpt-4-turbo", "claude-3-sonnet", "deepseek-chat", "qwen-turbo", "glm-4"]


__all__ = [
    "BaseLLMProvider",
    "LLMProvider",  # 别名
    "LLMMessage",
    "LLMResponse",
    "ModelInfo",
    "get_model_info",
    "get_recommended_models",
    "OpenAIProvider",
    "AnthropicProvider",
    "DeepSeekProvider",
    "QwenProvider",
    "KimiProvider",
    "DoubaoProvider",
    "ZhipuProvider",
    "BaichuanProvider",
]
