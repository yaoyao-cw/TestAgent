"""RAGFlow适配器实现"""

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

logger = get_logger("ragflow_adapter")


class RAGFlowAdapter(RAGServiceInterface):
    """RAGFlow适配器

    支持RAGFlow API调用，提供统一的RAG服务接口
    """

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """初始化RAGFlow适配器

        Args:
            service_name: 服务名称
            config: 配置信息，包含：
                - api_url: RAGFlow API地址
                - api_key: API密钥
                - dataset_id: 数据集ID
                - timeout: 请求超时时间
                - max_retries: 最大重试次数
        """
        super().__init__(service_name, config)

        self.api_url = config.get("api_url", "http://localhost:9380")
        self.api_key = config.get("api_key")
        self.dataset_id = config.get("dataset_id", "default")
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)

        # 确保API URL格式正确
        if not self.api_url.startswith(("http://", "https://")):
            self.api_url = f"http://{self.api_url}"

        self.api_url = self.api_url.rstrip("/")

        # HTTP会话
        self.session = None

        if not self.api_key:
            logger.warning("RAGFlow API密钥未配置，可能影响服务功能")

        logger.info(f"RAGFlow适配器初始化: {service_name}, API: {self.api_url}")

    async def initialize(self) -> bool:
        """初始化RAGFlow客户端"""
        try:
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                    "Content-Type": "application/json",
                },
            )

            # 测试连接
            await self._test_connection()

            self._is_initialized = True
            logger.info(f"RAGFlow适配器 {self.service_name} 初始化成功")
            return True

        except Exception as e:
            logger.error(f"RAGFlow适配器初始化失败: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            return False

    async def _test_connection(self):
        """测试RAGFlow连接"""
        try:
            # 尝试获取数据集信息
            url = f"{self.api_url}/api/v1/datasets"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(
                        f"RAGFlow连接测试成功，发现 {len(data.get('data', []))} 个数据集"
                    )
                elif response.status == 401:
                    raise RAGServiceException("RAGFlow API密钥无效")
                else:
                    raise RAGServiceException(
                        f"RAGFlow连接失败，状态码: {response.status}"
                    )
        except aiohttp.ClientError as e:
            raise RAGServiceException(f"RAGFlow连接测试失败: {e}")

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """发起HTTP请求"""
        if not self.session:
            raise RAGServiceException("RAGFlow会话未初始化")

        url = f"{self.api_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        raise RAGServiceException("RAGFlow API密钥无效")
                    elif response.status == 404:
                        raise RAGServiceException("RAGFlow资源不存在")
                    else:
                        error_text = await response.text()
                        raise RAGServiceException(
                            f"RAGFlow请求失败: {response.status} - {error_text}"
                        )

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise RAGServiceException(f"RAGFlow请求失败: {e}")

                # 指数退避重试
                await asyncio.sleep(2**attempt)
                logger.warning(f"RAGFlow请求重试 {attempt + 1}/{self.max_retries}: {e}")

    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)

        try:
            # 构建检索请求
            payload = {
                "query": query,
                "dataset_id": dataset_id,
                "top_k": top_k,
                "include_metadata": True,
            }

            # 发起检索请求
            response = await self._make_request("POST", "/api/v1/search", json=payload)

            # 解析结果
            search_results = []
            results_data = response.get("data", {}).get("results", [])

            for i, result in enumerate(results_data):
                # 提取相似度分数
                similarity_score = result.get("score", 0.0)

                # 应用相似度阈值
                if similarity_score < similarity_threshold:
                    continue

                # 构建文档对象
                document = Document(
                    id=result.get("id", str(uuid.uuid4())),
                    content=result.get("content", ""),
                    metadata={
                        "source": result.get("source", ""),
                        "title": result.get("title", ""),
                        "dataset_id": dataset_id,
                        **result.get("metadata", {}),
                    },
                )

                search_result = SearchResult(
                    document=document, similarity_score=similarity_score, rank=i + 1
                )
                search_results.append(search_result)

            logger.info(
                f"RAGFlow检索完成: 查询='{query[:50]}...', 结果数={len(search_results)}"
            )
            return search_results

        except Exception as e:
            logger.error(f"RAGFlow检索失败: {e}")
            raise RAGServiceException(f"检索失败: {e}")

    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            # 构建文档数据
            payload = {
                "dataset_id": dataset_id,
                "documents": [
                    {
                        "id": document.id,
                        "content": document.content,
                        "metadata": {
                            **document.metadata,
                            "added_at": datetime.now().isoformat(),
                            "added_by": self.service_name,
                        },
                    }
                ],
            }

            # 发起添加请求
            response = await self._make_request(
                "POST", "/api/v1/documents", json=payload
            )

            # 检查结果
            if response.get("success", False):
                logger.info(f"文档已添加到RAGFlow: {document.id}")
                return document.id
            else:
                raise RAGServiceException(
                    f"添加文档失败: {response.get('message', '未知错误')}"
                )

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise RAGServiceException(f"添加文档失败: {e}")

    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            # 构建批量文档数据
            docs_data = []
            for document in documents:
                docs_data.append(
                    {
                        "id": document.id,
                        "content": document.content,
                        "metadata": {
                            **document.metadata,
                            "added_at": datetime.now().isoformat(),
                            "added_by": self.service_name,
                        },
                    }
                )

            payload = {"dataset_id": dataset_id, "documents": docs_data}

            # 发起批量添加请求
            response = await self._make_request(
                "POST", "/api/v1/documents/batch", json=payload
            )

            # 检查结果
            if response.get("success", False):
                document_ids = [doc.id for doc in documents]
                logger.info(f"批量添加 {len(documents)} 个文档到RAGFlow")
                return document_ids
            else:
                raise RAGServiceException(
                    f"批量添加文档失败: {response.get('message', '未知错误')}"
                )

        except Exception as e:
            logger.error(f"批量添加文档失败: {e}")
            raise RAGServiceException(f"批量添加文档失败: {e}")

    async def delete_document(self, document_id: str, **kwargs) -> bool:
        """删除文档"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            # 发起删除请求
            response = await self._make_request(
                "DELETE",
                f"/api/v1/documents/{document_id}",
                params={"dataset_id": dataset_id},
            )

            if response.get("success", False):
                logger.info(f"文档已从RAGFlow删除: {document_id}")
                return True
            else:
                logger.error(f"删除文档失败: {response.get('message', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def delete_documents(self, document_ids: List[str], **kwargs) -> bool:
        """批量删除文档"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            # 构建批量删除请求
            payload = {"dataset_id": dataset_id, "document_ids": document_ids}

            response = await self._make_request(
                "DELETE", "/api/v1/documents/batch", json=payload
            )

            if response.get("success", False):
                logger.info(f"批量删除 {len(document_ids)} 个文档从RAGFlow")
                return True
            else:
                logger.error(f"批量删除文档失败: {response.get('message', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"批量删除文档失败: {e}")
            return False

    async def update_document(
        self, document_id: str, document: Document, **kwargs
    ) -> bool:
        """更新文档"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            # 构建更新数据
            payload = {
                "dataset_id": dataset_id,
                "content": document.content,
                "metadata": {
                    **document.metadata,
                    "updated_at": datetime.now().isoformat(),
                    "updated_by": self.service_name,
                },
            }

            response = await self._make_request(
                "PUT", f"/api/v1/documents/{document_id}", json=payload
            )

            if response.get("success", False):
                logger.info(f"文档已在RAGFlow中更新: {document_id}")
                return True
            else:
                logger.error(f"更新文档失败: {response.get('message', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            return False

    async def get_document(self, document_id: str, **kwargs) -> Optional[Document]:
        """获取文档"""
        await self.ensure_initialized()

        dataset_id = kwargs.get("dataset_id", self.dataset_id)

        try:
            response = await self._make_request(
                "GET",
                f"/api/v1/documents/{document_id}",
                params={"dataset_id": dataset_id},
            )

            if response.get("success", False):
                doc_data = response.get("data", {})
                return Document(
                    id=document_id,
                    content=doc_data.get("content", ""),
                    metadata=doc_data.get("metadata", {}),
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
            response = await self._make_request("GET", "/api/v1/health")

            response_time = (time.time() - start_time) * 1000

            health_info = ServiceHealthInfo(
                status=RAGServiceStatus.HEALTHY,
                response_time_ms=response_time,
                last_check_time=datetime.now().isoformat(),
                metadata={
                    "api_url": self.api_url,
                    "dataset_id": self.dataset_id,
                    "api_version": response.get("version", "unknown"),
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
            logger.error(f"RAGFlow健康检查失败: {e}")

        self._update_health_check(health_info)
        return health_info

    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        info = {
            "service_name": self.service_name,
            "service_type": "RAGFlow",
            "api_url": self.api_url,
            "dataset_id": self.dataset_id,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "initialized": self._is_initialized,
        }

        if self._is_initialized:
            try:
                # 获取数据集信息
                response = await self._make_request("GET", "/api/v1/datasets")
                datasets = response.get("data", [])
                info["available_datasets"] = [ds.get("id") for ds in datasets]
                info["datasets_count"] = len(datasets)
            except Exception as e:
                info["error"] = str(e)

        return info

    async def list_collections(self) -> List[str]:
        """列出所有集合（数据集）"""
        await self.ensure_initialized()

        try:
            response = await self._make_request("GET", "/api/v1/datasets")
            datasets = response.get("data", [])
            return [dataset.get("id", dataset.get("name", "")) for dataset in datasets]
        except Exception as e:
            logger.error(f"列出数据集失败: {e}")
            return []

    async def create_collection(self, collection_name: str, **kwargs) -> bool:
        """创建集合（数据集）"""
        await self.ensure_initialized()

        try:
            payload = {
                "name": collection_name,
                "description": kwargs.get(
                    "description", f"由 {self.service_name} 创建的数据集"
                ),
                "metadata": kwargs.get("metadata", {}),
            }

            response = await self._make_request(
                "POST", "/api/v1/datasets", json=payload
            )

            if response.get("success", False):
                logger.info(f"创建数据集成功: {collection_name}")
                return True
            else:
                logger.error(f"创建数据集失败: {response.get('message', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"创建数据集失败: {e}")
            return False

    async def delete_collection(self, collection_name: str, **kwargs) -> bool:
        """删除集合（数据集）"""
        await self.ensure_initialized()

        try:
            response = await self._make_request(
                "DELETE", f"/api/v1/datasets/{collection_name}"
            )

            if response.get("success", False):
                logger.info(f"删除数据集成功: {collection_name}")
                return True
            else:
                logger.error(f"删除数据集失败: {response.get('message', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"删除数据集失败: {e}")
            return False

    async def get_collection_info(
        self, collection_name: str, **kwargs
    ) -> Dict[str, Any]:
        """获取集合（数据集）信息"""
        await self.ensure_initialized()

        try:
            response = await self._make_request(
                "GET", f"/api/v1/datasets/{collection_name}"
            )

            if response.get("success", False):
                dataset_info = response.get("data", {})
                return {
                    "name": collection_name,
                    "document_count": dataset_info.get("document_count", 0),
                    "service": self.service_name,
                    "description": dataset_info.get("description", ""),
                    "created_at": dataset_info.get("created_at", ""),
                    "metadata": dataset_info.get("metadata", {}),
                }
            else:
                return {
                    "name": collection_name,
                    "document_count": 0,
                    "service": self.service_name,
                    "error": response.get("message", "未知错误"),
                }

        except Exception as e:
            logger.error(f"获取数据集信息失败: {e}")
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
