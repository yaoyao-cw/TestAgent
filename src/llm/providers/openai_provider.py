"""OpenAI LLM提供商实现"""

from typing import Dict, Any, List, Optional
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM提供商"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider_name = "openai"

    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        return ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"]

    def create_llm(self, model_name: str, **kwargs) -> Any:
        """创建LLM实例"""
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name,
                api_key=self.config.get("api_key"),
                base_url=self.config.get("base_url"),
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2000),
                **kwargs,
            )
        except ImportError:
            raise ImportError("请安装 langchain-openai: pip install langchain-openai")

    def validate_config(self) -> bool:
        """验证配置"""
        required_keys = ["api_key"]
        return all(key in self.config for key in required_keys)
