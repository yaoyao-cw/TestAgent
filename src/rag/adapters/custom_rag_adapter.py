"""自研RAG适配器实现"""

import time
import uuid
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from ...config.logging_config import get_logger
from ...exceptions import RAGServiceException
from ..interfaces import (
    RAGServiceInterface,
    Document,
    SearchResult,
    ServiceHealthInfo,
    RAGServiceStatus,
)

logger = get_logger("custom_rag_adapter")


class CustomRAGAdapter(RAGServiceInterface):
    """自研RAG适配器

    支持自研RAG服务接入，提供统一的RAG服务接口
    """

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """初始化自研RAG适配器

        Args:
            service_name: 服务名称
            config: 配置信息，包含：
                - api_url: 自研RAG API地址
                - api_key: API密钥
                - model_name: 嵌入模型名称
                - index_name: 索引名称
                - timeout: 请求超时时间
                - max_retries: 最大重试次数
                - custom_headers: 自定义请求头
        """
        super().__init__(service_name, config)

        self.api_url = config.get("api_url", "http://localhost:8080")
        self.api_key = config.get("api_key")
        self.model_name = config.get("model_name", "custom-embedding-model")
        self.index_name = config.get("index_name", "default")
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.custom_headers = config.get("custom_headers", {})

        # 确保API URL格式正确
        if not self.api_url.startswith(("http://", "https://")):
            self.api_url = f"http://{self.api_url}"

        self.api_url = self.api_url.rstrip("/")

        # HTTP会话
        self.session = None

        if not self.api_key:
            logger.warning("自研RAG API密钥未配置，可能影响服务功能")

        logger.info(f"自研RAG适配器初始化: {service_name}, API: {self.api_url}")

    async def initialize(self) -> bool:
        """初始化自研RAG客户端"""
        try:
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"Content-Type": "application/json", **self.custom_headers}

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                # 也支持其他认证方式
                headers["X-API-Key"] = self.api_key

            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)

            # 测试连接
            await self._test_connection()

            self._is_initialized = True
            logger.info(f"自研RAG适配器 {self.service_name} 初始化成功")
            return True

        except Exception as e:
            logger.error(f"自研RAG适配器初始化失败: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            return False

    async def _test_connection(self):
        """测试自研RAG连接"""
        try:
            # 尝试获取服务状态
            url = f"{self.api_url}/api/v1/status"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(
                        f"自研RAG连接测试成功: {data.get('status', 'unknown')}"
                    )
                elif response.status == 401:
                    raise RAGServiceException("自研RAG API密钥无效")
                else:
                    # 尝试备用健康检查端点
                    await self._test_health_endpoint()
        except aiohttp.ClientError as e:
            raise RAGServiceException(f"自研RAG连接测试失败: {e}")

    async def _test_health_endpoint(self):
        """测试健康检查端点"""
        try:
            url = f"{self.api_url}/health"
            async with self.session.get(url) as response:
                if response.status == 200:
                    logger.debug("自研RAG健康检查端点连接成功")
                else:
                    raise RAGServiceException(
                        f"自研RAG健康检查失败，状态码: {response.status}"
                    )
        except aiohttp.ClientError as e:
            raise RAGServiceException(f"自研RAG健康检查失败: {e}")

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """发起HTTP请求"""
        if not self.session:
            raise RAGServiceException("自研RAG会话未初始化")

        url = f"{self.api_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        raise RAGServiceException("自研RAG API密钥无效")
                    elif response.status == 404:
                        raise RAGServiceException("自研RAG资源不存在")
                    else:
                        error_text = await response.text()
                        raise RAGServiceException(
                            f"自研RAG请求失败: {response.status} - {error_text}"
                        )

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise RAGServiceException(f"自研RAG请求失败: {e}")

                # 指数退避重试
                await asyncio.sleep(2**attempt)
                logger.warning(f"自研RAG请求重试 {attempt + 1}/{self.max_retries}: {e}")

    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)

        try:
            # 构建检索请求
            payload = {
                "query": query,
                "index_name": index_name,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "model_name": self.model_name,
                "include_metadata": True,
                "include_embeddings": False,
            }

            # 发起检索请求
            response = await self._make_request("POST", "/api/v1/search", json=payload)

            # 解析结果
            search_results = []
            results_data = response.get("results", response.get("data", []))

            for i, result in enumerate(results_data):
                # 提取相似度分数
                similarity_score = result.get(
                    "similarity_score", result.get("score", 0.0)
                )

                # 应用相似度阈值
                if similarity_score < similarity_threshold:
                    continue

                # 构建文档对象
                document = Document(
                    id=result.get("id", result.get("document_id", str(uuid.uuid4()))),
                    content=result.get("content", result.get("text", "")),
                    metadata={
                        "source": result.get("source", ""),
                        "title": result.get("title", ""),
                        "index_name": index_name,
                        "model_name": self.model_name,
                        **result.get("metadata", {}),
                    },
                )

                search_result = SearchResult(
                    document=document, similarity_score=similarity_score, rank=i + 1
                )
                search_results.append(search_result)

            logger.info(
                f"自研RAG检索完成: 查询='{query[:50]}...', 结果数={len(search_results)}"
            )
            return search_results

        except Exception as e:
            logger.error(f"自研RAG检索失败: {e}")
            raise RAGServiceException(f"检索失败: {e}")

    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            # 构建文档数据
            payload = {
                "index_name": index_name,
                "document": {
                    "id": document.id,
                    "content": document.content,
                    "metadata": {
                        **document.metadata,
                        "added_at": datetime.now().isoformat(),
                        "added_by": self.service_name,
                    },
                },
                "model_name": self.model_name,
                "auto_embed": True,  # 自动生成嵌入向量
            }

            # 如果已有嵌入向量，直接使用
            if document.embedding:
                payload["document"]["embedding"] = document.embedding
                payload["auto_embed"] = False

            # 发起添加请求
            response = await self._make_request(
                "POST", "/api/v1/documents", json=payload
            )

            # 检查结果
            if response.get("success", True):  # 默认认为成功
                document_id = response.get("document_id", document.id)
                logger.info(f"文档已添加到自研RAG: {document_id}")
                return document_id
            else:
                raise RAGServiceException(
                    f"添加文档失败: {response.get('error', response.get('message', '未知错误'))}"
                )

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise RAGServiceException(f"添加文档失败: {e}")

    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            # 构建批量文档数据
            docs_data = []
            for document in documents:
                doc_data = {
                    "id": document.id,
                    "content": document.content,
                    "metadata": {
                        **document.metadata,
                        "added_at": datetime.now().isoformat(),
                        "added_by": self.service_name,
                    },
                }

                # 如果已有嵌入向量，包含在数据中
                if document.embedding:
                    doc_data["embedding"] = document.embedding

                docs_data.append(doc_data)

            payload = {
                "index_name": index_name,
                "documents": docs_data,
                "model_name": self.model_name,
                "auto_embed": True,
            }

            # 发起批量添加请求
            response = await self._make_request(
                "POST", "/api/v1/documents/batch", json=payload
            )

            # 检查结果
            if response.get("success", True):
                document_ids = response.get(
                    "document_ids", [doc.id for doc in documents]
                )
                logger.info(f"批量添加 {len(documents)} 个文档到自研RAG")
                return document_ids
            else:
                raise RAGServiceException(
                    f"批量添加文档失败: {response.get('error', response.get('message', '未知错误'))}"
                )

        except Exception as e:
            logger.error(f"批量添加文档失败: {e}")
            raise RAGServiceException(f"批量添加文档失败: {e}")

    async def delete_document(self, document_id: str, **kwargs) -> bool:
        """删除文档"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            # 发起删除请求
            response = await self._make_request(
                "DELETE",
                f"/api/v1/documents/{document_id}",
                params={"index_name": index_name},
            )

            if response.get("success", True):
                logger.info(f"文档已从自研RAG删除: {document_id}")
                return True
            else:
                logger.error(
                    f"删除文档失败: {response.get('error', response.get('message', '未知错误'))}"
                )
                return False

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def delete_documents(self, document_ids: List[str], **kwargs) -> bool:
        """批量删除文档"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            # 构建批量删除请求
            payload = {"index_name": index_name, "document_ids": document_ids}

            response = await self._make_request(
                "DELETE", "/api/v1/documents/batch", json=payload
            )

            if response.get("success", True):
                logger.info(f"批量删除 {len(document_ids)} 个文档从自研RAG")
                return True
            else:
                logger.error(
                    f"批量删除文档失败: {response.get('error', response.get('message', '未知错误'))}"
                )
                return False

        except Exception as e:
            logger.error(f"批量删除文档失败: {e}")
            return False

    async def update_document(
        self, document_id: str, document: Document, **kwargs
    ) -> bool:
        """更新文档"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            # 构建更新数据
            payload = {
                "index_name": index_name,
                "document": {
                    "id": document_id,
                    "content": document.content,
                    "metadata": {
                        **document.metadata,
                        "updated_at": datetime.now().isoformat(),
                        "updated_by": self.service_name,
                    },
                },
                "model_name": self.model_name,
                "auto_embed": True,
            }

            # 如果已有嵌入向量，直接使用
            if document.embedding:
                payload["document"]["embedding"] = document.embedding
                payload["auto_embed"] = False

            response = await self._make_request(
                "PUT", f"/api/v1/documents/{document_id}", json=payload
            )

            if response.get("success", True):
                logger.info(f"文档已在自研RAG中更新: {document_id}")
                return True
            else:
                logger.error(
                    f"更新文档失败: {response.get('error', response.get('message', '未知错误'))}"
                )
                return False

        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            return False

    async def get_document(self, document_id: str, **kwargs) -> Optional[Document]:
        """获取文档"""
        await self.ensure_initialized()

        index_name = kwargs.get("index_name", self.index_name)

        try:
            response = await self._make_request(
                "GET",
                f"/api/v1/documents/{document_id}",
                params={"index_name": index_name, "include_embedding": False},
            )

            if response.get("success", True) and response.get("document"):
                doc_data = response["document"]
                return Document(
                    id=document_id,
                    content=doc_data.get("content", ""),
                    metadata=doc_data.get("metadata", {}),
                    embedding=doc_data.get("embedding"),
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

            # 测试API连接
            try:
                response = await self._make_request("GET", "/api/v1/status")
            except:
                # 如果状态端点不存在，尝试健康检查端点
                response = await self._make_request("GET", "/health")

            response_time = (time.time() - start_time) * 1000

            health_info = ServiceHealthInfo(
                status=RAGServiceStatus.HEALTHY,
                response_time_ms=response_time,
                last_check_time=datetime.now().isoformat(),
                metadata={
                    "api_url": self.api_url,
                    "index_name": self.index_name,
                    "model_name": self.model_name,
                    "service_status": response.get("status", "unknown"),
                    "version": response.get("version", "unknown"),
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
            logger.error(f"自研RAG健康检查失败: {e}")

        self._update_health_check(health_info)
        return health_info

    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        info = {
            "service_name": self.service_name,
            "service_type": "CustomRAG",
            "api_url": self.api_url,
            "index_name": self.index_name,
            "model_name": self.model_name,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "initialized": self._is_initialized,
        }

        if self._is_initialized:
            try:
                # 获取服务状态信息
                try:
                    response = await self._make_request("GET", "/api/v1/status")
                except:
                    response = await self._make_request("GET", "/health")

                info.update(
                    {
                        "service_status": response.get("status", "unknown"),
                        "version": response.get("version", "unknown"),
                        "available_models": response.get("models", []),
                        "available_indices": response.get("indices", []),
                    }
                )
            except Exception as e:
                info["error"] = str(e)

        return info

    async def list_collections(self) -> List[str]:
        """列出所有集合（索引）"""
        await self.ensure_initialized()

        try:
            response = await self._make_request("GET", "/api/v1/indices")
            indices = response.get("indices", response.get("data", []))

            if isinstance(indices, list):
                return [
                    idx.get("name", idx) if isinstance(idx, dict) else str(idx)
                    for idx in indices
                ]
            else:
                return [self.index_name]  # 返回默认索引

        except Exception as e:
            logger.error(f"列出索引失败: {e}")
            return [self.index_name]

    async def create_collection(self, collection_name: str, **kwargs) -> bool:
        """创建集合（索引）"""
        await self.ensure_initialized()

        try:
            payload = {
                "index_name": collection_name,
                "model_name": kwargs.get("model_name", self.model_name),
                "dimension": kwargs.get("dimension", 768),
                "metric": kwargs.get("metric", "cosine"),
                "description": kwargs.get(
                    "description", f"由 {self.service_name} 创建的索引"
                ),
                "metadata": kwargs.get("metadata", {}),
            }

            response = await self._make_request("POST", "/api/v1/indices", json=payload)

            if response.get("success", True):
                logger.info(f"创建索引成功: {collection_name}")
                return True
            else:
                logger.error(
                    f"创建索引失败: {response.get('error', response.get('message', '未知错误'))}"
                )
                return False

        except Exception as e:
            logger.error(f"创建索引失败: {e}")
            return False

    async def delete_collection(self, collection_name: str, **kwargs) -> bool:
        """删除集合（索引）"""
        await self.ensure_initialized()

        try:
            response = await self._make_request(
                "DELETE", f"/api/v1/indices/{collection_name}"
            )

            if response.get("success", True):
                logger.info(f"删除索引成功: {collection_name}")
                return True
            else:
                logger.error(
                    f"删除索引失败: {response.get('error', response.get('message', '未知错误'))}"
                )
                return False

        except Exception as e:
            logger.error(f"删除索引失败: {e}")
            return False

    async def get_collection_info(
        self, collection_name: str, **kwargs
    ) -> Dict[str, Any]:
        """获取集合（索引）信息"""
        await self.ensure_initialized()

        try:
            response = await self._make_request(
                "GET", f"/api/v1/indices/{collection_name}"
            )

            if response.get("success", True) and response.get("index"):
                index_info = response["index"]
                return {
                    "name": collection_name,
                    "document_count": index_info.get("document_count", 0),
                    "service": self.service_name,
                    "model_name": index_info.get("model_name", self.model_name),
                    "dimension": index_info.get("dimension", 0),
                    "metric": index_info.get("metric", "cosine"),
                    "created_at": index_info.get("created_at", ""),
                    "metadata": index_info.get("metadata", {}),
                }
            else:
                return {
                    "name": collection_name,
                    "document_count": 0,
                    "service": self.service_name,
                    "error": response.get(
                        "error", response.get("message", "索引不存在")
                    ),
                }

        except Exception as e:
            logger.error(f"获取索引信息失败: {e}")
            return {
                "name": collection_name,
                "document_count": 0,
                "service": self.service_name,
                "error": str(e),
            }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            self.session = None
