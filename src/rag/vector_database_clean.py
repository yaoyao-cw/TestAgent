#!/usr/bin/env python3
"""
向量数据库服务模块 - 清理版本
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 向量数据库库
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

import logging
from ..exceptions import RAGServiceException
from .text_splitter import TextChunk

logger = logging.getLogger("vector_database")


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
        collection_name: str = "default"
    ) -> List[str]:
        """存储文档块和对应的向量"""
        raise NotImplementedError
    
    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "default",
        top_k: int = 5,
        similarity_threshold: float = 0.0
    ) -> List[SearchResult]:
        """搜索相似文档"""
        raise NotImplementedError


class ChromaVectorDatabase(VectorDatabase):
    """基于Chroma的向量数据库实现"""
    
    def __init__(self, persist_directory: Optional[str] = None):
        if not CHROMA_AVAILABLE:
            logger.warning("chromadb not available, using mock implementation")
            self.client = None
            return
        
        self.persist_directory = persist_directory or "data/vectordb"
        os.makedirs(self.persist_directory, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            logger.info(f"Initialized ChromaDB with persist directory: {self.persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
    
    def _get_or_create_collection(self, collection_name: str):
        """获取或创建集合"""
        if not self.client:
            return None
        
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.debug(f"Retrieved existing collection: {collection_name}")
            return collection
        except Exception:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")
            return collection
    
    async def store_documents(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        collection_name: str = "default"
    ) -> List[str]:
        """存储文档块和对应的向量"""
        if not self.client:
            # Mock implementation
            return [f"mock_id_{i}" for i in range(len(chunks))]
        
        try:
            collection = self._get_or_create_collection(collection_name)
            if not collection:
                return []
            
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
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"Stored {len(chunks)} documents in collection {collection_name}")
            return ids
            
        except Exception as e:
            logger.error(f"Failed to store documents: {e}")
            return []
    
    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "default",
        top_k: int = 5,
        similarity_threshold: float = 0.0
    ) -> List[SearchResult]:
        """搜索相似文档"""
        if not self.client:
            # Mock implementation
            return []
        
        try:
            collection = self._get_or_create_collection(collection_name)
            if not collection:
                return []
            
            # 执行搜索
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances']
            )
            
            # 转换结果格式
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    distance = results['distances'][0][i]
                    similarity_score = 1.0 - distance
                    
                    if similarity_score >= similarity_threshold:
                        result = SearchResult(
                            id=results['ids'][0][i],
                            content=results['documents'][0][i],
                            metadata=results['metadatas'][0][i] or {},
                            similarity_score=similarity_score,
                            chunk_id=results['ids'][0][i]
                        )
                        search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def search_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        collection_name: str = "default"
    ) -> List[Dict[str, Any]]:
        """根据元数据搜索文档"""
        if not self.client:
            return []
        
        try:
            collection = self._get_or_create_collection(collection_name)
            if not collection:
                return []
            
            # 构建查询条件
            where_clause = {}
            for key, value in metadata_filter.items():
                where_clause[key] = {"$eq": value}
            
            # 执行查询
            results = collection.get(
                where=where_clause,
                include=['documents', 'metadatas']
            )
            
            # 转换结果格式
            documents = []
            if results['ids']:
                for i in range(len(results['ids'])):
                    doc = {
                        "id": results['ids'][i],
                        "content": results['documents'][i] if results['documents'] else "",
                        "metadata": results['metadatas'][i] if results['metadatas'] else {}
                    }
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            return []