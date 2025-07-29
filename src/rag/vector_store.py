#!/usr/bin/env python3
"""
向量存储服务
提供向量存储的统一接口
"""

from typing import List, Dict, Any, Optional
from .vector_database_clean import ChromaVectorDatabase
import logging

logger = logging.getLogger("vector_store")


class VectorStore:
    """向量存储服务"""

    def __init__(self):
        """初始化向量存储"""
        self.vector_db = ChromaVectorDatabase()
        logger.info("向量存储服务初始化完成")

    async def similarity_search(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """相似度搜索"""
        try:
            # 这里需要先向量化查询
            from .embedding_service import EmbeddingService

            embedding_service = EmbeddingService()
            query_embedding = await embedding_service.embed_text(query)

            # 执行搜索
            results = await self.vector_db.search(
                query_embedding=query_embedding,
                collection_name="default",
                top_k=k,
                similarity_threshold=score_threshold,
            )

            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_result = {
                    "content": result.content,
                    "score": result.similarity_score,
                    "metadata": result.metadata,
                }
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []


# 全局向量存储实例
_vector_store_instance = None


def get_vector_store() -> VectorStore:
    """获取向量存储实例（单例模式）"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
