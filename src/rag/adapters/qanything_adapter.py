"""QAnything适配器实现"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ...config.logging_config import get_logger
from ...exceptions import RAGServiceException
from ..interfaces import (Document, RAGServiceInterface, RAGServiceStatus,
                          SearchResult, ServiceHealthInfo)

logger = get_logger("qanything_adapter")


class QAnythingAdapter(RAGServiceInterface):
    """QAnything适配器

    实现QAnything服务集成，提供统一的RAG服务接口
    """

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """初始化QAnything适配器

        Args:
            service_name: 服务名称
            config: 配置信息，包含：
                - api_url: QAnything API地址
                - api_key: API密钥
                - knowledge_base_id: 知识库ID
                - timeout: 请求超时时间
                - max_retries: 最大重试次数
        """
        super().__init__(service_name, config)

        self.api_url = config.get("api_url", "http://localhost:8777")
        self.api_key = config.get("api_key")
        self.knowledge_base_id = config.get("knowledge_base_id", "default")
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)

        # 确保API URL格式正确
        if not self.api_url.startswith(("http://", "https://")):
            self.api_url = f"http://{self.api_url}"

        self.api_url = self.api_url.rstrip("/")

        # HTTP会话
        self.session = None

        if not self.api_key:
            logger.warning("QAnything API密钥未配置，可能影响服务功能")

        logger.info(f"QAnything适配器初始化: {service_name}, API: {self.api_url}")

    async def initialize(self) -> bool:
        """初始化QAnything客户端"""
        try:
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"Content-Type": "application/json"}

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)

            # 测试连接
            await self._test_connection()

            self._is_initialized = True
            logger.info(f"QAnything适配器 {self.service_name} 初始化成功")
            return True

        except Exception as e:
            logger.error(f"QAnything适配器初始化失败: {e}")
            if self.session:
                await self.session.close()
                self.session = None
            return False

    async def _test_connection(self):
        """测试QAnything连接"""
        try:
            # 尝试获取知识库列表
            url = f"{self.api_url}/api/local_doc_qa/list_knowledge_base"
            async with self.session.post(url, json={}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 200:
                        kb_list = data.get("data", [])
                        logger.debug(
                            f"QAnything连接测试成功，发现 {len(kb_list)} 个知识库"
                        )
                    else:
                        raise RAGServiceException(
                            f"QAnything API错误: {data.get('msg', '未知错误')}"
                        )
                elif response.status == 401:
                    raise RAGServiceException("QAnything API密钥无效")
                else:
                    raise RAGServiceException(
                        f"QAnything连接失败，状态码: {response.status}"
                    )
        except aiohttp.ClientError as e:
            raise RAGServiceException(f"QAnything连接测试失败: {e}")

    async def _make_request(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """发起HTTP请求"""
        if not self.session:
            raise RAGServiceException("QAnything会话未初始化")

        url = f"{self.api_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            return data
                        else:
                            raise RAGServiceException(
                                f"QAnything API错误: {data.get('msg', '未知错误')}"
                            )
                    elif response.status == 401:
                        raise RAGServiceException("QAnything API密钥无效")
                    else:
                        error_text = await response.text()
                        raise RAGServiceException(
                            f"QAnything请求失败: {response.status} - {error_text}"
                        )

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise RAGServiceException(f"QAnything请求失败: {e}")

                # 指数退避重试
                await asyncio.sleep(2**attempt)
                logger.warning(
                    f"QAnything请求重试 {attempt + 1}/{self.max_retries}: {e}"
                )

    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档"""
        await self.ensure_initialized()

        knowledge_base_id = kwargs.get("knowledge_base_id", self.knowledge_base_id)
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)

        try:
            # 构建检索请求
            payload = {
                "knowledge_base_id": knowledge_base_id,
                "question": query,
                "top_k": top_k,
                "score_threshold": similarity_threshold,
                "history": [],
            }

            # 发起检索请求
            response = await self._make_request(
                "/api/local_doc_qa/local_doc_chat", payload
            )

            # 解析结果
            search_results = []
            source_documents = response.get("data", {}).get("source_documents", [])

            for i, doc in enumerate(source_documents):
                # 提取相似度分数
                similarity_score = doc.get("score", 0.0)

                # 应用相似度阈值
                if similarity_score < similarity_threshold:
                    continue

                # 构建文档对象
                document = Document(
                    id=doc.get("id", str(uuid.uuid4())),
                    content=doc.get("page_content", ""),
                    metadata={
                        "source": doc.get("metadata", {}).get("source", ""),
                        "page": doc.get("metadata", {}).get("page", 0),
                        "knowledge_base_id": knowledge_base_id,
                        **doc.get("metadata", {}),
                    },
                )

                search_result = SearchResult(
                    document=document, similarity_score=similarity_score, rank=i + 1
                )
                search_results.append(search_result)

            logger.info(
                f"QAnything检索完成: 查询='{query[:50]}...', 结果数={len(search_results)}"
            )
            return search_results

        except Exception as e:
            logger.error(f"QAnything检索失败: {e}")
            raise RAGServiceException(f"检索失败: {e}")

    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库"""
        await self.ensure_initialized()

        knowledge_base_id = kwargs.get("knowledge_base_id", self.knowledge_base_id)

        try:
            # QAnything通常通过文件上传添加文档
            # 这里我们尝试通过文本直接添加
            payload = {
                "knowledge_base_id": knowledge_base_id,
                "file_name": document.metadata.get("filename", f"{document.id}.txt"),
                "file_content": document.content,
                "metadata": {
                    **document.metadata,
                    "added_at": datetime.now().isoformat(),
                    "added_by": self.service_name,
                },
            }

            # 发起添加请求
            response = await self._make_request(
                "/api/local_doc_qa/upload_file", payload
            )

            # 检查结果
            if response.get("code") == 200:
                logger.info(f"文档已添加到QAnything: {document.id}")
                return document.id
            else:
                raise RAGServiceException(
                    f"添加文档失败: {response.get('msg', '未知错误')}"
                )

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise RAGServiceException(f"添加文档失败: {e}")

    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库"""
        await self.ensure_initialized()

        # QAnything可能不支持真正的批量添加，我们逐个添加
        document_ids = []
        errors = []

        for document in documents:
            try:
                doc_id = await self.add_document(document, **kwargs)
                document_ids.append(doc_id)
            except Exception as e:
                errors.append(f"文档 {document.id} 添加失败: {e}")
                logger.error(f"添加文档失败: {document.id} - {e}")

        if errors:
            logger.warning(f"批量添加完成，但有 {len(errors)} 个文档失败")

        logger.info(f"批量添加 {len(document_ids)}/{len(documents)} 个文档到QAnything")
        return document_ids

    async def delete_document(self, document_id: str, **kwargs) -> bool:
        """删除文档"""
        await self.ensure_initialized()

        knowledge_base_id = kwargs.get("knowledge_base_id", self.knowledge_base_id)

        try:
            # 构建删除请求
            payload = {
                "knowledge_base_id": knowledge_base_id,
                "file_name": document_id,  # QAnything通常使用文件名作为标识
            }

            response = await self._make_request(
                "/api/local_doc_qa/delete_file", payload
            )

            if response.get("code") == 200:
                logger.info(f"文档已从QAnything删除: {document_id}")
                return True
            else:
                logger.error(f"删除文档失败: {response.get('msg', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def delete_documents(self, document_ids: List[str], **kwargs) -> bool:
        """批量删除文档"""
        await self.ensure_initialized()

        success_count = 0
        for document_id in document_ids:
            if await self.delete_document(document_id, **kwargs):
                success_count += 1

        logger.info(f"批量删除 {success_count}/{len(document_ids)} 个文档从QAnything")
        return success_count == len(document_ids)

    async def update_document(
        self, document_id: str, document: Document, **kwargs
    ) -> bool:
        """更新文档"""
        await self.ensure_initialized()

        try:
            # QAnything可能不支持直接更新，我们先删除再添加
            await self.delete_document(document_id, **kwargs)

            # 确保文档ID一致
            document.id = document_id
            await self.add_document(document, **kwargs)

            logger.info(f"文档已在QAnything中更新: {document_id}")
            return True

        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            return False

    async def get_document(self, document_id: str, **kwargs) -> Optional[Document]:
        """获取文档"""
        await self.ensure_initialized()

        knowledge_base_id = kwargs.get("knowledge_base_id", self.knowledge_base_id)

        try:
            # QAnything可能不支持直接通过ID获取文档
            # 我们尝试通过列出文件来查找
            payload = {"knowledge_base_id": knowledge_base_id}

            response = await self._make_request("/api/local_doc_qa/list_files", payload)

            files = response.get("data", [])
            for file_info in files:
                if file_info.get("file_name") == document_id:
                    # 找到文件，但QAnything可能不返回完整内容
                    return Document(
                        id=document_id,
                        content="",  # QAnything通常不返回完整内容
                        metadata={
                            "filename": file_info.get("file_name", ""),
                            "file_size": file_info.get("file_size", 0),
                            "knowledge_base_id": knowledge_base_id,
                            **file_info.get("metadata", {}),
                        },
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
            payload = {}
            response = await self._make_request(
                "/api/local_doc_qa/list_knowledge_base", payload
            )

            response_time = (time.time() - start_time) * 1000

            health_info = ServiceHealthInfo(
                status=RAGServiceStatus.HEALTHY,
                response_time_ms=response_time,
                last_check_time=datetime.now().isoformat(),
                metadata={
                    "api_url": self.api_url,
                    "knowledge_base_id": self.knowledge_base_id,
                    "knowledge_bases_count": len(response.get("data", [])),
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
            logger.error(f"QAnything健康检查失败: {e}")

        self._update_health_check(health_info)
        return health_info

    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        info = {
            "service_name": self.service_name,
            "service_type": "QAnything",
            "api_url": self.api_url,
            "knowledge_base_id": self.knowledge_base_id,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "initialized": self._is_initialized,
        }

        if self._is_initialized:
            try:
                # 获取知识库信息
                response = await self._make_request(
                    "/api/local_doc_qa/list_knowledge_base", {}
                )
                knowledge_bases = response.get("data", [])
                info["available_knowledge_bases"] = [
                    kb.get("kb_id") for kb in knowledge_bases
                ]
                info["knowledge_bases_count"] = len(knowledge_bases)
            except Exception as e:
                info["error"] = str(e)

        return info

    async def list_collections(self) -> List[str]:
        """列出所有集合（知识库）"""
        await self.ensure_initialized()

        try:
            response = await self._make_request(
                "/api/local_doc_qa/list_knowledge_base", {}
            )
            knowledge_bases = response.get("data", [])
            return [kb.get("kb_id", kb.get("kb_name", "")) for kb in knowledge_bases]
        except Exception as e:
            logger.error(f"列出知识库失败: {e}")
            return []

    async def create_collection(self, collection_name: str, **kwargs) -> bool:
        """创建集合（知识库）"""
        await self.ensure_initialized()

        try:
            payload = {
                "knowledge_base_name": collection_name,
                "vector_store_type": kwargs.get("vector_store_type", "faiss"),
                "embed_model": kwargs.get("embed_model", "text2vec-base-chinese"),
            }

            response = await self._make_request(
                "/api/local_doc_qa/new_knowledge_base", payload
            )

            if response.get("code") == 200:
                logger.info(f"创建知识库成功: {collection_name}")
                return True
            else:
                logger.error(f"创建知识库失败: {response.get('msg', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"创建知识库失败: {e}")
            return False

    async def delete_collection(self, collection_name: str, **kwargs) -> bool:
        """删除集合（知识库）"""
        await self.ensure_initialized()

        try:
            payload = {"knowledge_base_id": collection_name}

            response = await self._make_request(
                "/api/local_doc_qa/delete_knowledge_base", payload
            )

            if response.get("code") == 200:
                logger.info(f"删除知识库成功: {collection_name}")
                return True
            else:
                logger.error(f"删除知识库失败: {response.get('msg', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"删除知识库失败: {e}")
            return False

    async def get_collection_info(
        self, collection_name: str, **kwargs
    ) -> Dict[str, Any]:
        """获取集合（知识库）信息"""
        await self.ensure_initialized()

        try:
            # 获取知识库列表
            response = await self._make_request(
                "/api/local_doc_qa/list_knowledge_base", {}
            )

            knowledge_bases = response.get("data", [])
            for kb in knowledge_bases:
                if (
                    kb.get("kb_id") == collection_name
                    or kb.get("kb_name") == collection_name
                ):
                    # 获取文件列表来计算文档数量
                    files_response = await self._make_request(
                        "/api/local_doc_qa/list_files",
                        {"knowledge_base_id": collection_name},
                    )

                    files = files_response.get("data", [])

                    return {
                        "name": collection_name,
                        "document_count": len(files),
                        "service": self.service_name,
                        "vector_store_type": kb.get("vs_type", ""),
                        "embed_model": kb.get("embed_model", ""),
                        "created_time": kb.get("create_time", ""),
                        "metadata": kb,
                    }

            return {
                "name": collection_name,
                "document_count": 0,
                "service": self.service_name,
                "error": "知识库不存在",
            }

        except Exception as e:
            logger.error(f"获取知识库信息失败: {e}")
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
