"""通义千问 LLM提供商"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from .base import BaseLLMProvider, LLMMessage, LLMResponse


class QwenProvider(BaseLLMProvider):
    """通义千问 LLM提供商"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key, base_url or "https://dashscope.aliyuncs.com", **kwargs
        )
        self.models = [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-max-longcontext",
            "qwen2.5-72b-instruct",
            "qwen2.5-32b-instruct",
            "qwen2.5-14b-instruct",
            "qwen2.5-7b-instruct",
        ]

    async def generate(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """生成响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": msg.role, "content": msg.content} for msg in messages
                ]
            },
            "parameters": {"temperature": temperature, "result_format": "message"},
        }

        if max_tokens:
            payload["parameters"]["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/compatible-mode/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    raise Exception(
                        f"通义千问API错误: {response.status} - {await response.text()}"
                    )

                data = await response.json()

                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data["model"],
                    usage=data.get("usage"),
                    finish_reason=data["choices"][0].get("finish_reason"),
                )

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式生成响应"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": msg.role, "content": msg.content} for msg in messages
                ]
            },
            "parameters": {
                "temperature": temperature,
                "result_format": "message",
                "incremental_output": True,
            },
        }

        if max_tokens:
            payload["parameters"]["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/compatible-mode/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    raise Exception(
                        f"通义千问API错误: {response.status} - {await response.text()}"
                    )

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue

    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        return self.models

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            test_messages = [LLMMessage(role="user", content="你好")]
            await self.generate(test_messages, self.models[0], max_tokens=10)
            return True
        except Exception:
            return False
