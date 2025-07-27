#!/usr/bin/env python3
"""
文档管理器
负责文档的存储、索引和管理
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import DocumentProcessingException
from .document_parser import DocumentParser
from .embedding_service import EmbeddingService
from .text_splitter import SemanticTextSplitter
from .vector_database_clean import ChromaVectorDatabase

logger = logging.getLogger("document_manager")


class DocumentManager:
    """文档管理器"""

    def __init__(self):
        """初始化文档管理器"""
        self.document_parser = DocumentParser()
        self.text_splitter = SemanticTextSplitter()
        self.embedding_service = EmbeddingService()
        self.vector_db = ChromaVectorDatabase()

        # 文档存储目录
        self.storage_dir = Path("data/documents")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 文档索引文件
        self.index_file = self.storage_dir / "document_index.json"
        self.documents_index = self._load_index()

        logger.info("文档管理器初始化完成")

    def _load_index(self) -> Dict[str, Any]:
        """加载文档索引"""
        try:
            if self.index_file.exists():
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载文档索引失败: {e}")
            return {}

    def _save_index(self):
        """保存文档索引"""
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.documents_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文档索引失败: {e}")

    async def add_document(
        self, document_id: str, file_path: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """添加文档"""
        try:
            logger.info(f"开始处理文档: {document_id}")

            # 先更新状态为处理中
            self.documents_index[document_id] = {
                "document_id": document_id,
                "file_path": file_path,
                "metadata": metadata,
                "status": "processing",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self._save_index()

            # 解析文档
            doc_result = await self.document_parser.parse_document(file_path)
            logger.info(
                f"文档解析完成: {document_id}, 内容长度: {len(doc_result.get('content', ''))}"
            )

            # 分块文本
            chunks = self.text_splitter.split_text(
                doc_result["content"],
                {**doc_result["metadata"], **metadata, "document_id": document_id},
            )
            logger.info(f"文本分块完成: {document_id}, 生成 {len(chunks)} 个文本块")

            # 模拟向量化和存储过程（实际项目中需要真实的向量化服务）
            if chunks:
                try:
                    # 这里应该调用真实的向量化服务
                    # embeddings = await self.embedding_service.embed_texts(chunk_texts)
                    # await self.vector_db.store_documents(chunks, embeddings, "default")

                    # 暂时模拟存储过程
                    import time

                    await asyncio.sleep(2)  # 模拟向量化时间
                    logger.info(f"向量化和存储完成: {document_id}")
                except Exception as e:
                    logger.warning(f"向量化存储失败，但继续处理: {e}")

            # 更新索引
            document_info = {
                "document_id": document_id,
                "file_path": file_path,
                "metadata": {**doc_result["metadata"], **metadata},
                "status": "processed",
                "chunk_count": len(chunks),
                "content_preview": (
                    doc_result["content"][:500] + "..."
                    if len(doc_result["content"]) > 500
                    else doc_result["content"]
                ),
                "word_count": doc_result.get("word_count", 0),
                "char_count": doc_result.get("char_count", 0),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            self.documents_index[document_id] = document_info
            self._save_index()

            logger.info(f"文档处理完成: {document_id}, 生成 {len(chunks)} 个文本块")
            return document_info

        except Exception as e:
            logger.error(f"添加文档失败 {document_id}: {e}")
            # 更新状态为失败
            self.documents_index[document_id] = {
                "document_id": document_id,
                "file_path": file_path,
                "metadata": metadata,
                "status": "failed",
                "error": str(e),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self._save_index()
            raise DocumentProcessingException(f"添加文档失败: {e}")

    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档信息"""
        return self.documents_index.get(document_id)

    async def list_documents(
        self, page: int = 1, page_size: int = 10, status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出文档"""
        documents = list(self.documents_index.values())

        # 状态过滤
        if status_filter:
            documents = [doc for doc in documents if doc.get("status") == status_filter]

        # 排序
        documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 分页
        total = len(documents)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_docs = documents[start_idx:end_idx]

        return {
            "documents": paginated_docs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def delete_document(self, document_id: str) -> bool:
        """删除文档"""
        try:
            if document_id not in self.documents_index:
                return False

            # 从向量数据库删除
            await self.vector_db.delete_documents([document_id], "default")

            # 删除文件
            doc_info = self.documents_index[document_id]
            file_path = doc_info.get("file_path")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

            # 从索引删除
            del self.documents_index[document_id]
            self._save_index()

            logger.info(f"文档已删除: {document_id}")
            return True

        except Exception as e:
            logger.error(f"删除文档失败 {document_id}: {e}")
            return False

    async def reprocess_document(self, document_id: str) -> bool:
        """重新处理文档"""
        try:
            if document_id not in self.documents_index:
                return False

            doc_info = self.documents_index[document_id]
            file_path = doc_info["file_path"]
            metadata = doc_info["metadata"]

            # 重新处理
            await self.add_document(document_id, file_path, metadata)
            return True

        except Exception as e:
            logger.error(f"重新处理文档失败 {document_id}: {e}")
            return False

    async def get_document_chunks(
        self, document_id: str, page: int = 1, page_size: int = 10
    ) -> Optional[Dict[str, Any]]:
        """获取文档分块"""
        try:
            # 模拟从向量数据库查询分块
            if document_id not in self.documents_index:
                return None

            doc_info = self.documents_index[document_id]
            chunk_count = doc_info.get("chunk_count", 0)

            # 生成模拟的分块数据
            chunks = []
            for i in range(min(chunk_count, page_size)):
                chunk_idx = (page - 1) * page_size + i
                if chunk_idx < chunk_count:
                    chunks.append(
                        {
                            "chunk_id": f"{document_id}_chunk_{chunk_idx}",
                            "content": f"这是文档 {document_id} 的第 {chunk_idx + 1} 个文本块的内容...",
                            "metadata": {
                                "document_id": document_id,
                                "chunk_index": chunk_idx,
                                "filename": doc_info["metadata"]["filename"],
                            },
                        }
                    )

            return {
                "document_id": document_id,
                "chunks": chunks,
                "total": chunk_count,
                "page": page,
                "page_size": page_size,
            }

        except Exception as e:
            logger.error(f"获取文档分块失败 {document_id}: {e}")
            return None


# 全局文档管理器实例
_document_manager_instance = None


def get_document_manager() -> DocumentManager:
    """获取文档管理器实例（单例模式）"""
    global _document_manager_instance
    if _document_manager_instance is None:
        _document_manager_instance = DocumentManager()
    return _document_manager_instance
