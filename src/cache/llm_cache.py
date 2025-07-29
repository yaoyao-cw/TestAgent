#!/usr/bin/env python3
"""
LLM响应缓存系统

专门用于缓存LLM模型的响应，提高响应速度和降低API调用成本
"""

import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .cache_manager import get_cache_manager, cache

logger = logging.getLogger("llm_cache")


class LLMCache:
    """LLM缓存管理器"""

    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.default_ttl = 3600  # 1小时
        self.prefix = "llm:"

    def _generate_cache_key(
        self, provider: str, model: str, messages: List[Dict], **kwargs
    ) -> str:
        """生成LLM缓存键"""
        # 创建包含所有相关参数的字典
        cache_data = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens"),
            "top_p": kwargs.get("top_p"),
            "frequency_penalty": kwargs.get("frequency_penalty"),
            "presence_penalty": kwargs.get("presence_penalty"),
            "stop": kwargs.get("stop"),
        }

        # 移除None值
        cache_data = {k: v for k, v in cache_data.items() if v is not None}

        # 生成哈希键
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()

        return f"{self.prefix}{provider}:{model}:{cache_hash}"

    async def get_cached_response(
        self, provider: str, model: str, messages: List[Dict], **kwargs
    ) -> Optional[Dict[str, Any]]:
        """获取缓存的LLM响应"""
        cache_key = self._generate_cache_key(provider, model, messages, **kwargs)

        try:
            cached_response = await self.cache_manager.get(cache_key)
            if cached_response:
                logger.debug(f"LLM cache hit for key: {cache_key[:32]}...")
                # 添加缓存标记
                cached_response["_cached"] = True
                cached_response["_cache_key"] = cache_key
                return cached_response
            else:
                logger.debug(f"LLM cache miss for key: {cache_key[:32]}...")
                return None
        except Exception as e:
            logger.error(f"Error getting LLM cache: {e}")
            return None

    async def cache_response(
        self,
        provider: str,
        model: str,
        messages: List[Dict],
        response: Dict[str, Any],
        ttl: Optional[int] = None,
        **kwargs,
    ) -> bool:
        """缓存LLM响应"""
        cache_key = self._generate_cache_key(provider, model, messages, **kwargs)

        try:
            # 准备缓存数据
            cache_data = {
                "response": response,
                "provider": provider,
                "model": model,
                "cached_at": datetime.now().isoformat(),
                "request_hash": cache_key,
            }

            # 使用指定的TTL或默认TTL
            cache_ttl = ttl or self.default_ttl

            success = await self.cache_manager.set(cache_key, cache_data, cache_ttl)
            if success:
                logger.debug(f"LLM response cached with key: {cache_key[:32]}...")
            else:
                logger.warning(
                    f"Failed to cache LLM response for key: {cache_key[:32]}..."
                )

            return success
        except Exception as e:
            logger.error(f"Error caching LLM response: {e}")
            return False

    async def invalidate_cache(self, provider: str = None, model: str = None) -> int:
        """清除LLM缓存"""
        try:
            if provider and model:
                pattern = f"{self.prefix}{provider}:{model}:*"
            elif provider:
                pattern = f"{self.prefix}{provider}:*"
            else:
                pattern = f"{self.prefix}*"

            keys = await self.cache_manager.keys(pattern)
            count = 0
            for key in keys:
                if await self.cache_manager.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} LLM cache entries")
            return count
        except Exception as e:
            logger.error(f"Error invalidating LLM cache: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取LLM缓存统计信息"""
        try:
            # 获取所有LLM缓存键
            keys = await self.cache_manager.keys(f"{self.prefix}*")

            # 按提供商和模型分组统计
            stats = {"total_entries": len(keys), "providers": {}, "models": {}}

            for key in keys:
                try:
                    # 解析键格式: llm:provider:model:hash
                    parts = key.split(":", 3)
                    if len(parts) >= 3:
                        provider = parts[1]
                        model = parts[2]

                        if provider not in stats["providers"]:
                            stats["providers"][provider] = 0
                        stats["providers"][provider] += 1

                        model_key = f"{provider}:{model}"
                        if model_key not in stats["models"]:
                            stats["models"][model_key] = 0
                        stats["models"][model_key] += 1
                except:
                    continue

            return stats
        except Exception as e:
            logger.error(f"Error getting LLM cache stats: {e}")
            return {"error": str(e)}


# 全局LLM缓存实例
_llm_cache: Optional[LLMCache] = None


def get_llm_cache() -> LLMCache:
    """获取全局LLM缓存实例"""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMCache()
    return _llm_cache


def llm_cache(ttl: Optional[int] = None, cache_key_func: Optional[callable] = None):
    """LLM缓存装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            llm_cache_instance = get_llm_cache()

            # 从参数中提取LLM相关信息
            provider = kwargs.get("provider", "unknown")
            model = kwargs.get("model", "unknown")
            messages = kwargs.get("messages", [])

            # 尝试从缓存获取响应
            cached_response = await llm_cache_instance.get_cached_response(
                provider, model, messages, **kwargs
            )

            if cached_response:
                return cached_response["response"]

            # 缓存未命中，调用原函数
            response = await func(*args, **kwargs)

            # 缓存响应
            await llm_cache_instance.cache_response(
                provider, model, messages, response, ttl, **kwargs
            )

            return response

        return wrapper

    return decorator


# 便捷函数
async def cache_llm_response(
    provider: str,
    model: str,
    messages: List[Dict],
    response: Dict[str, Any],
    ttl: Optional[int] = None,
    **kwargs,
) -> bool:
    """缓存LLM响应的便捷函数"""
    llm_cache_instance = get_llm_cache()
    return await llm_cache_instance.cache_response(
        provider, model, messages, response, ttl, **kwargs
    )


async def get_cached_llm_response(
    provider: str, model: str, messages: List[Dict], **kwargs
) -> Optional[Dict[str, Any]]:
    """获取缓存的LLM响应的便捷函数"""
    llm_cache_instance = get_llm_cache()
    return await llm_cache_instance.get_cached_response(
        provider, model, messages, **kwargs
    )


async def clear_llm_cache(provider: str = None, model: str = None) -> int:
    """清除LLM缓存的便捷函数"""
    llm_cache_instance = get_llm_cache()
    return await llm_cache_instance.invalidate_cache(provider, model)
