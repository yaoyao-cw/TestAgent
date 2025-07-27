"""向量数据库服务模块"""

import json
import os
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

# 向量数据库库
try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from ..exceptions import RAGServiceException
from ..utils.performance import async_monitor_performance
from .text_splitter import TextChunk

logger = get_logger("vector_database")


@dataclass
class SearchResult:
    """搜索结果数据类"""

    id: str
    content: str
    metadata: Dict[str, Any]
    similarity_score: float
    chunk_id: Optional[str] = None


class VectorDatabase:
    """向量数据库抽象基类"""

    async def store_documents(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        collection_name: str = "default",
    ) -> List[str]:
        """存储文档块和对应的向量"""
        raise NotImplementedError

    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "default",
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """搜索相似文档"""
        raise NotImplementedError

    async def delete_documents(
        self, document_ids: List[str], collection_name: str = "default"
    ) -> bool:
        """删除文档"""
        raise NotImplementedError

    async def get_collection_info(
        self, collection_name: str = "default"
    ) -> Dict[str, Any]:
        """获取集合信息"""
        raise NotImplementedError


class ChromaVectorDatabase(VectorDatabase):
    """基于Chroma的向量数据库实现"""

    def __init__(self, persist_directory: Optional[str] = None):
        if not CHROMA_AVAILABLE:
            raise RAGServiceException("chromadb not installed")

        settings = get_settings()
        self.persist_directory = (
            persist_directory or settings.vector_db_persist_directory
        )

        # 确保持久化目录存在
        os.makedirs(self.persist_directory, exist_ok=True)

        # 初始化Chroma客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

        logger.info(
            f"Initialized ChromaDB with persist directory: {self.persist_directory}"
        )

    def _get_or_create_collection(self, collection_name: str):
        """获取或创建集合"""
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.debug(f"Retrieved existing collection: {collection_name}")
            return collection
        except Exception:
            # 集合不存在，创建新集合
            collection = self.client.create_collection(
                name=collection_name, metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")
            return collection

    async def store_documents(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        collection_name: str = "default",
    ) -> List[str]:
        """存储文档块和对应的向量"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 准备数据
            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = chunk.chunk_id or f"{collection_name}_chunk_{i}"
                ids.append(chunk_id)
                documents.append(chunk.content)
                metadatas.append(chunk.metadata)

            # 存储到Chroma
            collection.add(
                ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
            )

            logger.info(
                f"Stored {len(chunks)} documents in collection {collection_name}"
            )
            return ids

        except Exception as e:
            logger.error(f"Failed to store documents: {e}")
            raise RAGServiceException(f"Failed to store documents: {e}")

    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "default",
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """搜索相似文档"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 执行搜索
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            # 转换结果格式
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    # 计算相似度分数（距离转换为相似度）
                    distance = results["distances"][0][i]
                    similarity_score = 1.0 - distance  # 假设使用余弦距离

                    if similarity_score >= similarity_threshold:
                        result = SearchResult(
                            id=results["ids"][0][i],
                            content=results["documents"][0][i],
                            metadata=results["metadatas"][0][i] or {},
                            similarity_score=similarity_score,
                            chunk_id=results["ids"][0][i],
                        )
                        search_results.append(result)

            logger.info(f"Found {len(search_results)} similar documents")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise RAGServiceException(f"Search failed: {e}")

    async def delete_documents(
        self, document_ids: List[str], collection_name: str = "default"
    ) -> bool:
        """删除文档"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 删除文档
            collection.delete(ids=document_ids)

            logger.info(
                f"Deleted {len(document_ids)} documents from collection {collection_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False

    async def get_collection_info(
        self, collection_name: str = "default"
    ) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 获取集合统计信息
            count = collection.count()

            return {
                "name": collection_name,
                "count": count,
                "metadata": collection.metadata or {},
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"name": collection_name, "count": 0, "error": str(e)}

    async def search_by_metadata(
        self, metadata_filter: Dict[str, Any], collection_name: str = "default"
    ) -> List[Dict[str, Any]]:
        """根据元数据搜索文档"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 构建查询条件
            where_clause = {}
            for key, value in metadata_filter.items():
                where_clause[key] = {"$eq": value}

            # 执行查询
            results = collection.get(
                where=where_clause, include=["documents", "metadatas"]
            )

            # 转换结果格式
            documents = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    doc = {
                        "id": results["ids"][i],
                        "content": (
                            results["documents"][i] if results["documents"] else ""
                        ),
                        "metadata": (
                            results["metadatas"][i] if results["metadatas"] else {}
                        ),
                    }
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            return []
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": f"TestAgent collection: {collection_name}"},
            )
            logger.info(f"Created new collection: {collection_name}")

        return collection

    @async_monitor_performance
    async def store_documents(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        collection_name: str = "default",
    ) -> List[str]:
        """存储文档块和向量到Chroma"""
        if len(chunks) != len(embeddings):
            raise RAGServiceException("Number of chunks and embeddings must match")

        try:
            collection = self._get_or_create_collection(collection_name)

            # 准备数据
            ids = []
            documents = []
            metadatas = []

            for chunk, embedding in zip(chunks, embeddings):
                # 生成唯一ID
                doc_id = chunk.chunk_id or str(uuid.uuid4())
                ids.append(doc_id)
                documents.append(chunk.content)

                # 准备元数据
                metadata = {**chunk.metadata}
                metadata.update(
                    {
                        "start_index": chunk.start_index,
                        "end_index": chunk.end_index,
                        "chunk_id": chunk.chunk_id,
                        "content_length": len(chunk.content),
                    }
                )
                metadatas.append(metadata)

            # 存储到Chroma
            collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

            logger.info(
                f"Stored {len(chunks)} documents in collection '{collection_name}'"
            )
            return ids

        except Exception as e:
            logger.error(f"Failed to store documents: {e}")
            raise RAGServiceException(f"Failed to store documents: {e}")

    @async_monitor_performance
    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "default",
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """在Chroma中搜索相似文档"""
        try:
            collection = self._get_or_create_collection(collection_name)

            # 执行搜索
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            # 处理结果
            search_results = []

            if results["ids"] and results["ids"][0]:
                ids = results["ids"][0]
                documents = results["documents"][0] if results["documents"] else []
                metadatas = results["metadatas"][0] if results["metadatas"] else []
                distances = results["distances"][0] if results["distances"] else []

                for i, doc_id in enumerate(ids):
                    # 将距离转换为相似度分数 (Chroma返回的是L2距离，越小越相似)
                    # 转换为0-1范围的相似度分数
                    similarity = 1.0 / (1.0 + distances[i]) if distances else 0.0

                    # 应用相似度阈值过滤
                    if similarity < similarity_threshold:
                        continue

                    metadata = metadatas[i] if i < len(metadatas) else {}
                    content = documents[i] if i < len(documents) else ""
                    chunk_id = metadata.get("chunk_id", None)

                    search_results.append(
                        SearchResult(
                            id=doc_id,
                            content=content,
                            metadata=metadata,
                            similarity_score=similarity,
                            chunk_id=chunk_id,
                        )
                    )

            logger.info(
                f"Found {len(search_results)} results in collection '{collection_name}'"
            )
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise RAGServiceException(f"Search failed: {e}")

    @async_monitor_performance
    async def delete_documents(
        self, document_ids: List[str], collection_name: str = "default"
    ) -> bool:
        """从Chroma中删除文档"""
        try:
            collection = self._get_or_create_collection(collection_name)
            collection.delete(ids=document_ids)

            logger.info(
                f"Deleted {len(document_ids)} documents from collection '{collection_name}'"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise RAGServiceException(f"Failed to delete documents: {e}")

    async def get_collection_info(
        self, collection_name: str = "default"
    ) -> Dict[str, Any]:
        """获取Chroma集合信息"""
        try:
            collection = self._get_or_create_collection(collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "count": count,
                "metadata": collection.metadata,
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise RAGServiceException(f"Failed to get collection info: {e}")

    async def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            collections = self.client.list_collections()
            return [collection.name for collection in collections]

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise RAGServiceException(f"Failed to list collections: {e}")

    async def get_document(
        self, document_id: str, collection_name: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        try:
            collection = self._get_or_create_collection(collection_name)
            result = collection.get(
                ids=[document_id], include=["documents", "metadatas", "embeddings"]
            )

            if result["ids"] and result["ids"][0]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0] if result["documents"] else "",
                    "metadata": result["metadatas"][0] if result["metadatas"] else {},
                    "embedding": (
                        result["embeddings"][0] if result["embeddings"] else []
                    ),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise RAGServiceException(f"Failed to get document: {e}")

    async def reset_collection(self, collection_name: str) -> bool:
        """重置集合"""
        try:
            self.client.delete_collection(name=collection_name)
            self._get_or_create_collection(collection_name)

            logger.info(f"Reset collection '{collection_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise RAGServiceException(f"Failed to reset collection: {e}")
