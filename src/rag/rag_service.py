"""RAG知识库服务主接口"""

import os
import asyncio
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import asdict

from ..config.logging_config import get_logger
from ..config.settings import get_settings
from ..exceptions import RAGServiceException
from ..utils.performance import async_monitor_performance

from .document_parser import DocumentParser
from .text_splitter import TextSplitter, SemanticTextSplitter, TextChunk
from .embedding_service import EmbeddingService
from .vector_database import VectorDatabase, ChromaVectorDatabase, SearchResult

logger = get_logger("rag_service")


class RAGService:
    """RAG知识库服务，整合文档解析、文本分块、向量化和检索功能"""

    def __init__(
        self,
        vector_db: Optional[VectorDatabase] = None,
        embedding_service: Optional[EmbeddingService] = None,
        text_splitter: Optional[TextSplitter] = None,
        document_parser: Optional[DocumentParser] = None,
    ):
        """初始化RAG服务

        Args:
            vector_db: 向量数据库实例
            embedding_service: 向量化服务实例
            text_splitter: 文本分块器实例
            document_parser: 文档解析器实例
        """
        settings = get_settings()

        # 初始化各个组件
        self.vector_db = vector_db or ChromaVectorDatabase()
        self.embedding_service = embedding_service or EmbeddingService()
        self.text_splitter = text_splitter or SemanticTextSplitter()
        self.document_parser = document_parser or DocumentParser()

        # 配置参数
        self.default_collection = settings.default_collection_name
        self.max_search_results = settings.max_search_results

        logger.info("RAG service initialized successfully")

    @async_monitor_performance
    async def add_document(
        self,
        file_path: str,
        collection_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """添加文档到知识库

        Args:
            file_path: 文档文件路径
            collection_name: 集合名称
            metadata: 额外的元数据

        Returns:
            处理结果信息

        Raises:
            RAGServiceException: 处理失败时抛出
        """
        collection_name = collection_name or self.default_collection
        metadata = metadata or {}

        try:
            # 1. 解析文档
            logger.info(f"Parsing document: {file_path}")
            doc_result = await self.document_parser.parse_document(file_path)

            # 合并元数据
            combined_metadata = {**doc_result["metadata"], **metadata}

            # 2. 分块文本
            logger.info(f"Splitting text into chunks")
            chunks = self.text_splitter.split_text(
                doc_result["content"], combined_metadata
            )

            if not chunks:
                raise RAGServiceException("No chunks generated from document")

            # 3. 向量化文本块
            logger.info(f"Embedding {len(chunks)} chunks")
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.embed_texts(chunk_texts)

            # 4. 存储到向量数据库
            logger.info(f"Storing chunks in collection: {collection_name}")
            document_ids = await self.vector_db.store_documents(
                chunks, embeddings, collection_name
            )

            # 5. 返回处理结果
            result = {
                "file_path": file_path,
                "collection_name": collection_name,
                "chunks_count": len(chunks),
                "document_ids": document_ids,
                "word_count": doc_result.get("word_count", 0),
                "char_count": doc_result.get("char_count", 0),
                "metadata": combined_metadata,
            }

            logger.info(
                f"Successfully added document {file_path} with {len(chunks)} chunks"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to add document {file_path}: {e}")
            raise RAGServiceException(f"Failed to add document: {e}")

    @async_monitor_performance
    async def add_documents(
        self,
        file_paths: List[str],
        collection_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """批量添加文档到知识库

        Args:
            file_paths: 文档文件路径列表
            collection_name: 集合名称
            metadata: 额外的元数据

        Returns:
            批量处理结果
        """
        collection_name = collection_name or self.default_collection
        results = []
        errors = []

        # 并发处理文档
        tasks = []
        for file_path in file_paths:
            task = asyncio.create_task(
                self._add_single_document(file_path, collection_name, metadata)
            )
            tasks.append((file_path, task))

        for file_path, task in tasks:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                error_info = {"file_path": file_path, "error": str(e)}
                errors.append(error_info)
                logger.error(f"Failed to process {file_path}: {e}")

        summary = {
            "total_files": len(file_paths),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "collection_name": collection_name,
        }

        logger.info(
            f"Batch processing completed: {len(results)}/{len(file_paths)} successful"
        )
        return summary

    async def _add_single_document(
        self, file_path: str, collection_name: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """添加单个文档的包装方法"""
        return await self.add_document(file_path, collection_name, metadata)

    @async_monitor_performance
    async def search(
        self,
        query: str,
        collection_name: Optional[str] = None,
        top_k: Optional[int] = None,
        similarity_threshold: float = 0.0,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """搜索相关文档

        Args:
            query: 搜索查询
            collection_name: 集合名称
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
            include_metadata: 是否包含元数据

        Returns:
            搜索结果列表
        """
        collection_name = collection_name or self.default_collection
        top_k = top_k or self.max_search_results

        try:
            # 1. 向量化查询
            logger.info(f"Embedding search query")
            query_embedding = await self.embedding_service.embed_text(query)

            # 2. 向量搜索
            logger.info(f"Searching in collection: {collection_name}")
            search_results = await self.vector_db.search(
                query_embedding=query_embedding,
                collection_name=collection_name,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

            # 3. 格式化结果
            formatted_results = []
            for result in search_results:
                formatted_result = {
                    "content": result.content,
                    "similarity_score": result.similarity_score,
                    "chunk_id": result.chunk_id,
                }

                if include_metadata:
                    formatted_result["metadata"] = result.metadata

                formatted_results.append(formatted_result)

            logger.info(f"Found {len(formatted_results)} relevant documents")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise RAGServiceException(f"Search failed: {e}")

    async def get_document_by_id(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """根据ID获取文档

        Args:
            document_id: 文档ID
            collection_name: 集合名称

        Returns:
            文档信息，如果不存在返回None
        """
        collection_name = collection_name or self.default_collection

        try:
            return await self.vector_db.get_document(document_id, collection_name)
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            raise RAGServiceException(f"Failed to get document: {e}")

    async def delete_document(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> bool:
        """删除文档

        Args:
            document_id: 文档ID
            collection_name: 集合名称

        Returns:
            是否删除成功
        """
        collection_name = collection_name or self.default_collection

        try:
            return await self.vector_db.delete_documents([document_id], collection_name)
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise RAGServiceException(f"Failed to delete document: {e}")

    async def delete_documents(
        self, document_ids: List[str], collection_name: Optional[str] = None
    ) -> bool:
        """批量删除文档

        Args:
            document_ids: 文档ID列表
            collection_name: 集合名称

        Returns:
            是否删除成功
        """
        collection_name = collection_name or self.default_collection

        try:
            return await self.vector_db.delete_documents(document_ids, collection_name)
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise RAGServiceException(f"Failed to delete documents: {e}")

    async def get_collection_info(
        self, collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取集合信息

        Args:
            collection_name: 集合名称

        Returns:
            集合信息
        """
        collection_name = collection_name or self.default_collection

        try:
            return await self.vector_db.get_collection_info(collection_name)
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise RAGServiceException(f"Failed to get collection info: {e}")

    async def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            if hasattr(self.vector_db, "list_collections"):
                return await self.vector_db.list_collections()
            else:
                return [self.default_collection]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise RAGServiceException(f"Failed to list collections: {e}")

    async def reset_collection(self, collection_name: Optional[str] = None) -> bool:
        """重置集合

        Args:
            collection_name: 集合名称

        Returns:
            是否重置成功
        """
        collection_name = collection_name or self.default_collection

        try:
            if hasattr(self.vector_db, "reset_collection"):
                return await self.vector_db.reset_collection(collection_name)
            else:
                # 如果不支持重置，尝试删除所有文档
                info = await self.get_collection_info(collection_name)
                if info.get("count", 0) > 0:
                    logger.warning(
                        f"Vector database doesn't support reset, manual cleanup needed"
                    )
                return True
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise RAGServiceException(f"Failed to reset collection: {e}")

    async def add_text_directly(
        self, text: str, metadata: Dict[str, Any], collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """直接添加文本到知识库（不通过文件）

        Args:
            text: 要添加的文本内容
            metadata: 文本元数据
            collection_name: 集合名称

        Returns:
            处理结果信息
        """
        collection_name = collection_name or self.default_collection

        try:
            # 1. 分块文本
            chunks = self.text_splitter.split_text(text, metadata)

            if not chunks:
                raise RAGServiceException("No chunks generated from text")

            # 2. 向量化文本块
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.embed_texts(chunk_texts)

            # 3. 存储到向量数据库
            document_ids = await self.vector_db.store_documents(
                chunks, embeddings, collection_name
            )

            result = {
                "collection_name": collection_name,
                "chunks_count": len(chunks),
                "document_ids": document_ids,
                "word_count": len(text.split()),
                "char_count": len(text),
                "metadata": metadata,
            }

            logger.info(f"Successfully added text with {len(chunks)} chunks")
            return result

        except Exception as e:
            logger.error(f"Failed to add text: {e}")
            raise RAGServiceException(f"Failed to add text: {e}")

    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "vector_database": type(self.vector_db).__name__,
            "embedding_service": self.embedding_service.get_model_info(),
            "text_splitter": {
                "type": type(self.text_splitter).__name__,
                "chunk_size": self.text_splitter.chunk_size,
                "chunk_overlap": self.text_splitter.chunk_overlap,
            },
            "default_collection": self.default_collection,
            "max_search_results": self.max_search_results,
        }


class RAGServiceManager:
    """RAG服务管理器，支持多个RAG服务实例"""

    def __init__(self):
        self.services: Dict[str, RAGService] = {}
        self.default_service_name = "default"

    def add_service(self, name: str, service: RAGService):
        """添加RAG服务实例"""
        self.services[name] = service
        logger.info(f"Added RAG service: {name}")

    def get_service(self, name: Optional[str] = None) -> RAGService:
        """获取RAG服务实例"""
        name = name or self.default_service_name

        if name not in self.services:
            raise RAGServiceException(f"RAG service '{name}' not found")

        return self.services[name]

    def set_default_service(self, name: str):
        """设置默认服务"""
        if name in self.services:
            self.default_service_name = name
            logger.info(f"Set default RAG service to: {name}")
        else:
            raise RAGServiceException(f"Service '{name}' not found")

    def list_services(self) -> List[str]:
        """列出所有服务"""
        return list(self.services.keys())

    async def search_all_services(
        self, query: str, **kwargs
    ) -> Dict[str, List[Dict[str, Any]]]:
        """在所有服务中搜索"""
        results = {}

        for name, service in self.services.items():
            try:
                service_results = await service.search(query, **kwargs)
                results[name] = service_results
            except Exception as e:
                logger.error(f"Search failed in service {name}: {e}")
                results[name] = []

        return results
