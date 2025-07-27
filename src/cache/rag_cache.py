#!/usr/bin/env python3
"""
RAG检索结果缓存系统

缓存文档检索和向量化结果，提高RAG系统性能
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .cache_manager import cache, get_cache_manager

logger = logging.getLogger("rag_cache")


class RAGCache:
    """RAG缓存管理器"""

    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.default_ttl = 7200  # 2小时
        self.vector_ttl = 86400  # 24小时（向量化结果缓存更久）
        self.retrieval_prefix = "rag:retrieval:"
        self.vector_prefix = "rag:vector:"
        self.document_prefix = "rag:document:"

    def _generate_retrieval_key(
        self, query: str, collection: str = None, top_k: int = 5, **kwargs
    ) -> str:
        """生成检索缓存键"""
        cache_data = {
            "query": query.strip().lower(),
            "collection": collection,
            "top_k": top_k,
            "filters": kwargs.get("filters"),
            "threshold": kwargs.get("threshold"),
        }

        # 移除None值
        cache_data = {k: v for k, v in cache_data.items() if v is not None}

        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()

        return f"{self.retrieval_prefix}{cache_hash}"

    def _generate_vector_key(self, text: str, model: str = "default") -> str:
        """生成向量化缓存键"""
        # 对文本进行标准化
        normalized_text = text.strip()
        text_hash = hashlib.sha256(normalized_text.encode()).hexdigest()

        return f"{self.vector_prefix}{model}:{text_hash}"

    def _generate_document_key(self, document_id: str, chunk_id: str = None) -> str:
        """生成文档缓存键"""
        if chunk_id:
            return f"{self.document_prefix}{document_id}:{chunk_id}"
        else:
            return f"{self.document_prefix}{document_id}"

    async def get_cached_retrieval(
        self, query: str, collection: str = None, top_k: int = 5, **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的检索结果"""
        cache_key = self._generate_retrieval_key(query, collection, top_k, **kwargs)

        try:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                logger.debug(f"RAG retrieval cache hit for query: {query[:50]}...")
                return cached_result["results"]
            else:
                logger.debug(f"RAG retrieval cache miss for query: {query[:50]}...")
                return None
        except Exception as e:
            logger.error(f"Error getting RAG retrieval cache: {e}")
            return None

    async def cache_retrieval_result(
        self,
        query: str,
        results: List[Dict[str, Any]],
        collection: str = None,
        top_k: int = 5,
        ttl: Optional[int] = None,
        **kwargs,
    ) -> bool:
        """缓存检索结果"""
        cache_key = self._generate_retrieval_key(query, collection, top_k, **kwargs)

        try:
            cache_data = {
                "query": query,
                "results": results,
                "collection": collection,
                "top_k": top_k,
                "cached_at": datetime.now().isoformat(),
                "result_count": len(results),
            }

            cache_ttl = ttl or self.default_ttl
            success = await self.cache_manager.set(cache_key, cache_data, cache_ttl)

            if success:
                logger.debug(f"RAG retrieval result cached for query: {query[:50]}...")

            return success
        except Exception as e:
            logger.error(f"Error caching RAG retrieval result: {e}")
            return False

    async def get_cached_vector(
        self, text: str, model: str = "default"
    ) -> Optional[List[float]]:
        """获取缓存的向量"""
        cache_key = self._generate_vector_key(text, model)

        try:
            cached_vector = await self.cache_manager.get(cache_key)
            if cached_vector:
                logger.debug(f"Vector cache hit for text: {text[:50]}...")
                return cached_vector["vector"]
            else:
                logger.debug(f"Vector cache miss for text: {text[:50]}...")
                return None
        except Exception as e:
            logger.error(f"Error getting vector cache: {e}")
            return None

    async def cache_vector(
        self,
        text: str,
        vector: List[float],
        model: str = "default",
        ttl: Optional[int] = None,
    ) -> bool:
        """缓存向量"""
        cache_key = self._generate_vector_key(text, model)

        try:
            cache_data = {
                "text": text,
                "vector": vector,
                "model": model,
                "cached_at": datetime.now().isoformat(),
                "vector_dim": len(vector),
            }

            cache_ttl = ttl or self.vector_ttl
            success = await self.cache_manager.set(cache_key, cache_data, cache_ttl)

            if success:
                logger.debug(f"Vector cached for text: {text[:50]}...")

            return success
        except Exception as e:
            logger.error(f"Error caching vector: {e}")
            return False

    async def get_cached_document(
        self, document_id: str, chunk_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """获取缓存的文档"""
        cache_key = self._generate_document_key(document_id, chunk_id)

        try:
            cached_doc = await self.cache_manager.get(cache_key)
            if cached_doc:
                logger.debug(f"Document cache hit for: {document_id}")
                return cached_doc
            else:
                logger.debug(f"Document cache miss for: {document_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting document cache: {e}")
            return None

    async def cache_document(
        self,
        document_id: str,
        document_data: Dict[str, Any],
        chunk_id: str = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """缓存文档"""
        cache_key = self._generate_document_key(document_id, chunk_id)

        try:
            cache_data = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "data": document_data,
                "cached_at": datetime.now().isoformat(),
            }

            cache_ttl = ttl or self.vector_ttl  # 文档缓存时间较长
            success = await self.cache_manager.set(cache_key, cache_data, cache_ttl)

            if success:
                logger.debug(f"Document cached: {document_id}")

            return success
        except Exception as e:
            logger.error(f"Error caching document: {e}")
            return False

    async def invalidate_retrieval_cache(self, query_pattern: str = None) -> int:
        """清除检索缓存"""
        try:
            if query_pattern:
                # 这里简化处理，实际应该根据查询模式匹配
                pattern = f"{self.retrieval_prefix}*"
            else:
                pattern = f"{self.retrieval_prefix}*"

            keys = await self.cache_manager.keys(pattern)
            count = 0
            for key in keys:
                if await self.cache_manager.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} RAG retrieval cache entries")
            return count
        except Exception as e:
            logger.error(f"Error invalidating RAG retrieval cache: {e}")
            return 0

    async def invalidate_vector_cache(self, model: str = None) -> int:
        """清除向量缓存"""
        try:
            if model:
                pattern = f"{self.vector_prefix}{model}:*"
            else:
                pattern = f"{self.vector_prefix}*"

            keys = await self.cache_manager.keys(pattern)
            count = 0
            for key in keys:
                if await self.cache_manager.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} vector cache entries")
            return count
        except Exception as e:
            logger.error(f"Error invalidating vector cache: {e}")
            return 0

    async def invalidate_document_cache(self, document_id: str = None) -> int:
        """清除文档缓存"""
        try:
            if document_id:
                pattern = f"{self.document_prefix}{document_id}*"
            else:
                pattern = f"{self.document_prefix}*"

            keys = await self.cache_manager.keys(pattern)
            count = 0
            for key in keys:
                if await self.cache_manager.delete(key):
                    count += 1

            logger.info(f"Invalidated {count} document cache entries")
            return count
        except Exception as e:
            logger.error(f"Error invalidating document cache: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取RAG缓存统计信息"""
        try:
            retrieval_keys = await self.cache_manager.keys(f"{self.retrieval_prefix}*")
            vector_keys = await self.cache_manager.keys(f"{self.vector_prefix}*")
            document_keys = await self.cache_manager.keys(f"{self.document_prefix}*")

            stats = {
                "retrieval_cache": {
                    "entries": len(retrieval_keys),
                    "prefix": self.retrieval_prefix,
                },
                "vector_cache": {
                    "entries": len(vector_keys),
                    "prefix": self.vector_prefix,
                    "models": {},
                },
                "document_cache": {
                    "entries": len(document_keys),
                    "prefix": self.document_prefix,
                },
                "total_entries": len(retrieval_keys)
                + len(vector_keys)
                + len(document_keys),
            }

            # 统计不同模型的向量缓存
            for key in vector_keys:
                try:
                    # 解析键格式: rag:vector:model:hash
                    parts = key.split(":", 3)
                    if len(parts) >= 3:
                        model = parts[2]
                        if model not in stats["vector_cache"]["models"]:
                            stats["vector_cache"]["models"][model] = 0
                        stats["vector_cache"]["models"][model] += 1
                except:
                    continue

            return stats
        except Exception as e:
            logger.error(f"Error getting RAG cache stats: {e}")
            return {"error": str(e)}


# 全局RAG缓存实例
_rag_cache: Optional[RAGCache] = None


def get_rag_cache() -> RAGCache:
    """获取全局RAG缓存实例"""
    global _rag_cache
    if _rag_cache is None:
        _rag_cache = RAGCache()
    return _rag_cache


def rag_retrieval_cache(ttl: Optional[int] = None):
    """RAG检索缓存装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            rag_cache_instance = get_rag_cache()

            # 从参数中提取检索相关信息
            query = kwargs.get("query", args[0] if args else "")
            collection = kwargs.get("collection")
            top_k = kwargs.get("top_k", 5)

            # 尝试从缓存获取结果
            cached_result = await rag_cache_instance.get_cached_retrieval(
                query, collection, top_k, **kwargs
            )

            if cached_result is not None:
                return cached_result

            # 缓存未命中，调用原函数
            result = await func(*args, **kwargs)

            # 缓存结果
            if isinstance(result, list):
                await rag_cache_instance.cache_retrieval_result(
                    query, result, collection, top_k, ttl, **kwargs
                )

            return result

        return wrapper

    return decorator


def vector_cache(model: str = "default", ttl: Optional[int] = None):
    """向量缓存装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            rag_cache_instance = get_rag_cache()

            # 从参数中提取文本
            text = kwargs.get("text", args[0] if args else "")

            # 尝试从缓存获取向量
            cached_vector = await rag_cache_instance.get_cached_vector(text, model)

            if cached_vector is not None:
                return cached_vector

            # 缓存未命中，调用原函数
            vector = await func(*args, **kwargs)

            # 缓存向量
            if isinstance(vector, list) and len(vector) > 0:
                await rag_cache_instance.cache_vector(text, vector, model, ttl)

            return vector

        return wrapper

    return decorator


# 便捷函数
async def cache_retrieval_result(
    query: str,
    results: List[Dict[str, Any]],
    collection: str = None,
    top_k: int = 5,
    ttl: Optional[int] = None,
    **kwargs,
) -> bool:
    """缓存检索结果的便捷函数"""
    rag_cache_instance = get_rag_cache()
    return await rag_cache_instance.cache_retrieval_result(
        query, results, collection, top_k, ttl, **kwargs
    )


async def get_cached_retrieval(
    query: str, collection: str = None, top_k: int = 5, **kwargs
) -> Optional[List[Dict[str, Any]]]:
    """获取缓存检索结果的便捷函数"""
    rag_cache_instance = get_rag_cache()
    return await rag_cache_instance.get_cached_retrieval(
        query, collection, top_k, **kwargs
    )


async def cache_vector_result(
    text: str, vector: List[float], model: str = "default", ttl: Optional[int] = None
) -> bool:
    """缓存向量的便捷函数"""
    rag_cache_instance = get_rag_cache()
    return await rag_cache_instance.cache_vector(text, vector, model, ttl)


async def get_cached_vector_result(
    text: str, model: str = "default"
) -> Optional[List[float]]:
    """获取缓存向量的便捷函数"""
    rag_cache_instance = get_rag_cache()
    return await rag_cache_instance.get_cached_vector(text, model)
