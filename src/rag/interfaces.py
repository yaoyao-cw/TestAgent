"""RAG服务统一接口定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..config.logging_config import get_logger

logger = get_logger("rag_interfaces")


class RAGServiceStatus(Enum):
    """RAG服务状态枚举"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class Document:
    """文档数据类"""

    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "embedding": self.embedding,
        }


@dataclass
class SearchResult:
    """搜索结果数据类"""

    document: Document
    similarity_score: float
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "document": self.document.to_dict(),
            "similarity_score": self.similarity_score,
            "rank": self.rank,
        }


@dataclass
class ServiceHealthInfo:
    """服务健康信息"""

    status: RAGServiceStatus
    response_time_ms: float
    error_message: Optional[str] = None
    last_check_time: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RAGServiceInterface(ABC):
    """RAG服务统一接口

    定义了所有RAG服务适配器必须实现的标准接口，
    支持文档检索、添加、删除和健康检查等核心功能。
    """

    def __init__(self, service_name: str, config: Dict[str, Any]):
        """初始化RAG服务

        Args:
            service_name: 服务名称
            config: 服务配置
        """
        self.service_name = service_name
        self.config = config
        self._is_initialized = False
        self._last_health_check: Optional[ServiceHealthInfo] = None

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化服务连接

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 5, **kwargs
    ) -> List[SearchResult]:
        """检索相关文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: 其他查询参数

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        pass

    @abstractmethod
    async def add_document(self, document: Document, **kwargs) -> str:
        """添加文档到知识库

        Args:
            document: 要添加的文档
            **kwargs: 其他参数

        Returns:
            str: 文档ID
        """
        pass

    @abstractmethod
    async def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """批量添加文档到知识库

        Args:
            documents: 要添加的文档列表
            **kwargs: 其他参数

        Returns:
            List[str]: 文档ID列表
        """
        pass

    @abstractmethod
    async def delete_document(self, document_id: str, **kwargs) -> bool:
        """删除文档

        Args:
            document_id: 文档ID
            **kwargs: 其他参数

        Returns:
            bool: 删除是否成功
        """
        pass

    @abstractmethod
    async def delete_documents(self, document_ids: List[str], **kwargs) -> bool:
        """批量删除文档

        Args:
            document_ids: 文档ID列表
            **kwargs: 其他参数

        Returns:
            bool: 删除是否成功
        """
        pass

    @abstractmethod
    async def update_document(
        self, document_id: str, document: Document, **kwargs
    ) -> bool:
        """更新文档

        Args:
            document_id: 文档ID
            document: 更新后的文档
            **kwargs: 其他参数

        Returns:
            bool: 更新是否成功
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: str, **kwargs) -> Optional[Document]:
        """获取文档

        Args:
            document_id: 文档ID
            **kwargs: 其他参数

        Returns:
            Optional[Document]: 文档对象，如果不存在返回None
        """
        pass

    @abstractmethod
    async def health_check(self) -> ServiceHealthInfo:
        """健康检查

        Returns:
            ServiceHealthInfo: 服务健康信息
        """
        pass

    @abstractmethod
    async def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息

        Returns:
            Dict[str, Any]: 服务信息
        """
        pass

    # 可选实现的方法

    async def list_collections(self) -> List[str]:
        """列出所有集合

        Returns:
            List[str]: 集合名称列表
        """
        return ["default"]

    async def create_collection(self, collection_name: str, **kwargs) -> bool:
        """创建集合

        Args:
            collection_name: 集合名称
            **kwargs: 其他参数

        Returns:
            bool: 创建是否成功
        """
        return True

    async def delete_collection(self, collection_name: str, **kwargs) -> bool:
        """删除集合

        Args:
            collection_name: 集合名称
            **kwargs: 其他参数

        Returns:
            bool: 删除是否成功
        """
        return True

    async def get_collection_info(
        self, collection_name: str, **kwargs
    ) -> Dict[str, Any]:
        """获取集合信息

        Args:
            collection_name: 集合名称
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 集合信息
        """
        return {
            "name": collection_name,
            "document_count": 0,
            "service": self.service_name,
        }

    # 工具方法

    @property
    def is_initialized(self) -> bool:
        """检查服务是否已初始化"""
        return self._is_initialized

    @property
    def last_health_check(self) -> Optional[ServiceHealthInfo]:
        """获取最后一次健康检查结果"""
        return self._last_health_check

    def _update_health_check(self, health_info: ServiceHealthInfo):
        """更新健康检查结果"""
        self._last_health_check = health_info
        logger.debug(f"服务 {self.service_name} 健康检查更新: {health_info.status}")

    async def ensure_initialized(self):
        """确保服务已初始化"""
        if not self._is_initialized:
            success = await self.initialize()
            if not success:
                raise RuntimeError(f"RAG服务 {self.service_name} 初始化失败")
            self._is_initialized = True

    def __str__(self) -> str:
        return f"RAGService({self.service_name})"

    def __repr__(self) -> str:
        return f"RAGService(name='{self.service_name}', initialized={self._is_initialized})"
