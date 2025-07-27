"""ChromaDB适配器实现"""

import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from ...config.logging_config import get_logger
from ...exceptions import RAGServiceException
from ..embedding_service import EmbeddingService
from ..interfaces import (Document, RAGServiceInterface, RAGServiceStatus,
                          SearchResult, ServiceHealthInfo)

logger = get_logger("chromadb_adapter")


class ChromaDBAdapter(RAGServiceInterface):
    """ChromaDB适配器

    集成现有ChromaDB功能，提供统一的RAG服务接口
    """

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """初始化ChromaDB适配器

        Args:
            service_name: 服务名称
            config: 配置信息，包含：
                - persist_directory: 持久化目录
                - collection_name: 默认集合名称
                - embedding_model: 嵌入模型名称
                - embedding_provider: 嵌入服务提供商
        """
        super().__init__(service_name, config)

        if not CHROMA_AVAILABLE:
            raise RAGServiceException("chromadb库未安装，请运行: pip install chromadb")

        self.persist_directory = config.get("persist_directory", "./data/vectordb")
        self.default_collection = config.get("collection_name", "default")
        self.embedding_model = config.get("embedding_model", "text-embedding-ada-002")
        self.embedding_provider = config.get("embedding_provider", "openai")

        self.client = None
        self.embedding_service = None
        self._collections_cache = {}

        logger.info(f"ChromaDB适配器初始化: {service_name}")

    async def initialize(self) -> bool:
        """初始化ChromaDB客户端和嵌入服务"""
        try:
            # 确保持久化目录存在
            os.makedirs(self.persist_directory, exist_ok=True)

            # 初始化ChromaDB客户端
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            # 初始化嵌入服务
            self.embedding_service = EmbeddingService(
                model_name=self.embedding_model, provider=self.embedding_provider
            )

            # 测试连接
            await self._test_connection()

            self._is_initialized = True
            logger.info(f"ChromaDB适配器 {self.service_name} 初始化成功")
            return True

        except Exception as e:
            logger.error(f"ChromaDB适配器初始化失败: {e}")
            return False

    async def _test_connection(self):
        """测试ChromaDB连接"""
        try:
            # 尝试列出集合
            collections = self.client.list_collections()
            logger.debug(f"ChromaDB连接测试成功，发现 {len(collections)} 个集合")
        except Exception as e:
            raise RAGServiceException(f"ChromaDB连接测试失败: {e}")

    def _get_or_create_collection(self, collection_name: str = None):
        """获取或创建集合"""
        collection_name = collection_name or self.default_collection

        # 检查缓存
        if collection_name in self._collections_cache:
            return self._collections_cache[collection_name]

        try:
            # 尝试获取现有集合
            collection = self.client.get_collection(name=collection_name)
            logger.debug(f"获取现有集合: {collection_name}")
        except Exception:
            # 集合不存在，创建新集合
            collection = self.client.create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "description": f"TestAgent RAG集合: {collection_name}",
                    "created_by": self.service_name,
                    "created_at": datetime.now().isoformat(),
                },
            )
            logger.info(f"创建新集合: {collection_name}")

        # 缓存集合对象
        self._collections_cache[collection_name] = collection
        return collection

    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)

        try:
            # 生成查询向量
            query_embedding = await self.embedding_service.embed_text(query)

            # 获取集合
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
                for i, doc_id in enumerate(results["ids"][0]):
                    # 计算相似度分数（距离转换为相似度）
                    distance = (
                        results["distances"][0][i] if results["distances"] else 1.0
                    )
                    similarity_score = 1.0 / (1.0 + distance)  # 转换为0-1范围的相似度

                    # 应用相似度阈值
                    if similarity_score < similarity_threshold:
                        continue

                    # 构建文档对象
                    content = results["documents"][0][i] if results["documents"] else ""
                    metadata = (
                        results["metadatas"][0][i] if results["metadatas"] else {}
                    )

                    document = Document(
                        id=doc_id,
                        content=content,
                        metadata=metadata,
                        embedding=None,  # 不返回向量以节省内存
                    )

                    search_result = SearchResult(
                        document=document, similarity_score=similarity_score, rank=i + 1
                    )
                    search_results.append(search_result)

            logger.info(
                f"ChromaDB检索完成: 查询='{query[:50]}...', 结果数={len(search_results)}"
            )
            return search_results

        except Exception as e:
            logger.error(f"ChromaDB检索失败: {e}")
            raise RAGServiceException(f"检索失败: {e}")

    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            # 生成文档向量
            if document.embedding is None:
                document.embedding = await self.embedding_service.embed_text(
                    document.content
                )

            # 获取集合
            collection = self._get_or_create_collection(collection_name)

            # 准备元数据
            metadata = {**document.metadata}
            metadata.update(
                {
                    "added_at": datetime.now().isoformat(),
                    "added_by": self.service_name,
                    "content_length": len(document.content),
                }
            )

            # 添加到ChromaDB
            collection.add(
                ids=[document.id],
                documents=[document.content],
                embeddings=[document.embedding],
                metadatas=[metadata],
            )

            logger.info(f"文档已添加到ChromaDB: {document.id}")
            return document.id

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise RAGServiceException(f"添加文档失败: {e}")

    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            # 准备数据
            ids = []
            contents = []
            embeddings = []
            metadatas = []

            for document in documents:
                # 生成文档向量（如果没有）
                if document.embedding is None:
                    document.embedding = await self.embedding_service.embed_text(
                        document.content
                    )

                # 准备元数据
                metadata = {**document.metadata}
                metadata.update(
                    {
                        "added_at": datetime.now().isoformat(),
                        "added_by": self.service_name,
                        "content_length": len(document.content),
                    }
                )

                ids.append(document.id)
                contents.append(document.content)
                embeddings.append(document.embedding)
                metadatas.append(metadata)

            # 获取集合
            collection = self._get_or_create_collection(collection_name)

            # 批量添加到ChromaDB
            collection.add(
                ids=ids, documents=contents, embeddings=embeddings, metadatas=metadatas
            )

            logger.info(f"批量添加 {len(documents)} 个文档到ChromaDB")
            return ids

        except Exception as e:
            logger.error(f"批量添加文档失败: {e}")
            raise RAGServiceException(f"批量添加文档失败: {e}")

    async def delete_document(self, document_id: str, **kwargs) -> bool:
        """删除文档"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            collection = self._get_or_create_collection(collection_name)
            collection.delete(ids=[document_id])

            logger.info(f"文档已从ChromaDB删除: {document_id}")
            return True

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def delete_documents(self, document_ids: List[str], **kwargs) -> bool:
        """批量删除文档"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            collection = self._get_or_create_collection(collection_name)
            collection.delete(ids=document_ids)

            logger.info(f"批量删除 {len(document_ids)} 个文档从ChromaDB")
            return True

        except Exception as e:
            logger.error(f"批量删除文档失败: {e}")
            return False

    async def update_document(
        self, document_id: str, document: Document, **kwargs
    ) -> bool:
        """更新文档"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            # ChromaDB不支持直接更新，需要先删除再添加
            await self.delete_document(document_id, collection_name=collection_name)

            # 确保文档ID一致
            document.id = document_id
            await self.add_document(document, collection_name=collection_name)

            logger.info(f"文档已在ChromaDB中更新: {document_id}")
            return True

        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            return False

    async def get_document(self, document_id: str, **kwargs) -> Optional[Document]:
        """获取文档"""
        await self.ensure_initialized()

        collection_name = kwargs.get("collection_name", self.default_collection)

        try:
            collection = self._get_or_create_collection(collection_name)
            result = collection.get(
                ids=[document_id], include=["documents", "metadatas", "embeddings"]
            )

            if result["ids"] and result["ids"][0]:
                content = result["documents"][0] if result["documents"] else ""
                metadata = result["metadatas"][0] if result["metadatas"] else {}
                embedding = result["embeddings"][0] if result["embeddings"] else None

                return Document(
                    id=document_id,
                    content=content,
                    metadata=metadata,
                    embedding=embedding,
                )

            return None

        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            return None

    async def health_check(self) -> ServiceHealthInfo:
        """健康检查"""
        start_time = time.time()

        try:
            if not self._is_initialized:
                await self.initialize()

            # 测试基本操作
            collections = self.client.list_collections()

            # 测试嵌入服务
            if self.embedding_service:
                await self.embedding_service.embed_text("健康检查测试")

            response_time = (time.time() - start_time) * 1000

            health_info = ServiceHealthInfo(
                status=RAGServiceStatus.HEALTHY,
                response_time_ms=response_time,
                last_check_time=datetime.now().isoformat(),
                metadata={
                    "collections_count": len(collections),
                    "persist_directory": self.persist_directory,
                    "embedding_model": self.embedding_model,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            health_info = ServiceHealthInfo(
                status=RAGServiceStatus.UNAVAILABLE,
                response_time_ms=response_time,
                error_message=str(e),
                last_check_time=datetime.now().isoformat(),
            )
            logger.error(f"ChromaDB健康检查失败: {e}")

        self._update_health_check(health_info)
        return health_info

    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        info = {
            "service_name": self.service_name,
            "service_type": "ChromaDB",
            "version": (
                chromadb.__version__ if hasattr(chromadb, "__version__") else "unknown"
            ),
            "persist_directory": self.persist_directory,
            "default_collection": self.default_collection,
            "embedding_model": self.embedding_model,
            "embedding_provider": self.embedding_provider,
            "initialized": self._is_initialized,
        }

        if self._is_initialized and self.client:
            try:
                collections = self.client.list_collections()
                info["collections"] = [col.name for col in collections]
                info["collections_count"] = len(collections)
            except Exception as e:
                info["error"] = str(e)

        return info

    async def list_collections(self) -> List[str]:
        """列出所有集合"""
        await self.ensure_initialized()

        try:
            collections = self.client.list_collections()
            return [collection.name for collection in collections]
        except Exception as e:
            logger.error(f"列出集合失败: {e}")
            return []

    async def create_collection(self, collection_name: str, **kwargs) -> bool:
        """创建集合"""
        await self.ensure_initialized()

        try:
            metadata = kwargs.get("metadata", {})
            metadata.update(
                {
                    "created_by": self.service_name,
                    "created_at": datetime.now().isoformat(),
                }
            )

            collection = self.client.create_collection(
                name=collection_name, metadata=metadata
            )

            # 更新缓存
            self._collections_cache[collection_name] = collection

            logger.info(f"创建集合成功: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"创建集合失败: {e}")
            return False

    async def delete_collection(self, collection_name: str, **kwargs) -> bool:
        """删除集合"""
        await self.ensure_initialized()

        try:
            self.client.delete_collection(name=collection_name)

            # 清除缓存
            if collection_name in self._collections_cache:
                del self._collections_cache[collection_name]

            logger.info(f"删除集合成功: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            return False

    async def get_collection_info(
        self, collection_name: str, **kwargs
    ) -> Dict[str, Any]:
        """获取集合信息"""
        await self.ensure_initialized()

        try:
            collection = self._get_or_create_collection(collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "document_count": count,
                "service": self.service_name,
                "metadata": collection.metadata,
            }

        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {
                "name": collection_name,
                "document_count": 0,
                "service": self.service_name,
                "error": str(e),
            }
